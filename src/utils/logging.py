import os
import discord

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

async def enviar_log(guild: discord.Guild, embed: discord.Embed):
    if LOG_CHANNEL_ID > 0:
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                print(f"Error sending log to channel {LOG_CHANNEL_ID}: {e}")
