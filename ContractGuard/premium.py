from telethon.tl.types import MessageEntityCustomEmoji
from telethon.extensions import html as tl_html
from telethon.tl.functions.messages import EditMessageRequest

from .utils import utf16len
from .texts import EMOJIS

async def premium_edit(self, message, text: str):
    parsed_text, all_entities = _build_entities(text)
    await self.client(EditMessageRequest(
        peer=message.peer_id,
        id=message.id,
        message=parsed_text,
        entities=all_entities
    ))

async def premium_send(self, chat, text: str, reply_to=None):
    parsed_text, all_entities = _build_entities(text)
    return await self.client.send_message(
        chat,
        parsed_text,
        formatting_entities=all_entities,
        reply_to=reply_to
    )

def _build_entities(text: str):
    mapping = {
        "📦": EMOJIS["CONTRACT"],
        "📁": EMOJIS["CHANNEL"],
        "👤": EMOJIS["USER"],
        "🔐": EMOJIS["CODE"],
        "🕓": EMOJIS["TIME"],
        "✅": EMOJIS["SUCCESS"],
        "❌": EMOJIS["DELETE"],
        "⚠️": EMOJIS["WARNING"],
        "🆔": EMOJIS["ID"],
        "⏳": EMOJIS["DURATION"],
        "📊": EMOJIS["STATUS"],
        "♻️": EMOJIS["RECYCLE"]
    }
    parsed_text, html_entities = tl_html.parse(text)
    emoji_entities = []
    for emoji, doc_id in mapping.items():
        start = 0
        while True:
            try:
                pos = parsed_text.index(emoji, start)
            except ValueError:
                break
            offset = utf16len(parsed_text[:pos])
            length = utf16len(emoji)
            emoji_entities.append(MessageEntityCustomEmoji(
                offset=offset, length=length, document_id=doc_id
            ))
            start = pos + len(emoji)
    return parsed_text, list(html_entities) + emoji_entities
