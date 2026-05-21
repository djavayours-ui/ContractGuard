import time
import logging
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest
from datetime import datetime

from .utils import extract_link
from .premium import premium_send

logger = logging.getLogger(__name__)

async def watcher(self, message):
    try:
        if message.out or not self.auto_enabled or not self.auto_group:
            return

        is_pm = isinstance(message.peer_id, PeerUser)
        is_group = isinstance(message.peer_id, (PeerChat, PeerChannel))
        if not (is_pm or is_group):
            return

        sender = await message.get_sender()
        if not sender or getattr(sender, "bot", False):
            return

        uid = str(sender.id)

        # Waiting user (link expected)
        if uid in self.waiting_users:
            link = extract_link(message.raw_text or "")
            if not link:
                return

            channel_entity, joined = await self.resolve_channel(link)
            if not channel_entity:
                err = "⚠️ <b>Havola topilmadi yoki ochib bo'lmadi</b>"
                target = sender.id if is_pm else message.chat_id
                await self.premium_send(target, err, reply_to=message.id)
                return

            if not joined:
                err = "⚠️ <b>Kanalingizga qo'shilishda xatolik.</b>"
                target = sender.id if is_pm else message.chat_id
                await self.premium_send(target, err, reply_to=message.id)
                return

            contract_code = self.generate_code()
            self.contracts[uid] = {
                "code": contract_code,
                "username": sender.username,
                "user_id": sender.id,
                "their_channel_id": channel_entity.id,
                "their_channel_text": link,
                "created": int(time.time()),
                "active": True
            }
            created_time = datetime.now().strftime("%d.%m.%Y %H:%M")
            log_text = (
                "📦 <b>YANGI SHARTNOMA</b>\n\n"
                f"👤 <b>User:</b>\n@{sender.username}\n\n"
                f"📁 <b>Kanal:</b>\n{link}\n\n"
                f"🕓 <b>Tuzilgan vaqt:</b>\n<code>{created_time}</code>\n\n"
                f"🔐 <b>Shartnoma kodi:</b>\n<code>{contract_code}</code>\n\n"
                "✅ <b>Monitoring boshlandi</b>"
            )
            await self.premium_send(self.config["LOG_CHAT"], log_text)
            success_text = f"✅ <b>SHARTNOMA TUZILDI</b>\n\n🔐 <code>{contract_code}</code>"
            target = sender.id if is_pm else message.chat_id
            await self.premium_send(target, success_text, reply_to=message.id)
            del self.waiting_users[uid]
            self.save()
            return

        # Only groups for new contract requests
        if not is_group:
            return

        # Check if it's the configured auto group
        peer = message.peer_id
        if isinstance(peer, PeerChannel):
            chat_id = peer.channel_id
        elif isinstance(peer, PeerChat):
            chat_id = peer.chat_id
        else:
            return
        if chat_id != self.auto_group:
            return

        if not message.is_reply:
            return
        reply = await message.get_reply_message()
        if not reply:
            return
        me = await self.client.get_me()
        if reply.sender_id != me.id:
            return

        # Duplicate active contract
        if uid in self.contracts:
            data = self.contracts[uid]
            if data.get("active"):
                now = time.time()
                last = self._cooldowns.get(uid, 0)
                if now - last < 30:
                    return
                self._cooldowns[uid] = now
                duration = int(time.time()) - data["created"]
                channel_raw = data["their_channel_text"]
                if len(channel_raw) > 20:
                    channel_raw = channel_raw[:17] + "..."
                username_text = f"@{sender.username}" if sender.username else str(sender.id)
                txt = (
                    f"📦 {username_text}\n"
                    f"📊 ✅ ACTIVE\n"
                    f"📁 {channel_raw}\n"
                    f"🔐 <code>{data['code']}</code>\n"
                    f"⏳ <code>{self.format_time(duration)}</code>"
                )
                await self.premium_send(message.chat_id, txt, reply_to=message.id)
                return
            else:
                del self.contracts[uid]
                self.save()

        # Cooldown
        now = time.time()
        if now - self._cooldowns.get(uid, 0) < 5:
            return

        # Check user in MY_CHANNEL
        try:
            await self.client(GetParticipantRequest(
                channel=self.config["MY_CHANNEL"],
                participant=sender.id
            ))
        except UserNotParticipantError:
            self._cooldowns[uid] = now
            await self.premium_send(
                message.chat_id,
                "⚠️ <b>Сиз ҳали @djavamee каналига аъзо бўлмадингиз, взаимная подписка учун аввало каналга қўшилинг.</b>",
                reply_to=message.id
            )
            return

        # Add to waiting
        self._cooldowns[uid] = now
        self.waiting_users[uid] = {"group": message.chat_id, "reply_msg": message.id}
        self.save()
        await self.premium_send(
            message.chat_id,
            "✅ <b>Сиз каналга аъзо бўлдингиз, илтимос каналини ёки гуруҳингиз хаволасини менга реплй тарзда юборинг.</b>",
            reply_to=message.id
        )
    except Exception as e:
        logger.exception(e)
