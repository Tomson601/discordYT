import discord
from discord.ext import commands
import asyncio
import os
from downloader import download_from_youtube
import json
import re
import logging
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

SONGS_FILE = "songs.json"
MAX_QUEUE_LENGTH = 10
song_queue = []

# Logging
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def load_songs():
    if os.path.exists(SONGS_FILE):
        with open(SONGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_songs(songs):
    with open(SONGS_FILE, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)

def is_youtube_url(url):
    pattern = r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$"
    return re.match(pattern, url)

@bot.command(name="play")
async def play(ctx, url: str):
    if not ctx.author.voice:
        await ctx.send("Dołącz najpierw do kanału głosowego.")
        return

    if not is_youtube_url(url):
        await ctx.send("❌ Podaj poprawny link do YouTube.")
        return

    if len(song_queue) >= MAX_QUEUE_LENGTH:
        await ctx.send(f"❌ Kolejka jest pełna (max {MAX_QUEUE_LENGTH}).")
        return

    voice_channel = ctx.author.voice.channel
    try:
        if ctx.voice_client is None:
            vc = await voice_channel.connect()
        else:
            vc = ctx.voice_client
            await vc.move_to(voice_channel)
    except Exception as e:
        await ctx.send(f"❌ Nie mogę połączyć się z kanałem: {e}")
        logging.error(f"Błąd połączenia z kanałem: {e}")
        return

    # Jeśli coś gra, pobierz piosenkę i dodaj do kolejki
    if vc.is_playing() or vc.is_paused():
        songs = load_songs()
        file_path = songs.get(url)
        if not (file_path and os.path.exists(file_path)):
            await ctx.send("📥 Pobieram piosenkę do kolejki...")
            try:
                file_path = await asyncio.to_thread(download_from_youtube, url)
                songs[url] = file_path
                save_songs(songs)
                await ctx.send("✅ Piosenka pobrana i dodana do kolejki!")
            except Exception as e:
                await ctx.send(f"❌ Błąd pobierania: {e}")
                logging.error(f"Błąd pobierania do kolejki: {e}")
                return
        song_queue.append(url)
        await ctx.send("🎶 Dodano do kolejki!")
        return

    await play_song(ctx, url)

async def play_song(ctx, url):
    vc = ctx.voice_client
    songs = load_songs()
    file_path = songs.get(url)

    if file_path and os.path.exists(file_path):
        await ctx.send("▶️ Odtwarzam pobraną wcześniej piosenkę!")
    else:
        await ctx.send("📥 Pobieram piosenkę...")
        try:
            file_path = await asyncio.to_thread(download_from_youtube, url)
            songs[url] = file_path
            save_songs(songs)
            await ctx.send("▶️ Odtwarzam piosenkę!")
        except Exception as e:
            await ctx.send(f"❌ Błąd: {e}")
            logging.error(f"Błąd pobierania: {e}")
            return

    def after_playing(error):
        if error:
            logging.error(f"Błąd odtwarzania: {error}")
        fut = asyncio.run_coroutine_threadsafe(play_next(ctx, file_path), bot.loop)
        try:
            fut.result()
        except Exception as e:
            logging.error(f"Błąd kolejki: {e}")

    try:
        vc.play(discord.FFmpegPCMAudio(file_path), after=after_playing)
    except Exception as e:
        await ctx.send(f"❌ Nie można odtworzyć pliku: {e}")
        logging.error(f"Błąd odtwarzania pliku: {e}")

async def play_next(ctx, last_file_path=None):
    # Usuwanie pliku audio po odtworzeniu
    if last_file_path and os.path.exists(last_file_path):
        try:
            os.remove(last_file_path)
            songs = load_songs()
            for url, path in list(songs.items()):
                if path == last_file_path:
                    del songs[url]
            save_songs(songs)
        except Exception as e:
            logging.error(f"Błąd usuwania pliku: {e}")

    if song_queue:
        next_url = song_queue.pop(0)
        await play_song(ctx, next_url)
    else:
        await ctx.send("Kolejka zakończona.")
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

@bot.command(name="stop")
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Rozłączono.")
        song_queue.clear()
    else:
        await ctx.send("Nie jestem połączony.")

@bot.command(name="skip")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        await ctx.send("⏭️ Pomijam utwór...")
        ctx.voice_client.stop()
    else:
        await ctx.send("Nic nie jest aktualnie odtwarzane.")

@bot.command(name="queue")
async def queue(ctx):
    if not song_queue:
        await ctx.send("🎵 Kolejka jest pusta.")
    else:
        msg = "🎶 Kolejka piosenek:\n"
        for i, url in enumerate(song_queue, 1):
            msg += f"{i}. {url}\n"
        await ctx.send(msg)

@bot.command(name="clear")
async def clear(ctx):
    global song_queue
    song_queue.clear()
    await ctx.send("🧹 Kolejka została wyczyszczona.")

@bot.command(name="pause")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Wstrzymano odtwarzanie.")
    else:
        await ctx.send("Nic nie jest aktualnie odtwarzane.")

@bot.command(name="resume")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Wznowiono odtwarzanie.")
    else:
        await ctx.send("Nic nie jest wstrzymane.")

from discord.ext.commands import DefaultHelpCommand
class CustomHelpCommand(DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        help_text = (
            "Dostępne komendy:\n"
            "`!play <link>` - odtwarza lub dodaje piosenkę do kolejki\n"
            "`!queue` - pokazuje kolejkę\n"
            "`!skip` - pomija utwór\n"
            "`!stop` - rozłącza bota\n"
            "`!clear` - czyści kolejkę\n"
            "`!pause` - pauzuje odtwarzanie\n"
            "`!resume` - wznawia odtwarzanie\n"
            "`!help` - pokazuje pomoc"
        )
        channel = self.get_destination()
        await channel.send(help_text)

bot.help_command = CustomHelpCommand()

@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user}")
    logging.info(f"Bot zalogowany jako {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Nieznana komenda. Użyj `!help` aby zobaczyć dostępne komendy.")
    else:
        await ctx.send(f"❌ Błąd: {error}")
        logging.error(f"Błąd komendy: {error}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ Brak tokena w pliku .env (DISCORD_TOKEN)")
    exit(1)
bot.run(TOKEN)
