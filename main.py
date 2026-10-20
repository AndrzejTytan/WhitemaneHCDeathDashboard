import asyncio
import os
re = __import__('re')
discord = __import__('discord')
import aiohttp
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
SOURCE_CHANNEL_ID = int(os.environ.get('SOURCE_CHANNEL_ID', 0))
TARGET_CHANNEL_ID = int(os.environ.get('TARGET_CHANNEL_ID', 0))

RACES = ("Blood Elf", "Night Elf", "Draenei", "Dwarf", "Gnome", "Human", "Orc", "Tauren", "Troll", "Undead")
CLASSES = ("Death Knight", "Druid", "Hunter", "Mage", "Paladin", "Priest", "Rogue", "Shaman", "Warlock", "Warrior")
race_pattern = "|".join(re.escape(name) for name in sorted(RACES, key=len, reverse=True))
class_pattern = "|".join(re.escape(name) for name in sorted(CLASSES, key=len, reverse=True))

LOG_PATTERN = re.compile(
    rf"^(?P<player>.+?) the level (?P<level>\d+) "
    rf"(?P<race>{race_pattern}) (?P<class>{class_pattern}) "
    rf"has been slain by (?P<slain_by>.+?) in (?P<location>.+?)"
    rf"(?:\.)?(?:\s*/run\s+PlayHardcoreReplay\(\d+\))?\s*$"
)

class KillLogBot(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        try:
            source_channel = self.get_channel(SOURCE_CHANNEL_ID)
            target_channel = self.get_channel(TARGET_CHANNEL_ID)
            
            if not source_channel or not target_channel:
                print("Error: Could not find source or target channel IDs.")
                return

            print(f"Fetching messages from #{source_channel.name}...")
            data = []
            async for message in source_channel.history(limit=None):
                match = LOG_PATTERN.search(message.content)
                if match:
                    data.append(match.groupdict())

            print(f"Successfully extracted {len(data)} kill records.")

            if not data:
                print("No matching kill logs found.")
                return

            # Count top zones or killers for a simple summary
            killers = {}
            for row in data:
                mob = row['slain_by']
                killers[mob] = killers.get(mob, 0) + 1
            
            top_killers = sorted(killers.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # Build text summary report
            summary_text = "**__Recent Kill Log Report__**\n"
            summary_text += f"Total deaths analyzed: `{len(data)}`\n\n"
            summary_text += "**Top Dangerous Mobs:**\n"
            for mob, count in top_killers:
                summary_text += f"- {mob}: {count} kills\n"

            # Generate QuickChart payload to avoid heavy local image compilation
            chart_config = {
                "type": "bar",
                "data": {
                    "labels": [k[0] for k in top_killers],
                    "datasets": [{
                        "label": "Player Deaths",
                        "data": [k[1] for k in top_killers],
                        "backgroundColor": "rgba(231, 76, 60, 0.7)"
                    }]
                }
            }
            
            chart_url = None
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        "https://quickchart.io/chart/create",
                        json={"chart": chart_config, "width": 500, "height": 300},
                    ) as response:
                        response.raise_for_status()
                        chart_result = await response.json()
                        if isinstance(chart_result, dict):
                            chart_url = chart_result.get("url")
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                print(f"Could not generate chart: {e}")

            # Post results to target channel
            embed = discord.Embed(title="⚔️ Automated Kill Log Analysis", color=0xE74C3C)
            embed.description = summary_text
            if chart_url:
                embed.set_image(url=chart_url)

            await target_channel.send(embed=embed)
            print("Report successfully posted to Discord!")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await self.close()

intents = discord.Intents.default()
intents.message_content = True
client = KillLogBot(intents=intents)
client.run(DISCORD_BOT_TOKEN)