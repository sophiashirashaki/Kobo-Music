import aiofiles
import ffmpeg
import asyncio
import os
import shutil
import psutil
import subprocess
import requests
import aiohttp
import yt_dlp

from os import path
from typing import Union
from asyncio import QueueEmpty
from PIL import Image, ImageFont, ImageDraw
from typing import Callable

from pytgcalls import StreamType
from pytgcalls.types.input_stream import InputStream
from pytgcalls.types.input_stream import InputAudioStream

from youtube_search import YoutubeSearch

from pyrogram import Client, filters
from pyrogram.types import Message, Voice, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserAlreadyParticipant, UserNotParticipant

from oda.tgcalls import calls, queues
from oda.tgcalls.calls import client as ASS_ACC
from oda.database.queue import (
    get_active_chats,
    is_active_chat,
    add_active_chat,
    remove_active_chat,
    music_on,
    is_music_playing,
    music_off,
)
from oda import app
import oda.tgcalls
from oda.tgcalls import youtube
from oda.config import DURATION_LIMIT, que, SUDO_USERS, BOT_ID, ASSNAME, ASSUSERNAME, ASSID, SUPPORT, UPDATE
from oda.utils.filters import command
from oda.utils.decorators import errors, sudo_users_only
from oda.utils.administrator import adminsOnly
from oda.utils.errors import DurationLimitError
from oda.utils.gets import get_url, get_file_name
from oda.modules.admins import member_permissions



# plus
chat_id = None
DISABLED_GROUPS = []
useer = "NaN"
flex = {}


def transcode(filename):
    ffmpeg.input(filename).output(
        "input.raw", format="s16le", acodec="pcm_s16le", ac=2, ar="48k"
    ).overwrite_output().run()
    os.remove(filename)


# Convert seconds to mm:ss
def convert_seconds(seconds):
    seconds = seconds % (24 * 3600)
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%02d:%02d" % (minutes, seconds)


# Convert hh:mm:ss to seconds
def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


# Change image size
def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    return image.resize((newWidth, newHeight))


async def generate_cover(requested_by, title, views, duration, thumbnail):
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                f = await aiofiles.open("background.png", mode="wb")
                await f.write(await resp.read())
                await f.close()

    image1 = Image.open("./background.png")
    image2 = Image.open("etc/foreground.png")
    image3 = changeImageSize(1280, 720, image1)
    image4 = changeImageSize(1280, 720, image2)
    image5 = image3.convert("RGBA")
    image6 = image4.convert("RGBA")
    Image.alpha_composite(image5, image6).save("temp.png")
    img = Image.open("temp.png")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("etc/font.otf", 32)
    draw.text((190, 550), f"Title: {title}", (255, 255, 255), font=font)
    draw.text((190, 590), f"Duration: {duration}", (255, 255, 255), font=font)
    draw.text((190, 630), f"Views: {views}", (255, 255, 255), font=font)
    draw.text(
        (190, 670),
        f"Added By: {requested_by}",
        (255, 255, 255),
        font=font,
    )
    img.save("final.png")
    os.remove("temp.png")
    os.remove("background.png")


@Client.on_message(
    command(["musicplayer", "musicplayer@OdaRobot"])
    & ~filters.edited
    & ~filters.bot
    & ~filters.private
)
async def hfmm(_, message):
    global DISABLED_GROUPS
    if message.sender_chat:
        return await message.reply_text("You're an __Anonymous Admin__!\nRevert back to User Account.") 
    permission = "can_delete_messages"
    m = await adminsOnly(permission, message)
    if m == 1:
        return
    try:
        user_id = message.from_user.id
    except:
        return
    if len(message.command) != 2:
        await message.reply_text(
            "I only recognize `/musicplayer on` and /musicplayer `off only`"
        )
        return
    status = message.text.split(None, 1)[1]
    message.chat.id
    if status in ["ON", "on", "On"]:
        lel = await message.reply("`Processing...`")
        if message.chat.id not in DISABLED_GROUPS:
            await lel.edit("Music Player Already Activated In This Chat")
            return
        DISABLED_GROUPS.remove(message.chat.id)
        await lel.edit(f"Music Player Successfully Enabled in **{message.chat.title}**")

    elif status in ["OFF", "off", "Off"]:
        lel = await message.reply("`Processing...`")

        if message.chat.id in DISABLED_GROUPS:
            await lel.edit("Music Player Already turned off In This Chat")
            return
        DISABLED_GROUPS.append(message.chat.id)
        await lel.edit(
            f"Music Player Successfully Deactivated in **{message.chat.title}**"
        )
    else:
        await message.reply_text(
            "I only recognize `/musicplayer on` and /musicplayer `off only`"
        )


