[![CodeQL](https://github.com/kaffetorsk/mumble-recorder/actions/workflows/codeql.yml/badge.svg)](https://github.com/kaffetorsk/mumble-recorder/actions/workflows/codeql.yml)

# mumble-recorder
Python script that spawns recorder bots in all channels of a Murmur server.
Audio output is directed by modifying FFMPEG_OUT.

## Usage
Config through environment variables, if `.env` is present it will be checked for variables.
Where applicable `{name}` will be replaced by channel name.
### Required
```
SERVER: Server IP
PASSWORD: Server password
FFMPEG_OUT: out-string for ffmpeg. (e.g. -c:v copy -c:a copy -f flv rtmp://127.0.0.1:1935/live/{name})
```
### Optional
```
PORT: Server port (default: 64738)
DEBUG: Enable debug logging (default: False)
CLIENT_NAME: Name of the bot (default: "recorder")
STEP: Timestep in seconds between pulling soundchunks, has to be in intervals of 10ms (default: 0.001)
BUFFER: Incoming sound buffer (in seconds) (default: 2)
ACTIVE_TIMEOUT: Time in seconds before a user is shown as not active, after sound has stopped (default: 1)
SAMPLE_RATE: Sample rate of soundchunks recieved by pymumble (default: 48000)
```
### Running
```
python main.py
```
or
```
docker run -d --env-file .env kaffetorsk/mumble-recorder
```
## Acknowledgements
Main running loop is heavily inspired by [Robert904/mumblerecbot](https://github.com/Robert904/mumblerecbot)

## Notes
This repo is in early development, treat it as such and feel free to submit PRs.
