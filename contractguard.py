# meta developer: @djavame
# scope: hikka_only

import asyncio

from hikkatl.types import Message

from .. import loader, utils


@loader.tds
class ContractGuardMod(loader.Module):
    """
    Realtime Contract Guard
    """

    strings = {
        "name": "ContractGuard"
    }

    async def client_ready(self):

        self._task = asyncio.create_task(
            self.monitor_loop()
        )

    async def monitor_loop(self):

        while True:

            await asyncio.sleep(60)

    @loader.command()
    async def testcg(
        self,
        message: Message
    ):
        """Test"""

        await utils.answer(
            message,
            "✅ ContractGuard working"
        )
