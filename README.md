# 🎬 ClipForge — Viral Clip Generator

Turn any YouTube video into 30–60 viral clips, cropped to 9:16 phone format with burned-in subtitles.

## Prerequisites

Install these first:

```bash
# macOS
brew install ffmpeg python3
pip3 install yt-dlp

# Ubuntu / Debian
sudo apt install ffmpeg python3-pip
pip3 install yt-dlp

# Windows
# 1. Download ffmpeg: https://ffmpeg.org/download.html  (add to PATH)
# 2. pip install yt-dlp
```

## Setup

```bash
cd viralclips
pip3 install -r requirements.txt
```

## Run

```bash
python3 app.py
```

Then open **http://localhost:5000** in your browser.

## How it works

1. **Paste** a YouTube URL
2. **Configure** number of clips (10–60), length (10–180s), quality, subtitles
3. **Enter** your Anthropic API key (get one at console.anthropic.com)
4. **Click** Generate Clips

Behind the scenes:
- `yt-dlp` downloads the full video at your chosen quality
- Claude AI analyzes the title + duration and identifies the best viral moments
- `ffmpeg` trims each clip, crops to 9:16 phone format (centre crop for landscape video)
- If subtitles are on, the AI-generated caption text is burned directly into each clip
- All clips are saved as MP4s you can download individually or all at once

## Subtitle Styles

| Style  | Look                          |
|--------|-------------------------------|
| White  | White text, black border      |
| Yellow | Yellow text (classic captions)|
| Neon   | Neon green text               |
| Bold   | White with heavy dark box     |

## Output

Clips are saved to `static/clips/` inside the project folder.
Each clip is named: `{jobId}_{number}_{title}.mp4`

## Notes

- Large videos (1+ hour) may take several minutes to download
- Processing 40 clips takes roughly 5–15 minutes depending on your CPU
- The API key is never stored — it's only used during the job
- Videos are downloaded to `static/work/{jobId}/` and kept until you clean up
