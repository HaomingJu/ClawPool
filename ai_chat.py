#!/usr/bin/env python3
"""
AI 对话类 — 基于 Ollama + qwen2.5:7b
支持多轮上下文记忆，并在消息累积过多时自动总结历史，防止 context 爆炸。

依赖安装：
    pip install ollama

使用示例：
    ai = AI()
    print(ai.chat("你好"))
    print(ai.chat("帮我写一首关于秋天的诗"))
"""

import ollama

# ── 配置 ──────────────────────────────────────────────────────────
MODEL = "qwen2.5:7b"

# 触发历史摘要的对话轮数（每轮含 user + assistant 共 2 条消息）
SUMMARY_THRESHOLD_ROUNDS = 10   # 超过 10 轮时压缩一次

# 压缩后保留的最近轮数（不纳入摘要，保持对话连贯性）
KEEP_RECENT_ROUNDS = 3
# ─────────────────────────────────────────────────────────────────


class AI:
    """
    多轮对话 AI，内置上下文记忆与自动摘要压缩。

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
        """
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.history: list[dict] = []   # 仅存 user/assistant 消息
        self.summary: str = ""          # 历史摘要（压缩后的旧记忆）

    # ── 公开接口 ──────────────────────────────────────────────────

    def chat(self, user_input: str) -> str:
        """发送一条消息，返回 AI 回复文本。"""
        self.history.append({"role": "user", "content": user_input})

        messages = self._build_messages()
        response = ollama.chat(model=self.model, messages=messages)
        reply = response["message"]["content"]

        self.history.append({"role": "assistant", "content": reply})

        # 检查是否需要压缩历史
        if self._should_summarize():
            self._summarize_history()

        return reply

    def reset(self):
        """清空所有记忆，开始全新对话。"""
        self.history = []
        self.summary = ""

    @property
    def round_count(self) -> int:
        """当前已进行的对话轮数。"""
        return len(self.history) // 2

    # ── 内部方法 ──────────────────────────────────────────────────

    def _build_messages(self) -> list[dict]:
        """拼装本次请求的完整消息列表。"""
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
        """将旧历史压缩为摘要，只保留最近几轮原始消息。"""
        keep_msgs = KEEP_RECENT_ROUNDS * 2          # 保留的消息条数
        to_summarize = self.history[:-keep_msgs]    # 待压缩部分
        recent = self.history[-keep_msgs:]          # 保留部分

        if not to_summarize:
            return

        # 将旧对话拼成文本交给模型总结
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

        # 若已有旧摘要则合并
        if self.summary:
            self.summary = f"{self.summary}\n{new_summary_piece}"
        else:
            self.summary = new_summary_piece

        self.history = recent
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
