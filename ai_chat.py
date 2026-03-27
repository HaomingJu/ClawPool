#!/usr/bin/env python3
"""
AI 对话类 — 基于 DeepSeek API
支持多轮上下文记忆，并在消息累积过多时自动总结历史，防止 context 爆炸。
集成 JenkinsOps / GitlabOps / FeishuBitableOps 作为 Function Calling 工具。

依赖安装：
    pip install openai requests

环境变量：
    DEEPSEEK_API_KEY  DeepSeek API Key（必填）
    LLM_MODEL         模型名称（默认 deepseek-chat）
    JENKINS_URL       Jenkins 服务地址
    JENKINS_USER      Jenkins 用户名
    JENKINS_TOKEN     Jenkins API Token
    GITLAB_URL        GitLab 服务地址
    GITLAB_TOKEN      GitLab Access Token
    SHOW_THINKING     设为 1 时打印 Tool 调用日志
"""

import os
import json
from openai import OpenAI

from jenkins_ops import JenkinsOps
from gitlab_ops import GitlabOps
from feishu_bitable_ops import FeishuBitableOps
from tools_definition import TOOLS

# ── 配置 ──────────────────────────────────────────────────────────
MODEL       = os.environ.get("LLM_MODEL", "deepseek-chat")
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.1"))  # 低温度让工具调用更稳定

SUMMARY_THRESHOLD_ROUNDS = 10
KEEP_RECENT_ROUNDS = 3

SHOW_THINKING = os.environ.get("SHOW_THINKING", "0") == "1"

# ── DeepSeek 客户端 ───────────────────────────────────────────────

