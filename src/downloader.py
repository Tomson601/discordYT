import yt_dlp
import os

DOWNLOAD_DIR = "piosenki"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_from_youtube(link: str) -> str:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        filename = ydl.prepare_filename(info)
        mp3_file = os.path.splitext(filename)[0] + ".mp3"
        return mp3_file
