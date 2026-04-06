import asyncio
import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

from bot import TelegramToEpub


logger = logging.getLogger(__name__)


@dataclass
class IngestedChannelPost:
    text_content: str
    source_name: str
    source_identifier: str
    post_link: str
    message_id: Optional[int] = None


class SummaryMessageHandle:
    """A minimal message handle compatible with existing processing flow."""

    async def delete(self):
        return None


class BotSummaryTarget:
    """Summary target that sends status updates to a specific Telegram chat."""

    def __init__(self, bot_token: str, chat_id: int, bot_client=None):
        self.chat_id = chat_id
        if bot_client is not None:
            self.bot = bot_client
            return

        try:
            from telegram import Bot
        except Exception as exc:
            raise RuntimeError(
                "python-telegram-bot недоступен: не удалось создать summary target"
            ) from exc

        self.bot = Bot(token=bot_token)

    async def reply_text(self, text: str, **kwargs):
        await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)
        return SummaryMessageHandle()


class UserbotListener:
    """Listens to channel posts and routes eligible updates into shared pipeline."""

    def __init__(self, converter: TelegramToEpub, summary_target: BotSummaryTarget):
        self.converter = converter
        self.summary_target = summary_target

    def parse_channel_post(self, event) -> Optional[IngestedChannelPost]:
        message = getattr(event, "message", event)
        if getattr(event, "is_private", False) or getattr(event, "is_group", False):
            return None
        if getattr(event, "is_channel", None) is False:
            return None

        text = (
            getattr(message, "message", None)
            or getattr(message, "raw_text", None)
            or getattr(message, "text", None)
            or ""
        )
        if not text or not text.strip():
            return None

        chat = getattr(event, "chat", None) or getattr(message, "chat", None)
        chat_title = getattr(chat, "title", None) or getattr(chat, "username", None) or "Channel"

        username = getattr(chat, "username", None)
        chat_id = getattr(event, "chat_id", None)
        if chat_id is None:
            chat_id = getattr(message, "chat_id", None)
        if chat_id is None:
            peer = getattr(message, "peer_id", None)
            chat_id = getattr(peer, "channel_id", None)

        if username:
            source_identifier = username
        elif chat_id is not None:
            source_identifier = str(chat_id)
        else:
            return None

        message_id = getattr(message, "id", None)
        if username and message_id is not None:
            post_link = f"https://t.me/{username}/{message_id}"
        else:
            post_link = ""

        return IngestedChannelPost(
            text_content=text,
            source_name=chat_title,
            source_identifier=source_identifier,
            post_link=post_link,
            message_id=message_id,
        )

    async def handle_new_message(self, event) -> bool:
        post = self.parse_channel_post(event)
        if not post:
            logger.info("USERBOT_SKIP reason=empty_or_unresolved_message")
            return False

        logger.info(
            "USERBOT_RECEIVED source=%s message_id=%s",
            post.source_identifier,
            post.message_id,
        )
        success = await self.converter.process_channel_post(
            text_content=post.text_content,
            source_name=post.source_name,
            source_identifier=post.source_identifier,
            summary_target=self.summary_target,
            post_link=post.post_link,
        )
        if success:
            logger.info(
                "USERBOT_PROCESSED source=%s message_id=%s",
                post.source_identifier,
                post.message_id,
            )
        else:
            logger.info(
                "USERBOT_FILTERED_OR_FAILED source=%s message_id=%s",
                post.source_identifier,
                post.message_id,
            )
        return success


def _build_listener_from_env() -> UserbotListener:
    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin_id_raw = os.getenv("ADMIN_ID", "").strip()

    if not api_id_raw or not api_hash:
        raise RuntimeError("Не заданы API_ID/API_HASH для userbot.")
    if not bot_token or not admin_id_raw:
        raise RuntimeError("Для summary нужны TELEGRAM_BOT_TOKEN и ADMIN_ID.")

    try:
        admin_id = int(admin_id_raw)
    except ValueError as exc:
        raise RuntimeError("ADMIN_ID должен быть числом.") from exc

    summary_target = BotSummaryTarget(bot_token=bot_token, chat_id=admin_id)
    return UserbotListener(converter=TelegramToEpub(), summary_target=summary_target)


async def run_userbot_listener():
    """Start Telethon userbot and route channel posts into shared processing seam."""
    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    session_name = os.getenv("USERBOT_SESSION", "tg2book_userbot").strip()

    if not api_id_raw or not api_hash:
        raise RuntimeError("Не заданы API_ID/API_HASH для userbot.")

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise RuntimeError("API_ID должен быть числом.") from exc

    try:
        from telethon import TelegramClient, events
    except Exception as exc:
        raise RuntimeError(
            "Telethon не установлен. Установите зависимости из requirements.txt."
        ) from exc

    listener = _build_listener_from_env()
    client = TelegramClient(session_name, api_id, api_hash)

    @client.on(events.NewMessage())
    async def on_new_message(event):
        try:
            await listener.handle_new_message(event)
        except Exception as exc:
            logger.exception("USERBOT_HANDLER_ERROR: %s", exc)

    logger.info("USERBOT_START session=%s", session_name)
    await client.start()
    logger.info("USERBOT_READY")
    await client.run_until_disconnected()


def main():
    asyncio.run(run_userbot_listener())


if __name__ == "__main__":
    main()