@Client.on_callback_query(filters.regex(pattern=r"^(cls)$"))
async def closed(_, query: CallbackQuery):
    from_user = query.from_user
    permissions = await member_permissions(query.message.chat.id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        return await query.answer(
            "You don't have enough permissions to perform this action.\n"
            + f"Permission needed: {permission}",
            show_alert=True,
        )
    await query.message.delete()


# play
@Client.on_message(
    command(["play", "play@OdaRobot"])
    & filters.group
    & ~filters.edited
    & ~filters.forwarded
    & ~filters.via_bot
)
async def play(_, message: Message):
    global que
    global useer
    user_id = message.from_user.id
    if message.sender_chat:
        return await message.reply_text(
            "You're an **Anonymous Admin**!\nRevert back to User Account From Admin Rights."
        )

    if message.chat.id in DISABLED_GROUPS:
        await message.reply("**Musicplayer is Disable, ask admin for Enable it!**")
        return
    lel = await message.reply("🔄 **Processing...**")

    chid = message.chat.id

    c = await app.get_chat_member(message.chat.id, BOT_ID)
    if c.status != "administrator":
        await lel.edit(
            f"I need to be admin with some permissions:\n\n- **can_manage_voice_chats:** To manage voice chats\n- **can_delete_messages:** To delete Music's Searched Waste\n- **can_invite_users**: For inviting assistant to chat\n- **can_restrict_members**: For Protecting Music from Spammers."
        )
        return
    if not c.can_manage_voice_chats:
        await lel.edit(
            "I don't have the required permission to perform this action."
            + "\n**Permission:** Manage Voice Chats"
        )
        return
    if not c.can_delete_messages:
        await lel.edit(
            "I don't have the required permission to perform this action."
            + "\n**Permission:** Delete Message"
        )
        return
    if not c.can_invite_users:
        await lel.edit(
            "I don't have the required permission to perform this action."
            + "\n**Permission:** Invite User Via Invitelink"
        )
        return
    if not c.can_restrict_members:
        await lel.edit(
            "I don't have the required permission to perform this action."
            + "\n**Permission:** Ban User"
        )
        return

    try:
        b = await app.get_chat_member(message.chat.id , ASSID) 
        if b.status == "kicked":
            await message.reply_text(f"{ASSNAME}(@{ASSUSERNAME}) is banned in your chat **{message.chat.title}**\n\nUnban it first to use Music")
            return
    except UserNotParticipant:
        if message.chat.username:
            try: 
                await ASS_ACC.join_chat(f"{message.chat.username}")
                await message.reply(f"{ASSNAME} Joined Successfully",) 
                await remove_active_chat(chat_id)
            except Exception as e:
                await message.reply_text(f"__**Assistant Failed To Join**__\n\n**Reason**:{e}")
                return
        else:
            try:
                invite_link = await message.chat.export_invite_link()
                if "+" in invite_link:
                    kontol = (invite_link.replace("+", "")).split("t.me/")[1]
                    link_bokep = f"https://t.me/joinchat/{kontol}"
                await ASS_ACC.join_chat(link_bokep)
                await message.reply(f"{ASSNAME} Joined Successfully",) 
                await remove_active_chat(message.chat.id)
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                return await message.reply_text(f"__**Assistant Failed To Join**__\n\n**Reason**:{e}")

    audio = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    url = get_url(message)

    if audio:
        if round(audio.duration / 60) > DURATION_LIMIT:
            raise DurationLimitError(
                f"❌ Videos longer than {DURATION_LIMIT} minutes aren't allowed to play!"
            )

        file_name = get_file_name(audio)
        title = audio.title
        thumb_name = "https://telegra.ph/file/a7adee6cf365d74734c5d.png"
        thumbnail = thumb_name
        duration = round(audio.duration / 60)
        views = "Locally added"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🚨 Support", url=f"t.me/{SUPPORT}"),
                    InlineKeyboardButton("📡 Updates", url=f"t.me/{UPDATE}"),
                ],
                [InlineKeyboardButton(text="🗑 Close", callback_data="cls")],
            ]
        )

        requested_by = message.from_user.first_name
        await generate_cover(requested_by, title, views, duration, thumbnail)
        file_path = await oda.tgcalls.convert(
            (await message.reply_to_message.download(file_name))
            if not path.isfile(path.join("downloads", file_name))
            else file_name
        )

    elif url:
        try:
            results = YoutubeSearch(url, max_results=1).to_dict()
            # print results
            title = results[0]["title"]
            thumbnail = results[0]["thumbnails"][0]
            thumb_name = f"thumb{title}.jpg"
            thumb = requests.get(thumbnail, allow_redirects=True)
            open(thumb_name, "wb").write(thumb.content)
            duration = results[0]["duration"]
            url_suffix = results[0]["url_suffix"]
            views = results[0]["views"]
            durl = url
            durl = durl.replace("youtube", "youtubepp")

            secmul, dur, dur_arr = 1, 0, duration.split(":")
            for i in range(len(dur_arr) - 1, -1, -1):
                dur += int(dur_arr[i]) * secmul
                secmul *= 60

            keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🚨 Support", url=f"t.me/{SUPPORT}"),
                    InlineKeyboardButton("📡 Updates", url=f"t.me/{UPDATE}"),
                ],
                [InlineKeyboardButton(text="🗑 Close", callback_data="cls")],
            ]
        )

        except Exception as e:
            title = "NaN"
            thumb_name = "https://telegra.ph/file/a7adee6cf365d74734c5d.png"
            duration = "NaN"
            views = "NaN"
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="YouTube 🎬", url="https://youtube.com")]]
            )

        if (dur / 60) > DURATION_LIMIT:
            await lel.edit(
                f"❌ Videos longer than {DURATION_LIMIT} minutes aren't allowed to play!"
            )
            return
        requested_by = message.from_user.first_name
        await generate_cover(requested_by, title, views, duration, thumbnail)

        def my_hook(d):
            if d["status"] == "downloading":
                percentage = d["_percent_str"]
                per = (str(percentage)).replace(".", "", 1).replace("%", "", 1)
                per = int(per)
                eta = d["eta"]
                speed = d["_speed_str"]
                size = d["_total_bytes_str"]
                bytesx = d["total_bytes"]
                if str(bytesx) in flex:
                    pass
                else:
                    flex[str(bytesx)] = 1
                if flex[str(bytesx)] == 1:
                    flex[str(bytesx)] += 1
                    try:
                        if eta > 2:
                            lel.edit(
                                f"Downloading {title[:50]}\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                    except Exception as e:
                        pass
                if per > 250:
                    if flex[str(bytesx)] == 2:
                        flex[str(bytesx)] += 1
                        if eta > 2:
                            lel.edit(
                                f"**Downloading** {title[:50]}..\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                        print(
                            f"[{url_suffix}] Downloaded {percentage} at a speed of {speed} | ETA: {eta} seconds"
                        )
                if per > 500:
                    if flex[str(bytesx)] == 3:
                        flex[str(bytesx)] += 1
                        if eta > 2:
                            lel.edit(
                                f"**Downloading** {title[:50]}...\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                        print(
                            f"[{url_suffix}] Downloaded {percentage} at a speed of {speed} | ETA: {eta} seconds"
                        )
                if per > 800:
                    if flex[str(bytesx)] == 4:
                        flex[str(bytesx)] += 1
                        if eta > 2:
                            lel.edit(
                                f"**Downloading** {title[:50]}....\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                        print(
                            f"[{url_suffix}] Downloaded {percentage} at a speed of {speed} | ETA: {eta} seconds"
                        )
            if d["status"] == "finished":
                try:
                    taken = d["_elapsed_str"]
                except Exception as e:
                    taken = "00:00"
                size = d["_total_bytes_str"]
                lel.edit(
                    f"**Downloaded** {title[:50]}.....\n\n**FileSize:** {size}\n**Time Taken:** {taken} sec\n\n**Converting File**[__FFmpeg processing__]"
                )
                print(f"[{url_suffix}] Downloaded| Elapsed: {taken} seconds")

        loop = asyncio.get_event_loop()
        x = await loop.run_in_executor(None, youtube.download, url, my_hook)
        file_path = await oda.tgcalls.convert(x)
    else:
        if len(message.command) < 2:
            return await lel.edit(
                "🧐 **Song not found! Try searching with the correct title\nExample » /play In The End\n\nChannel : @UserLazyXBot**"
            )
        await lel.edit("🔎 **Finding the song...**")
        query = message.text.split(None, 1)[1]
        # print(query)
        await lel.edit("🎵 **Processing sounds...**")
        try:
            results = YoutubeSearch(query, max_results=5).to_dict()
            url = f"https://youtube.com{results[0]['url_suffix']}"
            # print results
            title = results[0]["title"]
            thumbnail = results[0]["thumbnails"][0]
            thumb_name = f"thumb{title}.jpg"
            thumb = requests.get(thumbnail, allow_redirects=True)
            open(thumb_name, "wb").write(thumb.content)
            duration = results[0]["duration"]
            url_suffix = results[0]["url_suffix"]
            views = results[0]["views"]
            durl = url
            durl = durl.replace("youtube", "youtubepp")

            secmul, dur, dur_arr = 1, 0, duration.split(":")
            for i in range(len(dur_arr) - 1, -1, -1):
                dur += int(dur_arr[i]) * secmul
                secmul *= 60

        except Exception as e:
            await lel.edit(
                "❌ Song not found.\n\nTry another song or maybe spell it properly."
            )
            print(str(e))
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🚨 Support", url=f"t.me/{SUPPORT}"),
                    InlineKeyboardButton("📡 Updates", url=f"t.me/{UPDATE}"),
                ],
                [InlineKeyboardButton(text="🗑 Close", callback_data="cls")],
            ]
        )

        if (dur / 60) > DURATION_LIMIT:
            await lel.edit(
                f"❌ Videos longer than {DURATION_LIMIT} minutes aren't allowed to play!"
            )
            return
        requested_by = message.from_user.first_name
        await generate_cover(requested_by, title, views, duration, thumbnail)

        def my_hook(d):
            if d["status"] == "downloading":
                percentage = d["_percent_str"]
                per = (str(percentage)).replace(".", "", 1).replace("%", "", 1)
                per = int(per)
                eta = d["eta"]
                speed = d["_speed_str"]
                size = d["_total_bytes_str"]
                bytesx = d["total_bytes"]
                if str(bytesx) in flex:
                    pass
                else:
                    flex[str(bytesx)] = 1
                if flex[str(bytesx)] == 1:
                    flex[str(bytesx)] += 1
                    try:
                        if eta > 2:
                            lel.edit(
                                f"Downloading {title[:50]}\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                    except Exception as e:
                        pass
                if per > 250:
                    if flex[str(bytesx)] == 2:
                        flex[str(bytesx)] += 1
                        if eta > 2:
                            lel.edit(
                                f"**Downloading** {title[:50]}..\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                        print(
                            f"[{url_suffix}] Downloaded {percentage} at a speed of {speed} | ETA: {eta} seconds"
                        )
                if per > 500:
                    if flex[str(bytesx)] == 3:
                        flex[str(bytesx)] += 1
                        if eta > 2:
                            lel.edit(
                                f"**Downloading** {title[:50]}...\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                        print(
                            f"[{url_suffix}] Downloaded {percentage} at a speed of {speed} | ETA: {eta} seconds"
                        )
                if per > 800:
                    if flex[str(bytesx)] == 4:
                        flex[str(bytesx)] += 1
                        if eta > 2:
                            lel.edit(
                                f"**Downloading** {title[:50]}....\n\n**FileSize:** {size}\n**Downloaded:** {percentage}\n**Speed:** {speed}\n**ETA:** {eta} sec"
                            )
                        print(
                            f"[{url_suffix}] Downloaded {percentage} at a speed of {speed} | ETA: {eta} seconds"
                        )
            if d["status"] == "finished":
                try:
                    taken = d["_elapsed_str"]
                except Exception as e:
                    taken = "00:00"
                size = d["_total_bytes_str"]
                lel.edit(
                    f"**Downloaded** {title[:50]}.....\n\n**FileSize:** {size}\n**Time Taken:** {taken} sec\n\n**Converting File**[__FFmpeg processing__]"
                )
                print(f"[{url_suffix}] Downloaded| Elapsed: {taken} seconds")

        loop = asyncio.get_event_loop()
        x = await loop.run_in_executor(None, youtube.download, url, my_hook)
        file_path = await oda.tgcalls.convert(x)

    if await is_active_chat(message.chat.id):
        position = await queues.put(message.chat.id, file=file_path)
        await message.reply_photo(
            photo="final.png",
            caption="**🎵 Song:** {}\n**🕒 Duration:** {} min\n**👤 Added By:** {}\n\n**#⃣ Queued Position:** {}".format(
                title,
                duration,
                message.from_user.mention(),
                position,
            ),
            reply_markup=keyboard,
        )
    else:
        await music_on(message.chat.id)
        await add_active_chat(message.chat.id)
        await calls.pytgcalls.join_group_call(
            message.chat.id,
            InputStream(
                InputAudioStream(
                    file_path,
                ),
            ),
            stream_type=StreamType().local_stream,
        )
        await message.reply_photo(
            photo="final.png",
            reply_markup=keyboard,
            caption="**🎵 Song:** {}\n**🕒 Duration:** {} min\n**👤 Added By:** {}\n\n**▶️ Now Playing at `{}`...**".format(
                title, duration, message.from_user.mention(), message.chat.title
            ),
        )

    os.remove("final.png")
    return await lel.delete()
