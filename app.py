import os
import asyncio
import time
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
PRUEBAS_CHANNEL_ID = int(os.getenv("PRUEBAS_CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

EMBED_COLORS = {
    "music": 0x9B59B6,
    "success": 0x2ECC71,
    "error": 0xE74C3C,
    "info": 0x3498DB,
    "warning": 0xF39C12,
}


def _embed(title: str, description: str = "", color: int = 0x9B59B6) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)

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
    await ctx.send(embed=_embed("Now Playing", f"**{track['title']}** [{duration}]", EMBED_COLORS["music"]))


leave_tasks: dict[int, asyncio.Task] = {}

SPAM_WINDOW = 30
SPAM_CHANNEL_THRESHOLD = 3
spam_tracker: dict[int, list[tuple[str, int, int, float]]] = {}


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    if not PRUEBAS_CHANNEL_ID:
        return

    user_id = message.author.id
    content = message.content.strip()
    if not content:
        return

    now = time.time()
    entries = spam_tracker.get(user_id, [])
    entries = [
        (c, ch, mid, ts) for c, ch, mid, ts in entries if now - ts <= SPAM_WINDOW
    ]
    entries.append((content, message.channel.id, message.id, now))
    spam_tracker[user_id] = entries

    channels_with_same = set()
    msgs_same_content = []
    for c, ch, mid, ts in entries:
        if c == content:
            channels_with_same.add(ch)
            msgs_same_content.append((ch, mid))

    if len(channels_with_same) < SPAM_CHANNEL_THRESHOLD:
        return

    pruebas_channel = bot.get_channel(PRUEBAS_CHANNEL_ID)
    deleted_count = 0
    delete_failed = 0

    for ch_id, msg_id in msgs_same_content:
        if ch_id == PRUEBAS_CHANNEL_ID:
            continue
        channel = bot.get_channel(ch_id)
        if not channel:
            continue
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.delete()
            deleted_count += 1
        except discord.NotFound:
            pass
        except discord.Forbidden:
            delete_failed += 1
        except discord.HTTPException:
            delete_failed += 1

    spam_tracker.pop(user_id, None)

    if pruebas_channel:
        channel_list = ", ".join(f"<#{cid}>" for cid in channels_with_same)
        embed = _embed(
            "⚠ Posible Cuenta Hackeada",
            f"**Usuario:** {message.author.mention} (`{message.author.id}`)\n"
            f"**Canales afectados ({len(channels_with_same)}):** {channel_list}\n"
            f"**Mensajes eliminados:** {deleted_count}\n"
            f"**Contenido:**\n>>> {content[:1500]}",
            EMBED_COLORS["warning"],
        )
        embed.set_footer(text="Anti-spam automático")
        await pruebas_channel.send(embed=embed)


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


@bot.command(name="sd")
async def sd(ctx, *, texto: str):
    if not texto:
        await ctx.send(embed=_embed("Uso", "Debes escribir un texto.\nUso: `!sd <texto>`", EMBED_COLORS["warning"]))
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send(embed=_embed("Error", "Debes estar en un canal de voz para usar este comando.", EMBED_COLORS["error"]))
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

        user_msg = ctx.message
        try:
            await user_msg.delete()
        except Exception as e:
            print(f"Error al borrar mensaje del usuario: {type(e).__name__}: {e}")

        async def _cleanup():
            try:
                os.remove(filename)
            except Exception:
                pass

        def after_play(error):
            if error:
                print(f"Error de reproducción: {error}")
            asyncio.run_coroutine_threadsafe(_cleanup(), bot.loop)

        source = discord.FFmpegPCMAudio(filename)
        voice_client.play(source, after=after_play)

    except Exception as e:
        print(f"Error al generar audio: {e}")


@bot.command(name="setvoz")
async def setvoz(ctx, voice_id: str):
    global VOICE_ID
    VOICE_ID = voice_id
    await ctx.send(embed=_embed("Voz Actualizada", f"Voz cambiada a ID: `{voice_id}`", EMBED_COLORS["success"]))


@bot.command(name="leave")
async def leave(ctx):
    music_queues.pop(ctx.guild.id, None)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send(embed=_embed("Desconectado", "Desconectado del canal de voz.", EMBED_COLORS["info"]))
    else:
        await ctx.send(embed=_embed("Error", "No estoy en un canal de voz.", EMBED_COLORS["error"]))


@bot.command(name="pley")
async def play(ctx, *, url: str):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send(embed=_embed("Error", "Debes estar en un canal de voz para usar este comando.", EMBED_COLORS["error"]))
        return

    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_connected():
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect(self_deaf=False)

    msg = await ctx.send(embed=_embed("Buscando", "Buscando audio...", EMBED_COLORS["info"]))

    try:
        track = await asyncio.to_thread(_extract_info, url)
    except Exception as e:
        await msg.edit(embed=_embed("Error", f"Error al obtener info del video: {e}", EMBED_COLORS["error"]))
        return

    if not track or not track["url"]:
        await msg.edit(embed=_embed("Error", "No se pudo obtener el audio del link proporcionado.", EMBED_COLORS["error"]))
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
            embed=_embed("Agregado a la Cola", f"**{track['title']}** [{duration}]\nPosicion: {len(queue)}", EMBED_COLORS["success"])
        )
        return

    queue.append(track)
    await msg.edit(embed=_embed("Reproduciendo", f"**{track['title']}**", EMBED_COLORS["music"]))
    await _play_next(ctx)


@bot.command(name="skip")
async def skip(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("No estoy reproduciendo nada.")
        return

    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send(embed=_embed("Saltado", "Cancion saltada.", EMBED_COLORS["info"]))
    else:
        await ctx.send(embed=_embed("Error", "No hay nada reproduciendose ahora.", EMBED_COLORS["error"]))


@bot.command(name="stop")
async def stop(ctx):
    music_queues.pop(ctx.guild.id, None)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        voice_client.stop()
        await ctx.send(embed=_embed("Detenido", "Reproduccion detenida y cola limpiada.", EMBED_COLORS["info"]))
    else:
        await ctx.send(embed=_embed("Error", "No estoy en un canal de voz.", EMBED_COLORS["error"]))


@bot.command(name="queue")
async def queue_cmd(ctx):
    q = _get_queue(ctx.guild.id)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not q and (not voice_client or not voice_client.is_playing()):
        await ctx.send(embed=_embed("Cola Vacia", "No hay canciones en la cola.", EMBED_COLORS["warning"]))
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
    await ctx.send(embed=_embed("Cola de Reproduccion", content, EMBED_COLORS["music"]))


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
