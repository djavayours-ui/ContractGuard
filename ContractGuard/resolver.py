import re
import logging
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.types import PeerChannel

logger = logging.getLogger(__name__)

async def resolve_user(self, user):
    try:
        if str(user).startswith("@"):
            return await self.client.get_entity(user)
        return await self.client.get_entity(int(user))
    except Exception:
        return None

async def resolve_channel(self, channel):
    """
    Returns (entity, joined: bool)
    """
    channel = str(channel).strip().split("?")[0].rstrip("/")

    async def _raw_call(request):
        return await self.client._call(self.client._sender, request, ordered=False)

    async def _join(entity):
        try:
            await _raw_call(JoinChannelRequest(entity))
            return True
        except UserAlreadyParticipantError:
            return True
        except Exception as e:
            logger.warning(f"_join failed: {e}")
            return False

    try:
        # Private invite
        invite_hash = None
        m = re.search(r"t\.me/\+([A-Za-z0-9_-]+)|t\.me/joinchat/([A-Za-z0-9_-]+)", channel)
        if m:
            invite_hash = m.group(1) or m.group(2)
        elif channel.startswith("+") and len(channel) > 5:
            invite_hash = channel[1:]

        if invite_hash:
            try:
                updates = await _raw_call(ImportChatInviteRequest(invite_hash))
                if updates and getattr(updates, "chats", None):
                    return updates.chats[0], True
                raise UserAlreadyParticipantError(None)
            except UserAlreadyParticipantError:
                entity = None
                try:
                    result = await _raw_call(CheckChatInviteRequest(invite_hash))
                    entity = getattr(result, "chat", None)
                    if entity is None:
                        cid = getattr(result, "channel_id", None) or getattr(result, "id", None)
                        if cid:
                            try:
                                entity = await self.client.get_entity(PeerChannel(cid))
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"CheckChatInviteRequest error: {e}")
                if entity is None:
                    return None, False
                joined = await _join(entity)
                return entity, joined
            except Exception as e:
                logger.warning(f"ImportChatInviteRequest failed: {e}")
                return None, False

        # Public
        if channel.startswith("@") or "t.me/" in channel:
            try:
                entity = await self.client.get_entity(channel)
            except Exception as e:
                logger.warning(f"get_entity (public) error: {e}")
                return None, False
            if entity is None:
                return None, False
            joined = await _join(entity)
            return entity, joined

        # Numeric ID
        try:
            entity = await self.client.get_entity(int(channel))
        except Exception as e:
            logger.warning(f"get_entity (id) error: {e}")
            return None, False
        joined = await _join(entity)
        return entity, joined

    except Exception as e:
        logger.warning(f"resolve_channel error: {e}")
        return None, False
