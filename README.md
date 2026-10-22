# WhitemaneHCDeathDashboard

Gives insight into deaths of Whitemane's Frostmourne reamlm hardcore players'. Extracts and parses data from guild's Discord server `#death-log` channel, and produces charts using `quickchart.io`.

### Set up
Go to https://discord.com/developers/ and create an application/bot.

In OAuth2 produce an invitation URL for the bot with the following permissions:
- Message Content Intent: True
- Bot Permissions:
    - View Channels
    - Read Message History
    - Send Messages
    - Embed Links

Discord user with relevant server permissions to add bots should v isit the URL to add the bot to the channel.

On Github fork the repository and add the following repository secrets:
`DISCORD_BOT_TOKEN` - the token is generated on you application's page on discord developer portal.
`SOURCE_CHANNEL_ID` and `TARGET_CHANNEL_ID` - discord channel ids, inspectable in discord after enabling developer mode in settings.

The script can be triggered manually via Github Actions, and is also triggered automatically as indicated in 'run.yml`'s 'cron' section.