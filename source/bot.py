import discord
from discord.ext import commands
import logging
import gtssetupfiles
import json
import sqlite3
import googlemaps
import ntplib
import time
from asyncio import sleep as async_sleep
import random

gtssetupfiles.checktokenfile()      # Check token file and database to make sure they are in good form
gtssetupfiles.checkdatabase()
with open("token.json", "r") as bot_token_file:     # Open token file and read tokens out of it
    bot_token_json = json.loads(bot_token_file.read())
    bot_token = bot_token_json["botToken"]
    google_token = bot_token_json["googleToken"]

gmaps = googlemaps.Client(google_token)
ntpclient = ntplib.NTPClient()
ntpserver = "ntp.plus.net"

sleepydb = sqlite3.connect("../sleepy.db")
sleepycursor = sleepydb.cursor()

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("gotosleeplog.txt", "w", "utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

sleepingbot = commands.Bot("s!")


@sleepingbot.event
async def on_ready():
    print("Loading up...")
    print("My name is " + sleepingbot.user.name)
    print("My ID is " + str(sleepingbot.user.id))
    print("Autobots, roll out")
    await sleepingbot.change_presence(activity=discord.Game("Oh god I'm alive"))


def remove_prefix(command, message):
    message = message.replace("s!"+command, "").strip()
    return message


@sleepingbot.command(pass_context=True)
async def sleep(ctx):
    await ctx.send("Go to sleep")


@sleepingbot.command(pass_context=True)
async def register(ctx):
    message = remove_prefix("register", ctx.message.content)
    # Prevents the rest from running if message is empty, since this will cause an error with the Geocoding API
    if message != "":
        location_geocode = gmaps.geocode(address=message)
        latlong = location_geocode[0]["geometry"]["location"]
        name = ""
        for address in location_geocode[0]["address_components"]:   # Finds the most generic but still useful form of the address given
            if address["types"] == ["administrative_area_level_1", "political"]:
                name = address["long_name"]
            # Gets the country name as a last resort if a lower-level region cannot be found
            if address["types"] == ["country", "political"]:
                if name == "":
                    name = address["long_name"]
        # If this name is not already in the cache:
        cached_location = sleepycursor.execute("SELECT * FROM area_cache WHERE area_name = ?", (name,)).fetchone()
        if cached_location is None:
            area_id = await newlocation(name, latlong, ctx)
        else:
            area_id = cached_location[0]
        # If user is not already in the database
        if sleepycursor.execute("SELECT user_id FROM sleep_tracker WHERE user_id = ?", (ctx.author.id,)) is None:
            sleepycursor.execute("""INSERT INTO sleep_tracker(user_id, area_id)
                                VALUES (?,?)""", (ctx.author.id, area_id))
        else:
            sleepycursor.execute("UPDATE sleep_tracker SET area_id=? WHERE user_id = ?", (area_id, ctx.author.id))
        sleepydb.commit()
        await ctx.send("You are now registered at "+name)


async def newlocation(name, latlong, ctx):
    timezone_info = gmaps.timezone(latlong)
    await ctx.send(timezone_info)
    timezone_in_database = sleepycursor.execute("SELECT timezone_id FROM timezones WHERE timezone_id=?",
                                                (timezone_info["timeZoneId"],)).fetchone()
    if timezone_in_database is not None:    # If the timezone in question is already in the database
        timezone_in_database = timezone_in_database[0]
    # If the timezone is not already in the database:
    if timezone_in_database != timezone_info["timeZoneId"]:
        sleepycursor.execute("""INSERT INTO timezones(timezone_id, timezone_name, utc_offset, dst_offset)
                    VALUES (?,?,?,?)""", (timezone_info["timeZoneId"], timezone_info["timeZoneName"], timezone_info["rawOffset"], timezone_info["dstOffset"]))
    sleepycursor.execute("""INSERT INTO area_cache(area_name, latitude, longitude, timezone_id) 
                VALUES(?,?,?,?) """, (name, latlong["lat"], latlong["lng"], timezone_info["timeZoneId"]))
    sleepydb.commit()
    area_id = sleepydb.execute("SELECT area_id FROM area_cache WHERE area_name = ?", (name,)).fetchone()
    return area_id[0]


async def align_to_hour():
    ntpresponse = ntpclient.request(ntpserver, version=3)
    ntptime = time.localtime(ntpresponse.tx_time)
    offsetfromnexthour = ((60 - ntptime.tm_min) - (ntptime.tm_sec / 60)) * 60
    await async_sleep(offsetfromnexthour)


async def refreshtimezoneoffset():
    await sleepingbot.wait_until_ready()
    aligning = False
    while aligning is True:
        await align_to_hour()
        aligning = False
    while aligning is False:
        for timezone in sleepycursor.execute("""SELECT timezones.timezone_id, ac.latitude, ac.longitude FROM timezones
                JOIN area_cache ac on timezones.timezone_id = ac.timezone_id""").fetchall():
            latlong = {"lat": timezone[1], "lng": timezone[2]}
            new_time = gmaps.timezone(latlong)
            sleepycursor.execute("""UPDATE timezones SET utc_offset=?, dst_offset=? WHERE timezone_id=?""",
                             (new_time["rawOffset"], new_time["dstOffset"], timezone[0]))
        sleepydb.commit()
        timetosleep = random.randrange(129, 200)
        await async_sleep(timetosleep)

@sleepingbot.command(pass_context=True)
async def testntp(ctx):
    ntpresponse = ntpclient.request("ntp.plus.net", version=3)
    ntptime = time.localtime(ntpresponse.tx_time)
    offsetfromnexthour = ((60 - ntptime.tm_min) - (ntptime.tm_sec/60)) * 60
    await ctx.send("Going into hibernation...")
    await async_sleep(offsetfromnexthour)
    ntpresponse = ntpclient.request("ntp.plus.net", version=3)
    ntptime = time.ctime(ntpresponse.tx_time)
    await ctx.send(ntptime)
    await ctx.send("I bet you didn't see me coming!")


@sleepingbot.command(pass_context=True)
async def aboutme(ctx):
    await ctx.send('''Hey! I'm the descendant of an older bot, just called "Go To Sleep", and trust me you don't want to see that
My source is at https://github.com/Lewis-Trowbridge/Go-To-Sleep-Revengeance in case you wanted to know more about me.''')

sleepingbot.loop.create_task(refreshtimezoneoffset())
sleepingbot.run(bot_token)
