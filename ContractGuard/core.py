import asyncio
import time
import logging
from datetime import datetime

from telethon.tl.types import PeerUser, PeerChat, PeerChannel, Channel
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest, LeaveChannelRequest

from .. import loader, utils

from .texts import strings, EMOJIS
from .utils import generate_code, format_time, parse_duration_str
from .premium import premium_edit, premium_send
from .resolver import resolve_user, resolve_channel
from .database import save
from .monitor import monitor_loop
from .watcher import watcher

logger = logging.getLogger(__name__)

@loader.tds
class ContractGuardMod(loader.Module):
    strings = strings

    # Attach methods from other modules
    premium_edit = premium_edit
    premium_send = premium_send
    resolve_user = resolve_user
    resolve_channel = resolve_channel
    save = save
    monitor_loop = monitor_loop
    watcher = watcher

    def __init__(self):
        self.config = loader.ModuleConfig(
            "MY_CHANNEL", -1003959173495, "Your channel ID",
            "LOG_CHAT", -1003921154698, "Logs group",
            "CHECK_DELAY", 60, "Realtime check delay"
        )
        self._task = None
        self.auto_enabled = False
        self.auto_group = None
        self.waiting_users = {}
        self._cooldowns = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.contracts = self.db.get("ContractGuard", "contracts", {})
        self.auto_enabled = self.db.get("ContractGuard", "auto_enabled", False)
        self.auto_group = self.db.get("ContractGuard", "auto_group", None)
        self.waiting_users = self.db.get("ContractGuard", "waiting_users", {})
        self._task = asyncio.create_task(self.monitor_loop())

    # Helper methods
    def _is_pm(self, message):
        return isinstance(message.peer_id, PeerUser)

    def _is_group(self, message):
        if isinstance(message.peer_id, PeerChat):
            return True
        if isinstance(message.peer_id, PeerChannel):
            chat = getattr(message, "chat", None)
            if chat and isinstance(chat, Channel):
                return getattr(chat, "megagroup", False)
            return True
        return False

    # Utility wrappers
    def generate_code(self):
        return generate_code()

    def format_time(self, seconds):
        return format_time(seconds)

    def parse_duration_str(self, s):
        return parse_duration_str(s)

    # =============== COMMANDS ===============

    async def autocmd(self, message):
        """ .auto — status, .auto on/off, .auto @group """
        raw = utils.get_args_raw(message)
        if not raw:
            status = "ON" if self.auto_enabled else "OFF"
            return await self.premium_edit(message, f"📊 <b>AUTO STATUS</b>\n\n📁 <code>{self.auto_group}</code>\n\n✅ <b>{status}</b>")
        arg = raw.lower()
        if arg == "on":
            self.auto_enabled = True
            peer = message.peer_id
            if isinstance(peer, PeerChannel):
                self.auto_group = peer.channel_id
            elif isinstance(peer, PeerChat):
                self.auto_group = peer.chat_id
            self.save()
            return await self.premium_edit(message, f"✅ <b>Auto javob yoqildi</b>\n\n📁 <code>{self.auto_group}</code>")
        if arg == "off":
            self.auto_enabled = False
            self.save()
            return await self.premium_edit(message, "❌ <b>Auto javob o'chirildi</b>")
        entity = await self.resolve_channel(raw)
        if not entity:
            return await self.premium_edit(message, "⚠️ <b>Guruh yoki kanal topilmadi</b>")
        self.auto_group = entity.id
        self.save()
        await self.premium_edit(message, f"✅ <b>Auto group o'rnatildi</b>\n\n🆔 <code>{entity.id}</code>")

    async def contractcmd(self, message):
        """ .contract USER CHANNEL or reply + .contract CHANNEL """
        raw = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if reply:
            if not raw:
                return await self.premium_edit(message, "<code>.contract @channel</code>")
            user_entity = await reply.get_sender()
            channel_input = raw
        else:
            if not raw:
                return
            args = raw.split(maxsplit=1)
            if len(args) != 2:
                return
            user_input, channel_input = args
            user_entity = await self.resolve_user(user_input)
        if not user_entity:
            return await self.premium_edit(message, "⚠️ <b>User topilmadi</b>")
        channel_entity, joined = await self.resolve_channel(channel_input)
        if not channel_entity:
            return await self.premium_edit(message, "⚠️ <b>Kanal topilmadi</b>")
        if not joined:
            return await self.premium_edit(message, "⚠️ <b>Kanalga qo'shilishda xatolik.</b>")
        try:
            await self.client(GetParticipantRequest(
                channel=self.config["MY_CHANNEL"],
                participant=user_entity.id
            ))
        except UserNotParticipantError:
            return await self.premium_edit(message, "⚠️ <b>User sizning kanalingizda emas</b>")
        uid = str(user_entity.id)
        if uid in self.contracts:
            return await self.premium_edit(message, "⚠️ <b>Contract mavjud</b>")
        contract_code = self.generate_code()
        self.contracts[uid] = {
            "code": contract_code,
            "username": user_entity.username,
            "user_id": user_entity.id,
            "their_channel_id": channel_entity.id,
            "their_channel_text": channel_input,
            "created": int(time.time()),
            "active": True
        }
        self.save()
        created_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        log_text = (
            "📦 <b>YANGI SHARTNOMA</b>\n\n"
            f"👤 <b>User:</b>\n@{user_entity.username}\n\n"
            f"📁 <b>Kanal:</b>\n{channel_input}\n\n"
            f"🕓 <b>Tuzilgan vaqt:</b>\n<code>{created_time}</code>\n\n"
            f"🔐 <b>Shartnoma kodi:</b>\n<code>{contract_code}</code>\n\n"
            "✅ <b>Monitoring boshlandi</b>"
        )
        await self.premium_send(self.config["LOG_CHAT"], log_text)
        await self.premium_edit(message, f"✅ <b>SHARTNOMA TUZILDI</b>\n\n🔐 <code>{contract_code}</code>")

    async def fixcmd(self, message):
        """ .fix CODE """
        code = utils.get_args_raw(message)
        if not code:
            return
        found = None
        for uid, data in self.contracts.items():
            if data["code"] == code:
                found = data
                break
        if not found:
            return await self.premium_edit(message, "⚠️ <b>SHARTNOMA TOPILMADI</b>")
        deadline_text = ""
        fix_deadline = found.get("fix_deadline")
        if fix_deadline:
            remaining = fix_deadline - int(time.time())
            if remaining > 0:
                deadline_text = f"\n\n⚠️ <b>Diqqat: agar <code>{self.format_time(remaining)}</code> ichida kanalga qayta qo'shilmasangiz, shartnoma bekor qilinadi.</b>"
        try:
            await self.premium_send(
                found["user_id"],
                "⚠️ <b>Siz @djavamee kanalidan chiqib ketgansiz.</b>\n\n📦 <b>Agar bu tasodifiy bo'lsa, kanalga qayta qo'shiling.</b>" + deadline_text
            )
        except Exception:
            return await self.premium_edit(message, "⚠️ <b>Userga yozib bo'lmadi</b>")
        await self.premium_edit(message, "✅ <b>Xabar yuborildi</b>")

    async def fixsetcmd(self, message):
        """ .fixset MUDDAT — 1d / 2h / 30m / 60s """
        time_str = utils.get_args_raw(message).strip()
        if not time_str:
            return await self.premium_edit(message, "⚠️ <b>Format:</b>\n<code>.fixset MUDDAT</code>\n\n📦 <b>Misol:</b>\n<code>.fixset 1d</code>\n<code>.fixset 12h</code>\n<code>.fixset 30m</code>")
        seconds = self.parse_duration_str(time_str)
        if not seconds or seconds <= 0:
            return await self.premium_edit(message, "⚠️ <b>Noto'g'ri format.</b>\n\n<code>1d</code>, <code>2h</code>, <code>30m</code>, <code>60s</code>")
        deadline = int(time.time()) + seconds
        deadline_dt = datetime.fromtimestamp(deadline).strftime("%d.%m.%Y %H:%M")
        broken_list = [(uid, data) for uid, data in self.contracts.items() if not data.get("active", True)]
        if not broken_list:
            return await self.premium_edit(message, "✅ <b>BROKEN shartnomalar yo'q</b>")
        notified = 0
        for uid, data in broken_list:
            data["fix_deadline"] = deadline
            try:
                await self.premium_send(
                    data["user_id"],
                    f"⚠️ <b>Siz @djavamee kanalidan chiqib ketgansiz.</b>\n\n"
                    f"📦 <b>Agar tasodifiy bo'lsa, kanalga qayta qo'shiling.</b>\n\n"
                    f"⏳ <b>Berilgan muddat:</b> <code>{time_str}</code>\n"
                    f"🕓 <b>Tugash vaqti:</b> <code>{deadline_dt}</code>\n\n"
                    f"⚠️ <b>Agar shu muddat ichida kanalga qayta qo'shilmasangiz, shartnoma bekor qilinadi.</b>"
                )
                notified += 1
            except Exception:
                pass
        self.save()
        await self.premium_edit(message, f"✅ <b>Muddat o'rnatildi</b>\n\n👥 <b>Ogohlantirish yuborildi:</b> <code>{notified}/{len(broken_list)}</code>\n\n⏳ <b>Muddat:</b> <code>{time_str}</code>\n\n🕓 <b>Tugash:</b> <code>{deadline_dt}</code>")

    async def contractscmd(self, message):
        """ .contracts """
        if not self.contracts:
            return await self.premium_edit(message, "⚠️ <b>Contractlar yo'q</b>")
        text = "📦 <b>SHARTNOMALAR</b>\n\n"
        for uid, data in self.contracts.items():
            status = "ACTIVE" if data["active"] else "BROKEN"
            duration = int(time.time()) - data["created"]
            text += f"📊 <b>{status}</b>\n\n👤 @{data['username']}\n\n🔐 <code>{data['code']}</code>\n\n📁 {data['their_channel_text']}\n\n⏳ <code>{self.format_time(duration)}</code>\n\n"
        await self.premium_edit(message, text)

    async def infcrcmd(self, message):
        """ .infcr (reply or code) """
        reply = await message.get_reply_message()
        code = utils.get_args_raw(message)
        found = None
        if reply:
            sender = await reply.get_sender()
            if not sender:
                return await self.premium_edit(message, "⚠️ <b>Foydaluvchi topilmadi</b>")
            uid = str(sender.id)
            if uid in self.contracts:
                found = self.contracts[uid]
            if not found:
                username = f"@{sender.username}" if sender.username else str(sender.id)
                return await self.premium_edit(message, f"📦 <b>SHARTNOMA TEKSHIRUVI</b>\n\n👤 <b>Foydaluvchi:</b>\n{username}\n\n🆔 <b>User ID:</b>\n<code>{sender.id}</code>\n\n❌ <b>Shartnoma mavjud emas</b>")
        else:
            if not code:
                return
            for uid, data in self.contracts.items():
                if data["code"] == code:
                    found = data
                    break
            if not found:
                return await self.premium_edit(message, "⚠️ <b>SHARTNOMA TOPILMADI</b>")
        duration = int(time.time()) - found["created"]
        created_time = datetime.fromtimestamp(found["created"]).strftime("%d.%m.%Y %H:%M")
        is_active = found["active"]
        status_icon = "✅" if is_active else "❌"
        status_text = "ACTIVE" if is_active else "BROKEN"
        text = (
            "📦 <b>SHARTNOMA INFO</b>\n\n"
            f"👤 <b>Username:</b>\n@{found['username']}\n\n"
            f"🆔 <b>User ID:</b>\n<code>{found['user_id']}</code>\n\n"
            f"📁 <b>Kanal:</b>\n{found['their_channel_text']}\n\n"
            f"🔐 <b>Shifr:</b>\n<code>{found['code']}</code>\n\n"
            f"🕓 <b>Tuzilgan:</b>\n<code>{created_time}</code>\n\n"
            f"⏳ <b>Davomiyligi:</b>\n<code>{self.format_time(duration)}</code>\n\n"
            f"📊 <b>Status:</b>\n{status_icon} <code>{status_text}</code>"
        )
        await self.premium_edit(message, text)
        await asyncio.sleep(120)
        try:
            await message.delete()
        except Exception:
            pass

    async def checkercmd(self, message):
        """ .checkcr (reply) """
        reply = await message.get_reply_message()
        if not reply:
            return await self.premium_edit(message, "⚠️ <b>Reply qiling</b>")
        sender = await reply.get_sender()
        if not sender:
            return await self.premium_edit(message, "⚠️ <b>Foydalanuvchi topilmadi</b>")
        uid = str(sender.id)
        username = f"@{sender.username}" if sender.username else str(sender.id)
        if uid not in self.contracts:
            return await self.premium_edit(message, f"📦 {username} ❌ <b>Shartnoma yo'q</b>")
        data = self.contracts[uid]
        is_active = data["active"]
        status_icon = "✅" if is_active else "⚠️"
        duration = int(time.time()) - data["created"]
        channel_raw = str(data["their_channel_text"])
        if len(channel_raw) > 20:
            channel_raw = channel_raw[:17] + "..."
        text = f"📦 {username}\n📊 {status_icon} {'ACTIVE' if is_active else 'BROKEN'}\n📁 {channel_raw}\n🔐 <code>{data['code']}</code>\n⏳ <code>{self.format_time(duration)}</code>"
        await self.premium_edit(message, text)
        await asyncio.sleep(60)
        try:
            await message.delete()
        except Exception:
            pass

    async def delcontractcmd(self, message):
        """ .delcontract CODE """
        code = utils.get_args_raw(message)
        if not code:
            return
        found_uid = None
        for uid, data in self.contracts.items():
            if data["code"] == code:
                found_uid = uid
                break
        if not found_uid:
            return await self.premium_edit(message, "⚠️ <b>SHARTNOMA TOPILMADI</b>")
        contract = self.contracts[found_uid]
        try:
            await self.client(LeaveChannelRequest(contract["their_channel_id"]))
        except Exception:
            pass
        del self.contracts[found_uid]
        self.save()
        await self.premium_send(self.config["LOG_CHAT"], f"❌ <b>SHARTNOMA O'CHIRILDI</b>\n\n🔐 <code>{code}</code>")
        await self.premium_edit(message, "✅ <b>Contract o'chirildi</b>")
