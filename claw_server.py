#!/usr/bin/env python3
"""
飞书长连接（WebSocket）AI 聊天机器人
使用官方 lark-oapi SDK，通过长连接实时接收消息，接入 AI 对话能力。

依赖安装：
    pip install lark-oapi ollama requests cachetools

环境变量：
    APP_ID              飞书应用的 App ID
    APP_SECRET          飞书应用的 App Secret
    JENKINS_URL         Jenkins 服务地址
    JENKINS_USER        Jenkins 用户名
    JENKINS_TOKEN       Jenkins API Token
    GITLAB_URL          GitLab 服务地址
    GITLAB_TOKEN        GitLab Access Token
    SHOW_THINKING       设为 1 时在终端打印 Tool 调用日志（默认关闭）
    SESSION_TTL         用户会话超时秒数（默认 3600，即 1 小时无消息后自动释放）
    SESSION_MAX_USERS   最大同时在线用户数（默认 500，超出时淘汰最久未活跃的）

内置指令（优先于 AI 处理）：
    reset / 重置    清空当前用户的 AI 对话记忆
    info  / 状态    查看当前对话轮数与摘要
    ping            连通性测试
"""

import json
import logging
import os

import lark_oapi as lark
from cachetools import TTLCache
from lark_oapi.api.im.v1 import (
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from ai_chat import AI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── 内置指令（不过 AI，直接返回） ──────────────────────────────────
BUILTIN_COMMANDS: dict[str, str] = {
    "ping": "pong 🏓",
    "帮助": (
        "支持的指令：\n"
        "• reset / 重置 — 清空 AI 对话记忆\n"
        "• info  / 状态 — 查看对话状态\n"
        "• ping         — 连通性测试\n"
        "• 其他内容      — 直接与 AI 对话"
    ),
}

# ── 会话缓存（TTL + LRU 双重淘汰） ───────────────────────────────
# 用户超过 SESSION_TTL 秒无消息 → 自动释放 AI 实例
# 同时在线超过 SESSION_MAX_USERS → 淘汰最久未活跃的用户
_SESSION_TTL = int(os.environ.get("SESSION_TTL", 3600))
_SESSION_MAX = int(os.environ.get("SESSION_MAX_USERS", 500))

_user_ai: TTLCache = TTLCache(maxsize=_SESSION_MAX, ttl=_SESSION_TTL)


def _get_ai(open_id: str) -> AI:
    """获取或创建用户专属的 AI 实例（每次访问自动刷新 TTL）"""
    if open_id not in _user_ai:
        _user_ai[open_id] = AI()
        logger.info("🤖 为用户 [%s] 创建新的 AI 会话（当前活跃会话: %d/%d）",
                    open_id, len(_user_ai), _SESSION_MAX)
    return _user_ai[open_id]


def get_credentials() -> tuple[str, str]:
    app_id = os.environ.get("APP_ID")
    app_secret = os.environ.get("APP_SECRET")
    if not app_id or not app_secret:
        raise EnvironmentError("请设置环境变量 APP_ID 和 APP_SECRET")
    return app_id, app_secret


def _send_reply(message_id: str, text: str) -> None:
    """向飞书发送回复消息"""
    app_id, app_secret = get_credentials()
    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    request = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(json.dumps({"text": text}))
            .build()
        )
        .build()
    )

    resp = client.im.v1.message.reply(request)
    if not resp.success():
        logger.error("❌ 回复失败: code=%s msg=%s", resp.code, resp.msg)


def _handle_text(open_id: str, text: str) -> str:
    """
    处理用户消息，返回回复文本。
    优先级：内置指令 > reset/info 操作 > AI 对话
    """
    normalized = text.strip()
    lower = normalized.lower()

    # 内置快捷指令
    for cmd, reply in BUILTIN_COMMANDS.items():
        if lower == cmd.lower():
            return reply

    ai = _get_ai(open_id)

    # reset 指令
    if lower in ("reset", "重置"):
        ai.reset()
        return "✅ AI 对话记忆已清空，开始全新会话。"

    # info 指令
    if lower in ("info", "状态"):
        summary_preview = (
            (ai.summary[:60] + "…") if len(ai.summary) > 60 else (ai.summary or "无")
        )
        return (
            f"📊 对话状态\n"
            f"• 当前轮数：{ai.round_count}\n"
            f"• 历史条数：{len(ai.history)}\n"
            f"• 摘要：{summary_preview}\n"
            f"• 当前活跃会话：{len(_user_ai)}/{_SESSION_MAX}"
        )

    # 交给 AI 处理
    try:
        return ai.chat(normalized)
    except Exception as e:
        logger.error("AI 调用异常: %s", e, exc_info=True)
        return f"⚠️ AI 处理出错：{e}"


def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    """收到消息事件的回调处理"""
    message = data.event.message
    message_id = message.message_id
    msg_type = message.message_type
    open_id = data.event.sender.sender_id.open_id

    # 只处理纯文本消息
    if msg_type != "text":
        logger.info("⏭️  忽略非文本消息类型: %s", msg_type)
        return

    try:
        text = json.loads(message.content).get("text", "").strip()
    except (json.JSONDecodeError, AttributeError):
        text = (message.content or "").strip()

    if not text:
        return

    logger.info("💬 [%s] 说: %s", open_id, text)

    reply_text = _handle_text(open_id, text)

    _send_reply(message_id, reply_text)
    logger.info("✉️  已回复 [%s]: %s", open_id, reply_text[:80])


def main():
    app_id, app_secret = get_credentials()

    logger.info(
        "⚙️  会话配置 — TTL: %ds | 最大用户数: %d", _SESSION_TTL, _SESSION_MAX
    )

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
        .build()
    )

    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    logger.info("🚀 飞书 AI 助手长连接启动，等待消息...")
    ws_client.start()


if __name__ == "__main__":
    main()

