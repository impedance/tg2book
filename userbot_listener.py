import asyncio
import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from telethon import TelegramClient as TelethonClient

import channel_registry
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

    def parse_channel_post(self, event) -> tuple[Optional[IngestedChannelPost], str]:
        message = getattr(event, "message", event)
        if getattr(event, "is_private", False) or getattr(event, "is_group", False):
            return None, "not_a_channel_post"
        if getattr(event, "is_channel", None) is False:
            return None, "not_a_channel_post"

        text = (
            getattr(message, "message", None)
            or getattr(message, "raw_text", None)
            or getattr(message, "text", None)
            or ""
        )
        if not text or not text.strip():
            return None, "empty_or_no_text"

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
            return None, "unresolved_source_id"

        message_id = getattr(message, "id", None)
        if username and message_id is not None:
            post_link = f"https://t.me/{username}/{message_id}"
        else:
            post_link = ""

        post = IngestedChannelPost(
            text_content=text,
            source_name=chat_title,
            source_identifier=source_identifier,
            post_link=post_link,
            message_id=message_id,
        )
        return post, ""

    async def handle_new_message(self, event) -> bool:
        message = getattr(event, "message", event)
        chat_id = getattr(event, "chat_id", None) or getattr(message, "chat_id", None)
        message_id = getattr(message, "id", None)

        # DEBUG Trace for ALL events
        logger.debug(
            "USERBOT_EVENT_RECEIVE chat_id=%s message_id=%s class=%s",
            chat_id,
            message_id,
            event.__class__.__name__,
        )

        post, skip_reason = self.parse_channel_post(event)
        if not post:
            if skip_reason != "not_a_channel_post":
                logger.info(
                    "USERBOT_SKIP reason=%s chat_id=%s message_id=%s",
                    skip_reason,
                    chat_id,
                    message_id,
                )
            return False

        logger.info(
            "HANDOFF_TO_BOT source=%s message_id=%s title=%s",
            post.source_identifier,
            post.message_id,
            post.source_name,
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
            # Update last_message_id in registry
            try:
                db_path = getattr(self.converter, "_channel_db_path", lambda: channel_registry.DEFAULT_DB_PATH)()
                channel_registry.update_last_message_id(post.source_identifier, post.message_id, db_path)
            except Exception as e:
                logger.error("Failed to update last_message_id: %s", e)
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


async def run_userbot_listener(
    client: Optional["TelethonClient"] = None,
    converter: Optional[TelegramToEpub] = None
):
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

    if converter is None:
        listener = _build_listener_from_env()
    else:
        # If converter supplied externally, build listener with it
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        admin_id_raw = os.getenv("ADMIN_ID", "").strip()
        if not bot_token or not admin_id_raw:
             raise RuntimeError("Для summary нужны TELEGRAM_BOT_TOKEN и ADMIN_ID.")
        summary_target = BotSummaryTarget(bot_token=bot_token, chat_id=int(admin_id_raw))
        listener = UserbotListener(converter=converter, summary_target=summary_target)

    if client is None:
        client = TelegramClient(session_name, api_id, api_hash)

    @client.on(events.NewMessage())
    async def on_new_message(event):
        try:
            await listener.handle_new_message(event)
        except Exception as exc:
            logger.exception("USERBOT_HANDLER_ERROR: %s", exc)

    async def log_dialogs():
        """Log channel member identities for startup check."""
        try:
            from telethon.tl.types import Channel
            logger.info("USERBOT_CHECK_DIALOGS: Loading monitored channels...")
            db_path = getattr(listener.converter, "_channel_db_path", lambda: channel_registry.DEFAULT_DB_PATH)()
            monitored = channel_registry.get_channels(db_path)
            
            logger.info("USERBOT_CHECK_DIALOGS: Monitored in registry: %s", monitored)
            
            async for dialog in client.iter_dialogs():
                if isinstance(dialog.entity, Channel):
                    title = dialog.name
                    username = getattr(dialog.entity, "username", None)
                    cid = dialog.id
                    if username and username.lower() in monitored or str(cid) in monitored:
                         logger.info("USERBOT_CHECK_DIALOGS: MATCH title='%s' id=%s username=%s", title, cid, username)
                    else:
                         logger.debug("USERBOT_CHECK_DIALOGS: OTHER title='%s' id=%s username=%s", title, cid, username)
        except Exception as e:
            logger.error("USERBOT_CHECK_DIALOGS_ERROR: %s", e)

    async def periodic_health_check_loop():
        """Polling loop to recover missed messages from monitored channels."""
        await asyncio.sleep(60)  # Initial wait
        while True:
            try:
                db_path = getattr(listener.converter, "_channel_db_path", lambda: channel_registry.DEFAULT_DB_PATH)()
                channels = channel_registry.get_channels_with_details(db_path)
                logger.info("HEALTH_CHECK_START count=%d", len(channels))
                
                for entry in channels:
                    identifier = entry["identifier"]
                    last_id = entry["last_message_id"] or 0
                    
                    try:
                        # Fetch up to 5 latest messages to catch gaps
                        async for message in client.iter_messages(identifier, limit=5):
                            if message.id > last_id:
                                logger.info("POLL_RECOVERY_FOUND identifier=%s msg_id=%s", identifier, message.id)
                                # Simulation of event for handle_new_message
                                await listener.handle_new_message(message)
                    except Exception as e:
                        logger.error("HEALTH_CHECK_CHANNEL_ERROR identifier=%s: %s", identifier, e)
                
                logger.info("HEALTH_CHECK_COMPLETED")
            except Exception as e:
                logger.exception("HEALTH_CHECK_LOOP_ERROR: %s", e)
            
            await asyncio.sleep(600)  # 10 minutes

    logger.info("USERBOT_START session=%s", session_name)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            # Не вызываем start() чтобы не триггернуть send_code_request
            # (это инвалидирует код отправленный через /reauth)
            raise EOFError("Userbot session is not authorized")
        logger.info("USERBOT_READY")
        await log_dialogs()
        asyncio.create_task(periodic_health_check_loop())
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


def main():
    try:
        asyncio.run(run_userbot_listener())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
