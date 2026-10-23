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
SPECIAL_DEATH_SOURCES = ("Warlord Krom'zar", "himself/herself", "Somnus", "Kobold")
CLASS_COLORS = {
    "Death Knight": "#C41E3A",
    "Druid": "#FF7C0A",
    "Hunter": "#AAD372",
    "Mage": "#3FC7EB",
    "Paladin": "#F48CBA",
    "Priest": "#F0F0F0",
    "Rogue": "#FFF468",
    "Shaman": "#0070DD",
    "Warlock": "#8788EE",
    "Warrior": "#C69B6D",
}
race_pattern = "|".join(re.escape(name) for name in sorted(RACES, key=len, reverse=True))
class_pattern = "|".join(re.escape(name) for name in sorted(CLASSES, key=len, reverse=True))

LOG_PATTERN = re.compile(
    rf"^(?P<player>.+?) the level (?P<level>\d+) "
    rf"(?P<race>{race_pattern}) (?P<class>{class_pattern}) "
    rf"has been slain by (?P<slain_by>.+?) in (?P<location>.+?)"
    rf"(?:\.)?(?:\s*/run\s+PlayHardcoreReplay\(\d+\))?\s*$"
)


def make_chart_config(labels, values, colors=None):
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Deaths",
                "data": values,
                "backgroundColor": colors or "rgba(231, 76, 60, 0.7)",
                "borderColor": "#666666" if colors else "rgba(231, 76, 60, 0.7)",
                "borderWidth": 1,
            }],
        },
        "options": {
            "indexAxis": "x",
            "legend": {"display": False},
            "plugins": {
                "legend": {"display": False},
                "datalabels": {
                    "anchor": "end",
                    "align": "top",
                    "color": "#FFFFFF",
                    "font": {"weight": "bold"},
                },
            },
            "scales": {
                "yAxes": [{
                    "ticks": {
                        "beginAtZero": True,
                        "precision": 0,
                        "maxTicksLimit": 8,
                        "fontSize": 16,
                        "fontStyle": "bold",
                    },
                }],
                "xAxes": [{
                    "ticks": {
                        "maxRotation": 60,
                        "fontSize": 16,
                        "fontStyle": "bold",
                    },
                }],
                "y": {
                    "beginAtZero": True,
                    "ticks": {"precision": 0, "font": {"size": 16, "weight": "bold"}},
                },
                "x": {"ticks": {"maxRotation": 60, "font": {"size": 16, "weight": "bold"}}},
            },
        },
    }


async def create_chart_url(session, chart_name, chart_config):
    try:
        async with session.post(
            "https://quickchart.io/chart/create",
            json={"chart": chart_config, "width": 600, "height": 400},
        ) as response:
            response.raise_for_status()
            chart_result = await response.json()
            if isinstance(chart_result, dict):
                chart_url = chart_result.get("url")
                if chart_url:
                    return chart_url
                print(f"Could not generate {chart_name} chart: QuickChart returned {chart_result}")
            else:
                print(f"Could not generate {chart_name} chart: unexpected response {chart_result!r}")
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        print(f"Could not generate {chart_name} chart: {e}")
    return None


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
                    record = match.groupdict()
                    if record["slain_by"].strip().casefold() == record["player"].strip().casefold():
                        record["slain_by"] = "himself/herself"
                    data.append(record)

            print(f"Successfully extracted {len(data)} kill records.")

            if not data:
                print("No matching kill logs found.")
                return

            level_brackets = (
                ("1-10", 1, 10),
                ("11-20", 11, 20),
                ("21-30", 21, 30),
                ("31-40", 31, 40),
                ("41-50", 41, 50),
                ("51-60", 51, 60),
                ("61-70", 61, 70),
                ("71-79", 71, 79),
            )
            class_deaths = {class_name: 0 for class_name in CLASSES}
            level_deaths = {label: 0 for label, _, _ in level_brackets}
            mob_deaths = {}
            location_deaths = {}
            deaths_outside_brackets = 0

            for row in data:
                class_name = row['class']
                class_deaths[class_name] += 1

                level = int(row['level'])
                matching_bracket = next(
                    (label for label, lower, upper in level_brackets if lower <= level <= upper),
                    None,
                )
                if matching_bracket:
                    level_deaths[matching_bracket] += 1
                else:
                    deaths_outside_brackets += 1

                mob = row['slain_by']
                mob_deaths[mob] = mob_deaths.get(mob, 0) + 1
                location = row['location']
                location_deaths[location] = location_deaths.get(location, 0) + 1

            top_mobs = sorted(mob_deaths.items(), key=lambda item: (-item[1], item[0]))[:10]
            top_locations = sorted(location_deaths.items(), key=lambda item: (-item[1], item[0]))[:10]
            class_totals = sorted(class_deaths.items(), key=lambda item: (-item[1], item[0]))
            special_deaths = {
                source: (
                    sum(
                        count
                        for mob, count in mob_deaths.items()
                        if "kobold" in mob.casefold()
                    )
                    if source == "Kobold"
                    else mob_deaths.get(source, 0)
                )
                for source in SPECIAL_DEATH_SOURCES
            }
            special_deaths = dict(
                sorted(special_deaths.items(), key=lambda item: (-item[1], item[0]))
            )

            chart_specs = [
                (
                    "Deaths by Class",
                    [item[0] for item in class_totals],
                    [item[1] for item in class_totals],
                    [CLASS_COLORS[item[0]] for item in class_totals],
                ),
                ("Deaths by Level Bracket", list(level_deaths), list(level_deaths.values()), None),
                ("Top 10 Most Dangerous Mobs", [item[0] for item in top_mobs], [item[1] for item in top_mobs], None),
                ("Top 10 Most Dangerous Locations", [item[0] for item in top_locations], [item[1] for item in top_locations], None),
                ("Special Deaths by Source", list(special_deaths), list(special_deaths.values()), None),
            ]

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                chart_urls = await asyncio.gather(*(
                    create_chart_url(
                        session,
                        title,
                        make_chart_config(labels, values, colors),
                    )
                    for title, labels, values, colors in chart_specs
                ))

            embeds = []
            for index, (title, _, _, _) in enumerate(chart_specs):
                embed = discord.Embed(title=title, color=0xE74C3C)
                if index == 1 and deaths_outside_brackets:
                    embed.description = (
                        f"{deaths_outside_brackets} deaths were outside the requested level brackets."
                    )
                if chart_urls[index]:
                    embed.set_image(url=chart_urls[index])
                elif embed.description:
                    embed.description += "\nChart unavailable."
                else:
                    embed.description = "Chart unavailable."
                embeds.append(embed)

            await target_channel.send(content=f"# Total Deaths: {len(data)}", embeds=embeds)
            print("Report successfully posted to Discord!")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await self.close()

intents = discord.Intents.default()
intents.message_content = True
client = KillLogBot(intents=intents)
client.run(DISCORD_BOT_TOKEN)