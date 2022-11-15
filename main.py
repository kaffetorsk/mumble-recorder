import asyncio
from decouple import config
import logging
from monitor import Monitor
import signal
import os
import shutil


SERVER = config('SERVER')
PASSWORD = config('PASSWORD')
PORT = config('PORT', default=64738, cast=int)
DEBUG = config('DEBUG', default=False, cast=bool)
CLIENT_NAME = config('CLIENT_NAME', default="recorder")

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )


async def main():
    logging.info("Starting")

    try:
        os.mkdir('cache')
    except FileExistsError:
        pass

    event_loop = asyncio.get_running_loop()
    monitor = Monitor(SERVER, CLIENT_NAME, PORT, PASSWORD)

    # Graceful shutdown
    async def shutdown(signal):
        logging.info('Shutting down...')
        await monitor.stop()
        asyncio.get_running_loop().stop()
        try:
            shutil.rmtree('cache')
        except FileNotFoundError:
            pass

    # Callbacks for shutdown signals
    for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        event_loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s)))

    # Run the Monitor
    await monitor.run()

try:
    asyncio.run(main())
except RuntimeError:
    logging.info("Done.")
