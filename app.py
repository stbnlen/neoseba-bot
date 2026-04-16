import os
import asyncio
import discord
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

if not discord.opus.is_loaded():
    discord.opus.load_opus("/lib/x86_64-linux-gnu/libopus.so.0")


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
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("Desconectado del canal de voz.")
    else:
        await ctx.send("No estoy en un canal de voz.")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
