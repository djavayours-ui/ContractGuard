import asyncio
import time
import logging
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest, LeaveChannelRequest
from datetime import datetime

logger = logging.getLogger(__name__)

async def monitor_loop(self):
    while True:
        try:
            for uid, data in list(self.contracts.items()):
                if not data.get("active"):
                    continue
                try:
                    await self.client(GetParticipantRequest(
                        channel=self.config["MY_CHANNEL"],
                        participant=int(uid)
                    ))
                except UserNotParticipantError:
                    data["active"] = False
                    data["broken_at"] = int(time.time())
                    self.save()
                    duration = int(time.time()) - data["created"]
                    text = (
                        "⚠️ <b>SHARTNOMA BUZILDI</b>\n\n"
                        f"👤 <b>User:</b>\n@{data['username']}\n\n"
                        f"📁 <b>Kanal:</b>\n{data['their_channel_text']}\n\n"
                        f"🔐 <b>Shartnoma kodi:</b>\n<code>{data['code']}</code>\n\n"
                        f"⏳ <b>Davomiyligi:</b>\n<code>{self.format_time(duration)}</code>\n\n"
                        "♻️ <b>Tiklash:</b>\n<code>.fix {data['code']}</code>\n\n"
                        "❌ <b>O'chirish:</b>\n<code>.delcontract {data['code']}</code>"
                    )
                    await self.premium_send(self.config["LOG_CHAT"], text)
                except Exception:
                    pass

            # Fix deadline cleanup
            now = int(time.time())
            to_delete = []
            for uid, data in list(self.contracts.items()):
                if data.get("active"):
                    continue
                fix_deadline = data.get("fix_deadline")
                if fix_deadline and now >= fix_deadline:
                    to_delete.append(uid)

            for uid in to_delete:
                data = self.contracts.get(uid)
                if data:
                    try:
                        await self.client(LeaveChannelRequest(data["their_channel_id"]))
                    except Exception:
                        pass
                    del self.contracts[uid]

            if to_delete:
                self.save()
                for uid in to_delete:
                    data = self.contracts.get(uid) or {}
                    log_text = (
                        "❌ <b>SHARTNOMA BEKOR QILINDI</b>\n\n"
                        f"👤 <b>User:</b>\n@{data.get('username', uid)}\n\n"
                        f"📁 <b>Kanal:</b>\n{data.get('their_channel_text', '')}\n\n"
                        f"🔐 <b>Kod:</b>\n<code>{data.get('code', '')}</code>\n\n"
                        "⏳ <b>Sabab: muddat tugadi</b>"
                    )
                    await self.premium_send(self.config["LOG_CHAT"], log_text)

        except Exception as e:
            logger.exception(e)
        await asyncio.sleep(self.config["CHECK_DELAY"])
