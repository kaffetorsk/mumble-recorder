import asyncio
import pymumble_py3 as pymumble
import logging
import os
import subprocess
from decouple import config
import shlex
import numpy as np
import time
from pymumble_py3.callbacks import (PYMUMBLE_CLBK_USERCREATED,
                                    PYMUMBLE_CLBK_USERUPDATED,
                                    PYMUMBLE_CLBK_USERREMOVED)
from PIL import Image, ImageDraw, ImageFont
import shutil


FFMPEG_OUT = config('FFMPEG_OUT')
STEP = config('STEP', default=0.001, cast=float)
BUFFER = config('BUFFER', default=2, cast=int)
ACTIVE_TIMEOUT = config('ACTIVE_TIMEOUT', default=1, cast=int)
SAMPLE_RATE = config('SAMPLE_RATE', default=48000, cast=int)
DEBUG = config('DEBUG', default=False, cast=bool)


class Recorder():
    def __init__(self, server, name, port, password, chan):
        self._stop = False
        self.client = pymumble.Mumble(server, name, port, password)
        self.chan = chan
        self.name = name
        self.users = []
        self.mixer = None
        self.streamer = None
        self.active_users = {}
        self.event_loop = asyncio.get_running_loop()
        self.cache_path = f"cache/{chan['name']}/"
        self._init_files()

    def _init_files(self):
        try:
            os.mkdir(self.cache_path)
        except FileExistsError:
            pass
        shutil.copy2('images/blank.jpg',
                     os.path.join(self.cache_path, 'view.jpg'))
        with open(os.path.join(self.cache_path, 'list.txt'), 'w') as file:
            file.writelines([
                "ffconcat version 1.0\n", "file view.jpg\n", "file view.jpg\n"
                ])

    async def run(self):
        self.client.start()
        await self.event_loop.run_in_executor(None, self.client.is_ready)

        # Get the channel object
        try:
            self.chan = [c for i, c in self.client.channels.items()
                         if c['channel_id'] == self.chan['channel_id']][0]
        except Exception as e:
            logging.warning(f"Failed to join {self.chan['name']}: {e}")
            self.stop()
            return

        # Join channel
        self.chan.move_in(self.client.users.myself_session)
        while self.client.my_channel() != self.chan:
            await asyncio.sleep(1)

        # Add user update callbacks
        self._update_users()
        for cb in [
            PYMUMBLE_CLBK_USERCREATED,
            PYMUMBLE_CLBK_USERUPDATED,
            PYMUMBLE_CLBK_USERREMOVED,
        ]:
            self.client.callbacks.set_callback(cb, self._update_users)

        self.client.set_receive_sound(1)

        # Spawn streamer and give it time to start before feeding it audio
        self.streamer, writer = await self._start_stream()
        await asyncio.sleep(15)
        self.mixer = self.event_loop.run_in_executor(None, self._mixer, writer)

        logging.info(f"Recording in {self.chan['name']}")
        await self.mixer
        await self.stop()

    def _mixer(self, writer):
        """
        Main loop that grabs soundchunks from users that are producing sound.
        A cursor is used to determine if the chunks should be mixed into
        the output.

        This method is heavily inspired by
        https://github.com/Robert904/mumblerecbot
        """
        next_view_update = 0
        base_chunk = np.zeros(shape=(int(SAMPLE_RATE * STEP)), dtype='<i2')
        cursor_time = time.time() - BUFFER

        while not self._stop:
            if time.time() - BUFFER > cursor_time:
                frames = [base_chunk]
                for user in self.users:

                    # Drain the queue for old chunks
                    while (
                        user.sound.is_sound()
                        and user.sound.first_sound().time < cursor_time
                    ):
                        user.sound.get_sound(STEP)

                    # Chunk that falls within the frames of current cursor
                    if (
                        user.sound.is_sound()
                        and user.sound.first_sound().time >= cursor_time
                        and user.sound.first_sound().time < cursor_time + STEP
                    ):
                        self.active_users[user['name']] = time.time()
                        frames.append(
                            np.fromstring(
                                user.sound.get_sound(STEP).pcm, '<i2'
                                ))

                if next_view_update < time.time():
                    self._update_active_users()
                    next_view_update = time.time() + 0.5

                # Use NumPy to perform (a + b + c ... / n) (Mixing)
                os.write(
                    writer, (
                        np.sum(np.asarray(frames), axis=0) / len(frames)
                               ).astype('<i2').tobytes())

                cursor_time += STEP

    async def _start_stream(self):
        """
        Spawns ffmpeg that reads audio from pipe, and infinitely loops a jpg
        showing active users and timestamp.
        """
        read, write = os.pipe()
        stderr = None if DEBUG else subprocess.DEVNULL
        proc = await asyncio.create_subprocess_exec(
            *([
                'ffmpeg',
                '-re',
                '-stream_loop', '-1',
                '-i', f'{self.cache_path}list.txt',
                '-ar', str(SAMPLE_RATE),
                '-f', 's16le',
                '-i', 'pipe:',
                '-map', '1:a', '-map', '0:v',
                '-video_size', '640x480',
                '-r', '20',
                '-flush_packets', '0',
                ] + shlex.split(
                    FFMPEG_OUT.format(name=self.chan['name'].lower())
                )),
            stdin=read, stdout=subprocess.DEVNULL, stderr=stderr
            )
        return proc, write

    # Something happened with the users, update list
    def _update_users(self, *args):
        self.users = [u for k, u in self.client.users.items()
                      if u['channel_id'] == self.chan['channel_id']
                      and u['name'] != self.name]
        self.active_users = {u['name']: 0 for u in self.users}

    # Draw the image showing users, activity and timestamp
    def _update_active_users(self):
        img = Image.new('RGB', (640, 480), color='black')
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype('fonts/CenturyGothic.ttf', 30)
        for i, (name, timeout) in enumerate(self.active_users.items()):
            color = 'red' if timeout + ACTIVE_TIMEOUT > time.time() else 'blue'
            col = 0 if i < 11 else 1
            row = i if i < 11 else i - 11
            draw.text(
                (10 + (330*col), 10 + (40*row)), name, fill=color, font=font)

        draw.text(
            (340, 440),
            time.strftime('%d-%m-%Y %H:%M:%S %Z',
                          time.localtime(time.time() - BUFFER)),
            fill='white',
            font=ImageFont.truetype('fonts/CenturyGothic.ttf', 25))

        img.save(os.path.join(self.cache_path, 'next.jpg'))
        os.replace(
            os.path.join(self.cache_path, 'next.jpg'),
            os.path.join(self.cache_path, 'view.jpg')
            )

    async def stop(self):
        try:
            self._stop = True
            logging.info(f"Shutting down {self.name}...")
            self.client.stop()
            self.streamer.kill()
            shutil.rmtree(self.cache_path)
        except Exception as e:
            logging.warning(
                f"Exception while shutting down {self.name}: {e}"
                )
