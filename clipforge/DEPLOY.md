# 🎬 ClipForge — Deploy Guide

## Fastest: Deploy to Railway (free tier, 5 minutes)

**Railway gives you a live URL for free with one click.**

### Steps

1. **Create a free account** at [railway.app](https://railway.app)

2. **Push this folder to GitHub**
   ```bash
   cd clipforge
   git init
   git add .
   git commit -m "ClipForge initial commit"
   # Create a new repo on github.com, then:
   git remote add origin https://github.com/YOUR_USERNAME/clipforge.git
   git push -u origin main
   ```

3. **Deploy on Railway**
   - Click **"New Project"** → **"Deploy from GitHub repo"**
   - Select your `clipforge` repo
   - Railway auto-detects the Dockerfile and builds it

4. **Add your API key** (optional — users can paste their own in the UI)
   - In Railway dashboard → your project → **Variables**
   - Add: `ANTHROPIC_API_KEY` = `sk-ant-...`
   - If set, users don't need to enter their own key

5. **Go live!**
   - Railway gives you a URL like `clipforge-production.up.railway.app`
   - Share it with anyone

---

## Alternative: Deploy to Render (free tier)

1. Create account at [render.com](https://render.com)
2. Click **"New"** → **"Web Service"**
3. Connect your GitHub repo
4. Render auto-reads `render.yaml` — just click **Deploy**
5. Add `ANTHROPIC_API_KEY` in Environment settings

---

## Run Locally

```bash
# Prerequisites
brew install ffmpeg          # macOS
# sudo apt install ffmpeg   # Linux
pip3 install yt-dlp

# Run
cd clipforge
pip3 install -r requirements.txt
python app.py
# → http://localhost:5000
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Pre-fills the API key on the server — users don't need to enter theirs | Optional |
| `PORT` | Port to run on (default: 5000) | Optional |

If `ANTHROPIC_API_KEY` is NOT set, users paste their own key in the UI. Both modes work.

---

## Notes

- The Dockerfile installs `ffmpeg` and `yt-dlp` automatically
- Clips are stored in `static/clips/` — on cloud deploys, use a persistent disk
- Railway Starter plan: 512MB RAM, may struggle with 1080p on very long videos — use 720p
- On Render free tier, the server sleeps after 15 min of inactivity (first request is slow)
- For production use, consider Railway Pro ($20/mo) or a VPS with 2GB+ RAM
