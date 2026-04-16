import os
import asyncio
import discord
import yt_dlp
from collections import deque
from discord.ext import commands
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

music_queues: dict[int, deque[dict]] = {}

YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "cookiefile": os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "cookies.txt"
    ),
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

if not discord.opus.is_loaded():
    discord.opus.load_opus("/lib/x86_64-linux-gnu/libopus.so.0")


def _get_queue(guild_id: int) -> deque[dict]:
    if guild_id not in music_queues:
        music_queues[guild_id] = deque()
    return music_queues[guild_id]


def _extract_info(url: str) -> dict | None:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        if "entries" in info:
            info = info["entries"][0]
        return {
            "title": info.get("title", "Desconocido"),
            "url": info.get("url"),
            "webpage_url": info.get("webpage_url", url),
            "duration": info.get("duration"),
        }


async def _play_next(ctx: commands.Context):
    queue = _get_queue(ctx.guild.id)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not queue or not voice_client or not voice_client.is_connected():
        return

    track = queue.popleft()
    source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTS)

    def after_play(error):
        if error:
            print(f"Error de reproducción: {error}")
        asyncio.run_coroutine_threadsafe(_play_next(ctx), bot.loop)

    voice_client.play(source, after=after_play)
    duration = (
        f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
        if track["duration"]
        else "?"
    )
    await ctx.send(f"Now playing: **{track['title']}** [{duration}]")


leave_tasks: dict[int, asyncio.Task] = {}


@bot.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    if member.id == bot.user.id:
        return

    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if not voice_client or not voice_client.is_connected():
        return

    channel = voice_client.channel
    humans = [m for m in channel.members if not m.bot]

    if humans:
        task = leave_tasks.pop(member.guild.id, None)
        if task and not task.done():
            task.cancel()
        return

    if member.guild.id in leave_tasks and not leave_tasks[member.guild.id].done():
        return

    async def _leave_after_timeout():
        await asyncio.sleep(5)
        voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
        if not voice_client or not voice_client.is_connected():
            return
        channel = voice_client.channel
        humans = [m for m in channel.members if not m.bot]
        if not humans:
            music_queues.pop(member.guild.id, None)
            await voice_client.disconnect()

    leave_tasks[member.guild.id] = asyncio.create_task(_leave_after_timeout())


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user} | Voz: {VOICE_ID}")


@bot.command(name="tts")
async def tts(ctx, *, texto: str):
    if not texto:
        await ctx.send("Debes escribir un texto. Uso: `!tts <texto>`")
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Debes estar en un canal de voz para usar este comando.")
        return

    voice_channel = ctx.author.voice.channel
    print("Generando audio...")

    try:
        audio = client.text_to_speech.convert(
            text=texto,
            voice_id=VOICE_ID,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        filename = f"tts_{ctx.message.id}.mp3"
        with open(filename, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_connected():
            if voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
            if voice_client.is_playing():
                voice_client.stop()
        else:
            voice_client = await voice_channel.connect(self_deaf=False)

        def after_play(error):
            if error:
                print(f"Error de reproducción: {error}")
            try:
                os.remove(filename)
            except Exception:
                pass

        source = discord.FFmpegPCMAudio(filename)
        voice_client.play(source, after=after_play)

    except Exception as e:
        print(f"Error al generar audio: {e}")


@bot.command(name="setvoz")
async def setvoz(ctx, voice_id: str):
    global VOICE_ID
    VOICE_ID = voice_id
    await ctx.send(f"Voz cambiada a ID: `{voice_id}`")


@bot.command(name="leave")
async def leave(ctx):
    music_queues.pop(ctx.guild.id, None)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("Desconectado del canal de voz.")
    else:
        await ctx.send("No estoy en un canal de voz.")


@bot.command(name="pley")
async def play(ctx, *, url: str):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Debes estar en un canal de voz para usar este comando.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_connected():
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect(self_deaf=False)

    msg = await ctx.send("Buscando...")

    try:
        track = await asyncio.to_thread(_extract_info, url)
    except Exception as e:
        await msg.edit(content=f"Error al obtener info del video: {e}")
        return

    if not track or not track["url"]:
        await msg.edit(content="No se pudo obtener el audio del link proporcionado.")
        return

    queue = _get_queue(ctx.guild.id)

    if voice_client.is_playing() or queue:
        queue.append(track)
        duration = (
            f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
            if track["duration"]
            else "?"
        )
        await msg.edit(
            content=f"Agregado a la cola: **{track['title']}** [{duration}] (posicion {len(queue)})"
        )
        return

    queue.append(track)
    await msg.edit(content=f"Reproduciendo: **{track['title']}**")
    await _play_next(ctx)


@bot.command(name="skip")
async def skip(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("No estoy reproduciendo nada.")
        return

    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Saltado.")
    else:
        await ctx.send("No hay nada reproduciendose ahora.")


@bot.command(name="stop")
async def stop(ctx):
    music_queues.pop(ctx.guild.id, None)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        voice_client.stop()
        await ctx.send("Reproduccion detenida y cola limpiada.")
    else:
        await ctx.send("No estoy en un canal de voz.")


@bot.command(name="queue")
async def queue_cmd(ctx):
    q = _get_queue(ctx.guild.id)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not q and (not voice_client or not voice_client.is_playing()):
        await ctx.send("La cola esta vacia.")
        return

    lines = []
    if voice_client and voice_client.is_playing():
        lines.append("Reproduciendo ahora")

    for i, track in enumerate(q, 1):
        duration = (
            f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
            if track["duration"]
            else "?"
        )
        lines.append(f"{i}. **{track['title']}** [{duration}]")

    content = "\n".join(lines)
    if len(content) > 1900:
        content = content[:1900] + "\n..."
    await ctx.send(content)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
