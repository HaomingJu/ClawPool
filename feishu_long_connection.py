#!/usr/bin/env python3
"""
飞书长连接（WebSocket）聊天机器人脚本
使用官方 lark-oapi SDK，通过长连接实时接收消息并自动回复关键词。

依赖安装：
    pip install lark-oapi

环境变量：
    APP_ID      飞书应用的 App ID
    APP_SECRET  飞书应用的 App Secret

关键词回复规则在 REPLY_RULES 字典中配置。
"""

import json
import logging
import os

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------
# 关键词回复规则：key 为收到的消息（忽略大小写、去除首尾空格）
#                value 为机器人的回复内容
# ----------------------------------------------------------------
REPLY_RULES: dict[str, str] = {
    "hello": "world",
    "你好": "你好呀！有什么可以帮你的？",
    "帮助": "支持的指令：hello、你好、帮助、ping",
    "ping": "pong",
    "评价一下黄亮亮": "亮亮是个非常帅的同学，喜欢打游戏",
    "评价一下尚佳乐": "佳乐是一个非常棒的同学，工作认真能力强",

}

DEFAULT_REPLY = "暂时不理解你的意思，输入「帮助」查看支持的指令。"


def get_credentials() -> tuple[str, str]:
    app_id = os.environ.get("APP_ID")
    app_secret = os.environ.get("APP_SECRET")
    if not app_id or not app_secret:
        raise EnvironmentError("请设置环境变量 APP_ID 和 APP_SECRET")
    return app_id, app_secret


def get_reply(text: str) -> str:
    """根据关键词匹配返回回复内容"""
    normalized = text.strip().lower()
    for keyword, reply in REPLY_RULES.items():
        if normalized == keyword.lower():
            return reply
    return DEFAULT_REPLY


def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    """收到消息事件的回调处理"""
    message = data.event.message
    message_id = message.message_id
    msg_type = message.message_type
    sender_id = data.event.sender.sender_id.open_id

    # 只处理纯文本消息
    if msg_type != "text":
        logger.info("⏭️  忽略非文本消息类型: %s", msg_type)
        return

    try:
        text = json.loads(message.content).get("text", "").strip()
    except (json.JSONDecodeError, AttributeError):
        text = (message.content or "").strip()

    logger.info("💬 [%s] 说: %s", sender_id, text)

    reply_text = get_reply(text)

    # 构造回复请求
    app_id, app_secret = get_credentials()
    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    request = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(json.dumps({"text": reply_text}))
            .build()
        )
        .build()
    )

    resp = client.im.v1.message.reply(request)
    if not resp.success():
        logger.error("❌ 回复失败: code=%s msg=%s", resp.code, resp.msg)
    else:
        logger.info("✉️  已回复 [%s]: %s", sender_id, reply_text)


def main():
    app_id, app_secret = get_credentials()

    # 注册事件处理器
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
        .build()
    )

    # 建立长连接（SDK 自动管理 WebSocket 地址、鉴权、断线重连）
    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    logger.info("🚀 飞书长连接启动，等待消息...")
    ws_client.start()


if __name__ == "__main__":
    main()