def _get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise EnvironmentError("请设置环境变量 DEEPSEEK_API_KEY")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _llm_chat(messages: list[dict], tools: list | None = None) -> dict:
    """
    调用 DeepSeek API。
    返回 dict：
      - content:        str，模型回复文本
      - tool_calls:     list | None，标准化工具调用（供 _dispatch_tool 使用）
      - _history_msg:   dict，直接追加进 messages 的 assistant 消息（OpenAI 原生格式）
      - _tool_call_ids: list[str]，每个 tool call 对应的 id
    """
    client = _get_client()
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "tool_choice": "auto",   # 明确告知模型可以调用工具，防止被忽略
    }
    if tools:
        kwargs["tools"] = tools
    else:
        kwargs.pop("tool_choice", None)  # 无工具时不传 tool_choice
    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0].message

    tool_calls = None
    tool_call_ids = []
    if choice.tool_calls:
        tool_calls = [
            {
                "function": {
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
            }
            for tc in choice.tool_calls
        ]
        tool_call_ids = [tc.id for tc in choice.tool_calls]

    history_msg = choice.model_dump()
    history_msg.pop("audio", None)

    return {
        "content": choice.content or "",
        "tool_calls": tool_calls,
        "_history_msg": history_msg,
        "_tool_call_ids": tool_call_ids,
    }


def _llm_simple(messages: list[dict]) -> str:
    """无工具的简单对话，返回文本（用于摘要压缩）。"""
    return _llm_chat(messages)["content"].strip()

# ─────────────────────────────────────────────────────────────────

# ── 初始化 Ops 客户端（从环境变量读取） ───────────────────────────
_jenkins = JenkinsOps(
    base_url=os.environ.get("JENKINS_URL", "http://localhost:8080"),
    username=os.environ.get("JENKINS_USER", "admin"),
    api_token=os.environ.get("JENKINS_TOKEN", ""),
)

_gitlab = GitlabOps(
    base_url=os.environ.get("GITLAB_URL", "https://gitlab.com"),
    access_token=os.environ.get("GITLAB_TOKEN", ""),
)

_bitable = FeishuBitableOps(
    app_id=os.environ.get("APP_ID", ""),
    app_secret=os.environ.get("APP_SECRET", ""),
)
# ─────────────────────────────────────────────────────────────────

# ── 项目配置（view_id 区分项目，filter 条件固定） ──────────────────
_PROJECT_CONFIG = {
    "北汽":   {"app_token": "Ft2ibanVKaEeMjsW2aTcr8eynvd", "table_id": "tblTsX1YCNXfFgTP", "view_id": "vew3bze81M"},
    "上汽":   {"app_token": "Ft2ibanVKaEeMjsW2aTcr8eynvd", "table_id": "tblTsX1YCNXfFgTP", "view_id": "vewVL8akAQ"},
    "广丰":   {"app_token": "Ft2ibanVKaEeMjsW2aTcr8eynvd", "table_id": "tblTsX1YCNXfFgTP", "view_id": "vewddvPkuM"},
    "奇瑞T28": {"app_token": "UzOobqjfDaXOvPsWYRMc1ggSnrf", "table_id": "tblRAa8RNhrPGVX8", "view_id": "vewddvPkuM"},
}
# 别名映射
_PROJECT_ALIASES = {
    "上汽ep2": "上汽", "上汽ep": "上汽", "saic": "上汽",
    "gac": "广丰", "广丰gac": "广丰",
    "baic": "北汽",
    "奇瑞": "奇瑞T28", "t28": "奇瑞T28",
}
_PENDING_MR_FILTERS = [
    {"field_name": "代码合入评审", "operator": "is", "value": ["评审通过待合入"]},
    {"field_name": "CR评审",      "operator": "is", "value": ["通过"]},
]


def _get_pending_mrs(project_name: str) -> str:
    """根据项目名查询待合入 MR，返回格式化字符串。"""
    key = _PROJECT_ALIASES.get(project_name.lower(), project_name)
    cfg = _PROJECT_CONFIG.get(key)
    if not cfg:
        available = "、".join(_PROJECT_CONFIG.keys())
        return f"[未知项目: {project_name}]，支持的项目：{available}"
    records = _bitable.search_records(
        app_token=cfg["app_token"],
        table_id=cfg["table_id"],
        view_id=cfg["view_id"],
        filter_conditions=_PENDING_MR_FILTERS,
        page_size=50,
    )
    return json.dumps(records, ensure_ascii=False)


# ── Tool 调度器 ───────────────────────────────────────────────────

def _dispatch_tool(name: str, args: dict) -> str:
    """根据工具名称调用对应的 Ops 方法，返回字符串结果。"""
    try:
        # Jenkins
        if name == "jenkins_ping":
            return str(_jenkins.ping())
        if name == "jenkins_list_jobs":
            return json.dumps(_jenkins.list_jobs(), ensure_ascii=False)
        if name == "jenkins_get_job_info":
            return json.dumps(_jenkins.get_job_info(args["job_name"]), ensure_ascii=False)
        if name == "jenkins_trigger_build":
            _jenkins.trigger_build(args["job_name"], args.get("parameters"))
            return f"已触发 Job [{args['job_name']}] 构建"
        if name == "jenkins_get_last_build":
            return json.dumps(_jenkins.get_last_build(args["job_name"]), ensure_ascii=False)
        if name == "jenkins_get_build_log":
            log = _jenkins.get_build_log(args["job_name"], args["build_number"])
            return log[-3000:] if len(log) > 3000 else log  # 截断避免 context 过长
        if name == "jenkins_get_queue":
            return json.dumps(_jenkins.get_queue(), ensure_ascii=False)

        # GitLab
        if name == "gitlab_ping":
            return str(_gitlab.ping())
        if name == "gitlab_list_projects":
            return json.dumps(_gitlab.list_projects(search=args.get("search")), ensure_ascii=False)
        if name == "gitlab_list_branches":
            return json.dumps(_gitlab.list_branches(args["project_id"]), ensure_ascii=False)
        if name == "gitlab_create_branch":
            return json.dumps(_gitlab.create_branch(
                args["project_id"], args["branch"], args["ref"]
            ), ensure_ascii=False)
        if name == "gitlab_list_merge_requests":
            return json.dumps(_gitlab.list_merge_requests(
                args["project_id"], args.get("state", "opened")
            ), ensure_ascii=False)
        if name == "gitlab_create_merge_request":
            extra = {k: v for k, v in args.items()
                     if k not in ("project_id", "source_branch", "target_branch", "title")}
            return json.dumps(_gitlab.create_merge_request(
                args["project_id"], args["source_branch"],
                args["target_branch"], args["title"], **extra
            ), ensure_ascii=False)
        if name == "gitlab_accept_merge_request":
            return json.dumps(_gitlab.accept_merge_request(
                args["project_id"], args["mr_iid"], args.get("squash", False)
            ), ensure_ascii=False)
        if name == "gitlab_get_merge_request":
            return json.dumps(_gitlab.get_merge_request(
                args["project_id"], args["mr_iid"]
            ), ensure_ascii=False)
        if name == "gitlab_check_mr_mergeable":
            return json.dumps(_gitlab.check_mr_mergeable(
                args["project_id"], args["mr_iid"]
            ), ensure_ascii=False)
        if name == "gitlab_list_pipelines":
            return json.dumps(_gitlab.list_pipelines(
                args["project_id"], args.get("ref"), args.get("status")
            ), ensure_ascii=False)
        if name == "gitlab_create_pipeline":
            return json.dumps(_gitlab.create_pipeline(
                args["project_id"], args["ref"], args.get("variables")
            ), ensure_ascii=False)
        if name == "gitlab_retry_pipeline":
            return json.dumps(_gitlab.retry_pipeline(
                args["project_id"], args["pipeline_id"]
            ), ensure_ascii=False)
        if name == "gitlab_list_tags":
            return json.dumps(_gitlab.list_tags(args["project_id"]), ensure_ascii=False)
        if name == "gitlab_create_tag":
            return json.dumps(_gitlab.create_tag(
                args["project_id"], args["tag_name"],
                args["ref"], args.get("message")
            ), ensure_ascii=False)

        # Feishu Bitable
        if name == "bitable_list_tables":
            return json.dumps(_bitable.list_tables(args["app_token"]), ensure_ascii=False)
        if name == "bitable_list_views":
            return json.dumps(_bitable.list_views(args["app_token"], args["table_id"]), ensure_ascii=False)
        if name == "bitable_list_fields":
            return json.dumps(_bitable.list_fields(args["app_token"], args["table_id"]), ensure_ascii=False)
        if name == "bitable_get_record":
            return json.dumps(_bitable.get_record(
                args["app_token"], args["table_id"], args["record_id"]
            ), ensure_ascii=False)
        if name == "bitable_search_records":
            return json.dumps(_bitable.search_records(
                app_token=args["app_token"],
                table_id=args["table_id"],
                filter_conditions=args.get("filter_conditions"),
                conjunction=args.get("conjunction", "and"),
                field_names=args.get("field_names"),
                page_size=args.get("page_size", 20),
                view_id=args.get("view_id"),
            ), ensure_ascii=False)

        # 高层业务工具
        if name == "get_pending_mrs":
            return _get_pending_mrs(args["project_name"])

        return f"[未知工具: {name}]"

    except Exception as e:
        return f"[工具调用失败] {name}: {e}"


# ─────────────────────────────────────────────────────────────────


class AI:
    """
    多轮对话 AI，内置上下文记忆与自动摘要压缩。
    通过 DeepSeek Function Calling 集成 Jenkins / GitLab / 飞书多维表格工具。

    消息结构：
        [system] [summary(可选)] [近期对话...] [当前 user]

    当历史超过 SUMMARY_THRESHOLD_ROUNDS 轮时，将旧消息压缩为一段摘要，
    保留最近 KEEP_RECENT_ROUNDS 轮保持连贯性，避免 context 过长。
    """

    def __init__(
        self,
        system_prompt: str = """你是一个专业的AI助手，负责北汽、上汽(上汽EP2)、广丰(GAC)、奇瑞T28项目的日常发版工作。

【绝对禁止】
- 严禁捏造、虚构任何数据（MR链接、提交人、构建状态、记录等）。
- 如果没有调用工具获取到真实数据，只能回答"未查询到数据"，不得编造任何内容。
- 所有数据必须来自工具调用结果，不得凭记忆或推断给出具体数值。

【回答规则】
1. 必须用中文回答。
2. 只回答专业、简洁、有用的内容，不啰嗦。
3. 若工具返回空列表，直接告知用户"暂无满足条件的数据"。

【项目信息】
- 北汽:    Jenkins Job = MCU-BAIC-N53TB-Daily
- 上汽EP2: Jenkins Job = MCU-SAIC-EP2-Daily
- 广丰GAC: Jenkins Job = MCU-GAC-Daily
- 奇瑞T28: Jenkins Job = MCU-T28-Daily

【核心任务流程】
- 查询某项目待合入MR：调用 get_pending_mrs(project_name=<项目名>)，从返回结果中提取 MR 链接和提交人，不输出其他字段。

【工具调用示例】
用户: 帮我查一下北汽的待合入MR
→ 调用: get_pending_mrs(project_name="北汽")

用户: 上汽EP2有哪些待合入的MR
→ 调用: get_pending_mrs(project_name="上汽")

用户: 这个MR能合并吗 https://gitlab.example.com/group/proj/-/merge_requests/42
→ 调用: gitlab_check_mr_mergeable(project_id="group/proj", mr_iid=42)

用户: 触发北汽的Jenkins构建
→ 调用: jenkins_trigger_build(job_name="MCU-BAIC-N53TB-Daily")
"""
    ):
        self.system_prompt = system_prompt
        self.history: list[dict] = []
        self.summary: str = ""

    # ── 公开接口 ──────────────────────────────────────────────────

    def chat(self, user_input: str) -> str:
        """发送一条消息，自动处理 Tool Call 循环，返回最终 AI 回复文本。"""
        self.history.append({"role": "user", "content": user_input})
        messages = self._build_messages()

        # ── Agentic Tool Call 循环 ──────────────────────────────
        while True:
            msg = _llm_chat(messages, tools=TOOLS)

            if not msg.get("tool_calls"):
                reply = msg["content"]
                break

            # 有工具调用：执行 → 结果注入 → 继续循环
            # 使用后端原生格式的 assistant 消息，确保 DeepSeek 能正确解析
            messages.append(msg["_history_msg"])
            for tc, call_id in zip(msg["tool_calls"], msg["_tool_call_ids"]):
                fn_name = tc["function"]["name"]
                fn_args = tc["function"].get("arguments", {})
                if SHOW_THINKING:
                    print(f"  [Tool] 调用 {fn_name}({fn_args})")
                result = _dispatch_tool(fn_name, fn_args)
                if SHOW_THINKING:
                    preview = result[:200] + "…" if len(result) > 200 else result
                    print(f"  [Tool] 结果 → {preview}")
                tool_msg = {"role": "tool", "content": result}
                if call_id:
                    tool_msg["tool_call_id"] = call_id  # DeepSeek 要求
                messages.append(tool_msg)
        # ────────────────────────────────────────────────────────

        self.history.append({"role": "assistant", "content": reply})

        if self._should_summarize():
            self._summarize_history()

        return reply

    def reset(self):
        """清空所有记忆，开始全新对话。"""
        self.history = []
        self.summary = ""

    @property
    def round_count(self) -> int:
        return len(self.history) // 2

    # ── 内部方法 ──────────────────────────────────────────────────

    def _build_messages(self) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        if self.summary:
            messages.append({
                "role": "system",
                "content": f"以下是之前对话的摘要，供你参考：\n{self.summary}",
            })
        messages.extend(self.history)
        return messages

    def _should_summarize(self) -> bool:
        return self.round_count >= SUMMARY_THRESHOLD_ROUNDS

    def _summarize_history(self):
        keep_msgs = KEEP_RECENT_ROUNDS * 2
        to_summarize = self.history[:-keep_msgs]
        recent = self.history[-keep_msgs:]

        if not to_summarize:
            return

        dialogue_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in to_summarize
        )
        prompt = (
            "请将以下对话历史用简洁的中文总结成一段话，"
            "保留关键信息、用户意图和重要结论，不超过 300 字：\n\n"
            + dialogue_text
        )
        resp_text = _llm_simple([{"role": "user", "content": prompt}])

        self.summary = f"{self.summary}\n{resp_text}" if self.summary else resp_text
        self.history = recent
        if SHOW_THINKING:
            print(f"[AI] 🗜️  已压缩历史记忆（保留最近 {KEEP_RECENT_ROUNDS} 轮）")


# ── 命令行交互入口 ────────────────────────────────────────────────

def main():
    print(f"集成虾之合并发版虾, 助手已启动（模型: {MODEL}）")
    print("输入 'quit' 退出，输入 'reset' 清空记忆，输入 'info' 查看状态\n")

    ai = AI()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("再见！")
            break

        if user_input.lower() == "reset":
            ai.reset()
            print("[已清空所有记忆，开始新对话]\n")
            continue

        if user_input.lower() == "info":
            summary_preview = (ai.summary[:80] + "…") if len(ai.summary) > 80 else (ai.summary or "无")
            print(f"[当前轮数: {ai.round_count} | 历史条数: {len(ai.history)} | 摘要: {summary_preview}]\n")
            continue

        reply = ai.chat(user_input)
        print(f"AI: {reply}\n")


if __name__ == "__main__":
    main()
