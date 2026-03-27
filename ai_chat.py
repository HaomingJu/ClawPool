#!/usr/bin/env python3
"""
AI 对话类 — 基于 Ollama + qwen2.5:7b
支持多轮上下文记忆，并在消息累积过多时自动总结历史，防止 context 爆炸。
集成 JenkinsOps / GitlabOps 作为 Function Calling 工具。

依赖安装：
    pip install ollama requests

环境变量：
    JENKINS_URL   Jenkins 服务地址（默认 http://localhost:8080）
    JENKINS_USER  Jenkins 用户名（默认 admin）
    JENKINS_TOKEN Jenkins API Token（必填）
    GITLAB_URL    GitLab 服务地址（默认 https://gitlab.com）
    GITLAB_TOKEN  GitLab Access Token（必填）

使用示例：
    ai = AI()
    print(ai.chat("帮我查一下 backend 这个 Jenkins Job 的最新构建状态"))
    print(ai.chat("触发 main 分支的 GitLab Pipeline，项目是 mygroup/myrepo"))
"""

import os
import json
import ollama

from jenkins_ops import JenkinsOps
from gitlab_ops import GitlabOps
from feishu_bitable_ops import FeishuBitableOps
from tools_definition import TOOLS

# ── 配置 ──────────────────────────────────────────────────────────
MODEL = "qwen2.5:7b"

SUMMARY_THRESHOLD_ROUNDS = 10
KEEP_RECENT_ROUNDS = 3

# 是否显示思考过程（Tool 调用日志）：export SHOW_THINKING=1 开启
SHOW_THINKING = os.environ.get("SHOW_THINKING", "0") == "1"
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
            ), ensure_ascii=False)

        return f"[未知工具: {name}]"

    except Exception as e:
        return f"[工具调用失败] {name}: {e}"


# ─────────────────────────────────────────────────────────────────


class AI:
    """
    多轮对话 AI，内置上下文记忆与自动摘要压缩。
    通过 Ollama Function Calling 集成 Jenkins / GitLab 工具。

    消息结构：
        [system] [summary(可选)] [近期对话...] [当前 user]

    当历史超过 SUMMARY_THRESHOLD_ROUNDS 轮时，将旧消息压缩为一段摘要，
    保留最近 KEEP_RECENT_ROUNDS 轮保持连贯性，避免 context 过长。
    """

    def __init__(
        self,
        model: str = MODEL,
        system_prompt: str = """
        你是一个专业的AI助手
        你的任务是:
            1. 数据源可以通过接口访问飞书表格
            2. 帮助用户通过gitlab REST API操作gitlab, 代码合并等等.
            3. 帮助用户通过jenkins REST API操作jenkins, 任务触发/查询等等

        请遵循一下规则:
            1. 你必须用中文回答问题。
            2. 你只负责北汽、上汽(又称上汽EP2)、广丰(又称广丰GAC或者GAC)、奇瑞T28项目 的日常发版工作
            3. 只回答专业、简洁、有用的内容
            4. 回答风格：严谨、直接、不啰嗦
        项目相关信息:
            - 北汽项目:
                - Jenkins Job: MCU-BAIC-N53TB-Daily  (后续的触发Job,已经在jenkins上配置好)
                - 飞书表格: https://navinfo.feishu.cn/base/Ft2ibanVKaEeMjsW2aTcr8eynvd?table=tblTsX1YCNXfFgTP&view=vew3bze81M
                    - bitable_app_token: Ft2ibanVKaEeMjsW2aTcr8eynvd
                    - view_id: vew3bze81M
            - 上汽EP2项目:
                - Jenkins Job: MCU-SAIC-EP2-Daily (后续的触发Job,已经在jenkins上配置好)
                - 飞书表格: https://navinfo.feishu.cn/base/Ft2ibanVKaEeMjsW2aTcr8eynvd?table=tblTsX1YCNXfFgTP&view=vewVL8akAQ
                    - bitable_app_token: Ft2ibanVKaEeMjsW2aTcr8eynvd
                    - view_id: vewVL8akAQ
            - 广丰GAC项目:
                - Jenkins Job: MCU-GAC-Daily (后续的触发Job,已经在jenkins上配置好)
                - 飞书表格: https://navinfo.feishu.cn/base/Ft2ibanVKaEeMjsW2aTcr8eynvd?table=tblTsX1YCNXfFgTP&view=vewddvPkuM
                    - bitable_app_token: Ft2ibanVKaEeMjsW2aTcr8eynvd
                    - view_id: vewddvPkuM
            - 奇瑞T28项目:
                - Jenkins Job: MCU-T28-Daily (后续的触发Job,已经在jenkins上配置好)
                - 飞书表格: https://navinfo.feishu.cn/base/UzOobqjfDaXOvPsWYRMc1ggSnrf?table=tblRAa8RNhrPGVX8&view=vewddvPkuM
                    - bitable_app_token: UzOobqjfDaXOvPsWYRMc1ggSnrf
                    - view_id: vewddvPkuM
        """
    ):
        self.model = model
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
            response = ollama.chat(model=self.model, messages=messages, tools=TOOLS)
            msg = response["message"]

            if not msg.get("tool_calls"):
                # 无工具调用，直接取回复
                reply = msg["content"]
                break

            # 有工具调用：执行 → 结果注入 → 继续循环
            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": msg["tool_calls"]})
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"].get("arguments", {})
                if SHOW_THINKING:
                    print(f"  [Tool] 调用 {fn_name}({fn_args})")
                result = _dispatch_tool(fn_name, fn_args)
                if SHOW_THINKING:
                    preview = result[:200] + "…" if len(result) > 200 else result
                    print(f"  [Tool] 结果 → {preview}")
                messages.append({"role": "tool", "content": result})
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
        resp = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        new_summary_piece = resp["message"]["content"].strip()

        self.summary = f"{self.summary}\n{new_summary_piece}" if self.summary else new_summary_piece
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
