import discord
from discord.ext import commands
import logging
import gtssetupfiles
import json
import sqlite3
import googlemaps
import ntplib
import datetime
from asyncio import sleep as async_sleep

gtssetupfiles.checktokenfile()  # Check token file and database to make sure they are in good form
gtssetupfiles.checkdatabase()
gtssetupfiles.checklogdirectory()  # Check log directory to make sure it is there and make it if it is not
gtssetupfiles.checksupportserver()  # Check support server invite to make sure it is there and make it if it is not

with open(
    "token.json", "r"
) as bot_token_file:  # Open token file and read tokens out of it
    bot_token_json = json.loads(bot_token_file.read())
    bot_token = bot_token_json["botToken"]
    google_token = bot_token_json["googleToken"]

with open("supportserver.json", "r") as support_server_file:
    support_server_json = json.loads(support_server_file.read())
    support_server_invite = support_server_json["supportServerInvite"]

gmaps = googlemaps.Client(google_token)
ntpclient = ntplib.NTPClient()
ntpserver = "time.google.com"
ntpoffset = datetime.datetime.now()

sleepydb = sqlite3.connect("../sleepy.db")
sleepycursor = sleepydb.cursor()

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(
    "./logs/gotosleeplog-"
    + datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    + ".txt",
    "w",
    "utf-8",
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

sleepingbot = commands.Bot("s!")


@sleepingbot.event
async def on_ready():
    print("Loading up...")
    print("My name is " + sleepingbot.user.name)
    print("My ID is " + str(sleepingbot.user.id))
    print("Autobots, roll out")
    await sleepingbot.change_presence(activity=discord.Game("s!help"))


def remove_prefix(command, message):
    message = message.replace("s!" + command, "").strip()
    return message


@sleepingbot.command(pass_context=True)
async def link(ctx):

    """
    Link a channel - use this one first!

    Links a channel for me to post pings to it's bedtime. I can't send any until you do this, so it's important you do this first.

    Usage: s!link
    Example:
        User: s!link
        Me: This channel has been registered as where I'll send pings - please don't force me to!
    """
    # If this channel is not registered
    if (
        sleepycursor.execute(
            "SELECT * FROM server_linked_channels WHERE server_id=?",
            (ctx.message.guild.id,),
        ).fetchone()
        is None
    ):
        sleepycursor.execute(
            "INSERT INTO server_linked_channels(server_id, channel_id) VALUES (?, ?)",
            (ctx.message.guild.id, ctx.message.channel.id),
        )
        await ctx.send(
            "This channel has been registered as where I'll send pings - please don't force me to!"
        )
    else:
        sleepycursor.execute(
            "UPDATE server_linked_channels SET channel_id=? WHERE server_id=?",
            (ctx.message.channel.id, ctx.message.guild.id),
        )
        await ctx.send("Okay, I'll ping here from now on!")
    sleepydb.commit()


@sleepingbot.command(pass_context=True)
async def register(ctx):

    """
    Register yourself for sleep notifications!

    This one will let you actually see the point in this bot - it will notify you to go to sleep at a suitable time in your timezone.

    You might be rightfully alarmed at the fact that I'm asking you in effect where you live, but don't worry - I don't need much to work out your timezone, and I will make sure to always get the most generic version possible, and I'll tell you what I've found afterwards.

    Usage: s!register [location]
    
    Example:
        User: s!register London
        Me: You are now registered at England. I'll now message you in this server.
    """

    message = remove_prefix("register", ctx.message.content)
    # Prevents the rest from running if message is empty, since this will cause an error with the Geocoding API
    if message != "":
        location_geocode = gmaps.geocode(address=message)
        # Filters out any garbage locations or anywhere that Google cannot find
        try:

            latlong = location_geocode[0]["geometry"]["location"]
        except IndexError:
            await ctx.send(
                "Sorry, there was a problem with finding the exact location for that. Please try another configuration, and if that doesn't work, please contact the owner."
            )
            return
        name = ""
        for address in location_geocode[0][
            "address_components"
        ]:  # Finds the most generic but still useful form of the address given
            if address["types"] == ["administrative_area_level_1", "political"]:
                name = address["long_name"]
            # Gets the country name as a last resort if a lower-level region cannot be found
            if address["types"] == ["country", "political"]:
                if name == "":
                    name = address["long_name"]
        # If this name is not already in the cache:
        cached_location = sleepycursor.execute(
            "SELECT * FROM area_cache WHERE area_name = ?", (name,)
        ).fetchone()
        if cached_location is None:
            area_id = await new_location(name, latlong)
        else:
            area_id = cached_location[0]

        # If user is not already in the database
        if (
            sleepycursor.execute(
                "SELECT user_id FROM sleep_tracker WHERE user_id = ?", (ctx.author.id,)
            ).fetchone()
            is None
        ):
            server_id = sleepycursor.execute(
                "SELECT server_id FROM server_linked_channels WHERE server_id = ?",
                (ctx.message.guild.id,),
            ).fetchone()
            # If the server does not already have a linked channel
            if server_id is None:
                await ctx.send(
                    "Sorry, but you'll need to link a channel to use first using the s!link command. I'd recommend a channel used only for bots."
                )
                return
            else:
                sleepycursor.execute(
                    """INSERT INTO sleep_tracker(user_id, area_id, server_id)
                                VALUES (?,?,?)""",
                    (ctx.author.id, area_id, server_id[0]),
                )
        # If user is already in the database
        else:
            sleepycursor.execute(
                "UPDATE sleep_tracker SET area_id=?, server_id=? WHERE user_id = ?",
                (area_id, ctx.message.guild.id, ctx.author.id),
            )
        sleepydb.commit()
        await ctx.send(
            "You are now registered at "
            + name
            + ". I'll now message you in this server."
        )


async def new_location(name, latlong):
    timezone_info = gmaps.timezone(latlong)
    timezone_in_database = sleepycursor.execute(
        "SELECT timezone_id FROM timezones WHERE timezone_id=?",
        (timezone_info["timeZoneId"],),
    ).fetchone()
    if (
        timezone_in_database is not None
    ):  # If the timezone in question is already in the database
        timezone_in_database = timezone_in_database[0]
    # If the timezone is not already in the database:
    if timezone_in_database != timezone_info["timeZoneId"]:
        sleepycursor.execute(
            """INSERT INTO timezones(timezone_id, timezone_name, utc_offset, dst_offset)
                    VALUES (?,?,?,?)""",
            (
                timezone_info["timeZoneId"],
                timezone_info["timeZoneName"],
                timezone_info["rawOffset"],
                timezone_info["dstOffset"],
            ),
        )
    sleepycursor.execute(
        """INSERT INTO area_cache(area_name, latitude, longitude, timezone_id) 
                VALUES(?,?,?,?) """,
        (name, latlong["lat"], latlong["lng"], timezone_info["timeZoneId"]),
    )
    sleepydb.commit()
    area_id = sleepydb.execute(
        "SELECT area_id FROM area_cache WHERE area_name = ?", (name,)
    ).fetchone()
    return area_id[0]


@sleepingbot.command(pass_context=True)
async def unregister(ctx):

    """
    Unregisters you for sleep notifications

    As simple as it sounds - this lets you delete yourself from my list if you feel like you don't want notifications.

    Usage: s!unregister

    Example:
        User: s!unregister
        Me: Okay, all done!
    """
    if (
        sleepycursor.execute(
            "SELECT user_id FROM sleep_tracker WHERE user_id = ?", (ctx.author.id,)
        ).fetchone()
        is not None
    ):
        sleepycursor.execute(
            "DELETE FROM sleep_tracker WHERE user_id = ?", (ctx.author.id,)
        )
        sleepydb.commit()
        await ctx.send("Okay, all done!")
    else:
        await ctx.send("Sorry, I can't find you - are you sure you're registered?")


@sleepingbot.command(pass_context=True)
async def bedtime(ctx):
    """
    Sets a custom bedtime!

    Allows you to decide when you want me to ping you - I'm trusting you to help yourself here, but I understand improving your sleep schedule isn't an instant matter and so should you.
    At the moment I only support 24-hour format for understanding exactly what time you mean, so please use that.

    Usage: s!bedtime [time]

    Example:
        User: s!bedtime 1:00
        Me: Got it! Well done for taking some action!
    """

    # If the user is already in the database
    if (
        sleepycursor.execute(
            "SELECT user_id FROM sleep_tracker WHERE user_id=?", (ctx.author.id,)
        ).fetchone()
        is not None
    ):
        try:
            string_bedtime = remove_prefix("bedtime", ctx.message.content)
            string_hour, string_minutes = str.split(string_bedtime, ":")
        # Filter out no colon placement
        except ValueError:
            await ctx.send(
                "Sorry, something went wrong there. Please try typing that in again - have you placed a colon?"
            )
            return
        # Filter out string placements
        try:
            hour = int(string_hour)
            minutes = int(string_minutes)
        except ValueError:
            await ctx.send(
                "Sorry, something went wrong there. Silly as it sounds, have you made sure to put both hours and minutes?"
            )
            return
        if hour == 24:
            hour = 0
        if hour > 24 or hour < 0 or minutes > 60 or minutes < 0:
            await ctx.send(
                "Sorry, something went wrong there. Are you sure you're using 24-hour time?"
            )
            return
        offset = (hour * 3600) + (minutes * 60)
        sleepycursor.execute(
            "UPDATE sleep_tracker SET bedtime_offset=? WHERE user_id=?",
            (offset, ctx.author.id),
        )
        sleepydb.commit()
        await ctx.send("Okay, that should be all! Well done for taking some action!")
    else:
        await ctx.send("Sorry, please register first - then we can get to this part.")


async def align_to_hour():
    ntpresponse = ntpclient.request(ntpserver, version=3)
    ntptime = datetime.datetime.utcfromtimestamp(ntpresponse.tx_time)
    offsetfromnexthour = ((60 - ntptime.minute) - (ntptime.second / 60)) * 60
    await async_sleep(offsetfromnexthour)


async def align_to_minute():
    global ntpoffset
    ntpresponse = ntpclient.request(ntpserver, version=3)
    ntptime = datetime.datetime.utcfromtimestamp(ntpresponse.tx_time)
    now = datetime.datetime.now()
    ntpoffset = ntptime - now
    offsetfromnextminute = 60 - ntptime.second
    await async_sleep(offsetfromnextminute)


async def refresh_timezone_offset():
    await sleepingbot.wait_until_ready()
    aligning = True
    while aligning is True:
        await align_to_hour()
        aligning = False
    while aligning is False:
        for timezone in sleepycursor.execute(
            """SELECT timezones.timezone_id, ac.latitude, ac.longitude FROM timezones
                JOIN area_cache ac on timezones.timezone_id = ac.timezone_id"""
        ).fetchall():
            latlong = {"lat": timezone[1], "lng": timezone[2]}
            new_time = gmaps.timezone(latlong)
            sleepycursor.execute(
                """UPDATE timezones SET utc_offset=?, dst_offset=? WHERE timezone_id=?""",
                (new_time["rawOffset"], new_time["dstOffset"], timezone[0]),
            )
        sleepydb.commit()
        await async_sleep(86400)


async def check_sleep():
    await sleepingbot.wait_until_ready()
    aligning = True
    while aligning is True:
        await align_to_minute()
        aligning = False
    while aligning is False:
        current_server_id = 0
        current_server_members = []
        current_channel_to_ping = 0
        lost_server_id = 0
        user_info = sleepycursor.execute(
            """SELECT user_id, sleep_tracker.server_id, bedtime_offset, t.utc_offset, t.dst_offset, slc.channel_id FROM sleep_tracker
    JOIN area_cache ac on sleep_tracker.area_id = ac.area_id
    JOIN timezones t on ac.timezone_id = t.timezone_id
    JOIN server_linked_channels slc on sleep_tracker.server_id = slc.server_id
    ORDER BY sleep_tracker.server_id;"""
        ).fetchall()
        for user in user_info:
            server_id = user[1]
            if server_id == lost_server_id:
                continue
            user_id = user[0]
            bedtime_offset = user[2]
            utc_offset = user[3]
            dst_offset = user[4]
            channel_to_ping = user[5]
            # If we've entered the range of users from a different server from the one we're looking at
            if server_id != current_server_id:
                # Fire off the messages to users from the old server
                await go_to_sleep(current_server_members, current_channel_to_ping)
                current_server_id = server_id  # Aim at the new server
                # Get a new guild object for the desired server to get member objects from
                current_server = sleepingbot.get_guild(current_server_id)
                current_server_members = []  # Clear out the members already gathered
                current_channel_to_ping = channel_to_ping
                if (
                    current_server is None
                ):  # If for some reason we cannot access a server, for example we've been kicked, delete all data about it
                    sleepycursor.execute(
                        "DELETE FROM sleep_tracker WHERE server_id = ? ",
                        (current_server_id,),
                    )  # Delete user data for users from that server, critical for privacy and ethical reasons
                    sleepycursor.execute(
                        "DELETE FROM server_linked_channels WHERE server_id = ?",
                        (current_server_id,),
                    )  # Delete server data, more to save space than privacy
                    sleepydb.commit()
                    lost_server_id = current_server_id
                    continue

            time_in_timezone = (
                datetime.datetime.now()
                + ntpoffset
                + datetime.timedelta(seconds=utc_offset)
                + datetime.timedelta(seconds=dst_offset)
            )
            bedtime_float = bedtime_offset / 3600
            bedtime_hours = int(bedtime_float)
            bedtime_minutes = round((bedtime_float - bedtime_hours) * 60)
            if (
                time_in_timezone.hour == bedtime_hours
                and time_in_timezone.minute == bedtime_minutes
            ):
                current_member = current_server.get_member(user_id)
                current_server_members.append(current_member)
        await go_to_sleep(current_server_members, current_channel_to_ping)
        await async_sleep(60)


async def go_to_sleep(members_to_ping, channel_id):
    if (
        len(members_to_ping) != 0
    ):  # If there are more than 0 members to ping, start counting through them - filters out the empty starting list
        sleep_time_string = ""
        well_done_string = ""
        channel_to_ping = sleepingbot.get_channel(channel_id)
        for user_to_ping in members_to_ping:
            if (
                user_to_ping.status == discord.Status.online
            ):  # If the user is online, add them to the list to be told to go to sleep.
                sleep_time_string += user_to_ping.mention + ", "
            else:  # If the user is not online, add them to the list to be congratulated for going to sleep.
                well_done_string += user_to_ping.name + ", "
        if (
            len(sleep_time_string) != 0
        ):  # If there are any users that have to go to sleep, send the message.
            await channel_to_ping.send(sleep_time_string + "it's time to go to sleep.")
        if (
            len(well_done_string) != 0
        ):  # If there are any users that are asleep, send the message.
            await channel_to_ping.send(
                well_done_string
                + "well done. It's good to see you're taking your health seriously. I'm proud of you!"
            )
    else:
        return


@sleepingbot.command(pass_context=True)
async def support(ctx):

    """
    Gives you the link for the support server

    If there's a problem you can't solve, go here to the support server! Try to give as much detail as possible please, as that will make it easier to solve
    """
    if support_server_invite != "":
        await ctx.send("Here's the invite: " + support_server_invite)
    else:
        await ctx.send(
            "Sorry, there doesn't seem to be a support server in this implementation of the bot - this may be a clone of the original source code without one."
        )


@sleepingbot.command(pass_context=True)
async def aboutme(ctx):

    """
    Tells you all about me

    There's not much to this one - it's just telling you why I'm named like this and where you can find out more.
    """
    await ctx.send(
        """Hey! I'm the descendant of an older bot, just called "Go To Sleep", and trust me you don't want to see that
My source is at https://github.com/Lewis-Trowbridge/Go-To-Sleep-Revengeance in case you wanted to know more about me."""
    )


sleepingbot.loop.create_task(refresh_timezone_offset())
sleepingbot.loop.create_task(check_sleep())
sleepingbot.run(bot_token)
