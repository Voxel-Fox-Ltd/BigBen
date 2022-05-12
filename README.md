# BigBen

This bot send a bong message at the start of every hour. The first user to press the button gets a point.

The bot also features a leaderboard to see who has the most bongs in that guild.

All information below assumes the default prefix `bb.`

## Self-hosting

1. Download the source code, using a git client or the download zip button.
2. Make a copy of the `config/config.example.toml` but rename it to `config/config.toml`
3. Modify the config file to use the correct token, database and other options.
4. Run the bot using `voxelbotutils run-bot` or by building a docker container using the provided docker file.
5. Use the recommended invite link

## Invite the bot

`https://discord.com/api/oauth2/authorize?client_id=<client id>&permissions=536947776&scope=bot`

Replace `<client id>` with the bot application id.

## Setup

1. Type `bb.setup` to setup the bot, set the bong channel, role and emoji.
2. Wait for the start of the next hour for the bong.
