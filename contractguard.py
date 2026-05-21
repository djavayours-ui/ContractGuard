# =========================================================
# meta developer: @djavame
# scope: hikka_only
# =========================================================

__version__ = (8, 0, 0)

import asyncio
import logging
import random
import re
import string
import time

from datetime import datetime

from hikkatl.types import Message

from telethon.errors import (
    UserNotParticipantError,
    UserAlreadyParticipantError
)

from telethon.tl.functions.channels import (
    GetParticipantRequest,
    LeaveChannelRequest,
    JoinChannelRequest
)

from telethon.tl.functions.messages import (
    ImportChatInviteRequest,
    CheckChatInviteRequest
)

from telethon.tl.types import (
    MessageEntityCustomEmoji,
    PeerUser,
    PeerChat,
    PeerChannel,
    Channel,
    Chat
)

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class ContractGuardMod(loader.Module):
    """
    Realtime Contract Guard
    """

    strings = {
        "name": "ContractGuard",

        "auto_on": "✅ <b>Auto javob yoqildi</b>",
        "auto_off": "❌ <b>Auto javob o'chirildi</b>",
        "contract_not_found": "⚠️ <b>SHARTNOMA TOPILMADI</b>",
        "user_not_found": "⚠️ <b>User topilmadi</b>",
        "channel_not_found": "⚠️ <b>Kanal topilmadi</b>",
    }

    strings_ru = {
        "auto_on": "✅ <b>Автоответ включен</b>",
    }

    def __init__(self):

        self.config = loader.ModuleConfig(

            loader.ConfigValue(
                "my_channel",
                -1003959173495,
                "Main channel ID",
                validator=loader.validators.TelegramID(),
            ),

            loader.ConfigValue(
                "log_chat",
                -1003921154698,
                "Logs group",
                validator=loader.validators.TelegramID(),
            ),

            loader.ConfigValue(
                "check_delay",
                60,
                "Realtime check delay",
                validator=loader.validators.Integer(
                    minimum=5
                ),
            ),
        )

        self._task = None

        self._cooldowns = {}

        self._entity_cache = {}

    async def client_ready(self):

        self._contracts = self.pointer(
            "contracts",
            {}
        )

        self._waiting_users = self.pointer(
            "waiting_users",
            {}
        )

        self._auto_enabled = self.get(
            "auto_enabled",
            False
        )

        self._auto_group = self.get(
            "auto_group",
            None
        )

        self._task = asyncio.create_task(
            self.monitor_loop()
        )

    # =====================================================
    # UTILS
    # =====================================================

    def generate_code(self) -> str:

        return "".join(

            random.choice(

                string.ascii_uppercase
                + string.digits

            ) for _ in range(10)
        )

    def utf16len(
        self,
        text: str
    ) -> int:

        return len(
            text.encode("utf-16-le")
        ) // 2

    def format_time(
        self,
        seconds: int
    ) -> str:

        days = seconds // 86400

        hours = (
            seconds % 86400
        ) // 3600

        minutes = (
            seconds % 3600
        ) // 60

        return (
            f"{days}d "
            f"{hours}h "
            f"{minutes}m"
        )

    # =====================================================
    # PREMIUM EMOJIS
    # =====================================================

    EMOJIS = {

        "CONTRACT":
            5258331647358540449,

        "CHANNEL":
            5257969839313526622,

        "USER":
            5257965810634202885,

        "CODE":
            5258476306152038031,

        "TIME":
            5258419835922030550,

        "SUCCESS":
            5260726538302660868,

        "DELETE":
            5258130763148172425,

        "ERROR":
            5260342697075416641,

        "ID":
            5258503720928288433,

        "DURATION":
            5260687119092817530,

        "STATUS":
            5359719332542718652,

        "WARNING":
            5260249440450520061,

        "RECYCLE":
            5260687681733533075
    }

    def _build_entities(
        self,
        text: str
    ):

        if text in self._entity_cache:
            return self._entity_cache[text]

        from telethon.extensions import html as tl_html

        mapping = {

            "📦":
                self.EMOJIS["CONTRACT"],

            "📁":
                self.EMOJIS["CHANNEL"],

            "👤":
                self.EMOJIS["USER"],

            "🔐":
                self.EMOJIS["CODE"],

            "🕓":
                self.EMOJIS["TIME"],

            "✅":
                self.EMOJIS["SUCCESS"],

            "❌":
                self.EMOJIS["DELETE"],

            "⚠️":
                self.EMOJIS["WARNING"],

            "🆔":
                self.EMOJIS["ID"],

            "⏳":
                self.EMOJIS["DURATION"],

            "📊":
                self.EMOJIS["STATUS"],

            "♻️":
                self.EMOJIS["RECYCLE"]
        }

        parsed_text, html_entities = tl_html.parse(text)

        emoji_entities = []

        for emoji, doc_id in mapping.items():

            start = 0

            while True:

                try:

                    pos = parsed_text.index(
                        emoji,
                        start
                    )

                except ValueError:
                    break

                offset = self.utf16len(
                    parsed_text[:pos]
                )

                length = self.utf16len(
                    emoji
                )

                emoji_entities.append(

                    MessageEntityCustomEmoji(

                        offset=offset,

                        length=length,

                        document_id=doc_id
                    )
                )

                start = pos + len(emoji)

        all_entities = list(
            html_entities
        ) + emoji_entities

        result = (
            parsed_text,
            all_entities
        )

        self._entity_cache[text] = result

        return result

    async def premium_send(
        self,
        chat,
        text: str,
        reply_to=None
    ):

        parsed_text, all_entities = (
            self._build_entities(text)
        )

        return await self._client.send_message(

            chat,

            parsed_text,

            formatting_entities=all_entities,

            reply_to=reply_to
            )
