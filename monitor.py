import pymumble_py3 as pymumble
import logging
from recorder import Recorder
import asyncio


class Monitor():
    """
    This class is initiated first, and enters the server to list channels and
    spawn recorders into each channel.
    """
    def __init__(self, server, name, port, password):
        self.server = server
        self.name = name
        self.port = port
        self.password = password
        self.client = pymumble.Mumble(self.server, name,
                                      self.port, self.password)

    async def run(self):
        self.client.start()
        self.client.is_ready()
        logging.info(f"Connected to {self.server}:{self.port}")
        self.recorders = []

        self.recorders = [
            Recorder(self.server, f"{self.name}-{chan['name']}",
                     self.port, self.password, chan)
            for chan in self.client.channels.values()
            ]

        tasks = []
        for r in self.recorders:
            tasks.append(asyncio.create_task(r.run()))
            await asyncio.sleep(5)

        await asyncio.gather(*tasks)

        # chan = self.client.channels[3]
        # rec = Recorder(self.server, f"{self.name}-{chan['name']}",
        #                self.port, self.password, chan)
        # await rec.run()

    async def stop(self):
        try:
            for r in self.recorders:
                await r.stop()
        except Exception:
            pass
        self.client.stop()
