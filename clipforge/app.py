"""
ClipForge — Viral Clip Generator
Production-ready Flask backend
"""

import os, json, re, uuid, subprocess, threading, textwrap, shutil, time
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

CLIPS_DIR = Path("static/clips")
WORK_DIR  = Path("static/work")
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
WORK_DIR.mkdir(parents=True, exist_ok=True)

JOBS: dict = {}
SERVER_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Helpers ──────────────────────────────────

def ts_to_secs(ts) -> float:
    ts = str(ts).strip()
    if ":" in ts:
        parts = [float(p) for p in ts.split(":")]
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        return parts[0]*60 + parts[1]
    try: return float(ts)
    except: return 0.0

def secs_fmt(s: float) -> str:
    s = max(0.0, s)
    h=int(s//3600); m=int((s%3600)//60); sec=s%60
    return f"{h}:{m:02d}:{sec:05.2f}" if h else f"{m}:{sec:05.2f}"

def safe_name(t: str) -> str:
    return re.sub(r"[^\w\s\-]","",t).strip().replace(" ","_")[:40] or "clip"

def emit(jid, step, pct, msg):
    if jid in JOBS:
        JOBS[jid].update({"step":step,"progress":pct,"message":msg,"updatedAt":time.time()})

# ── Claude AI ────────────────────────────────

def ask_claude(api_key, url, title, duration, n, cmin, cmax):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are a viral video strategist for TikTok, Reels, and Shorts.

Find the {n} best moments to clip from this YouTube video for maximum virality.

URL: {url}
Title: "{title}"
Duration: {secs_fmt(duration)} ({int(duration)}s total)
Clip range: {cmin}–{cmax} seconds each
Format: 9:16 vertical

Return ONLY a valid JSON array. Each object:
{{
  "title": "scroll-stopping clip title, max 9 words",
  "hook": "compelling opening caption, max 18 words",
  "startTime": "M:SS",
  "endTime": "M:SS",
  "durationSecs": integer {cmin}–{cmax},
  "viralScore": integer 70–99,
  "category": one of ["hook","emotional","funny","educational","controversial","surprising","motivational","story"],
  "tags": array of 2–3 from ["tiktok","instagram","youtube","hook","emotional","funny","educational","controversial","surprising","motivational"],
  "reason": "one sentence why this goes viral",
  "subtitleText": "2–3 sentence description of what is said/shown for subtitle overlay"
}}

Rules: spread clips across FULL video, no overlapping, startTime ≤ {max(0,int(duration-cmin))}s, endTime ≤ {int(duration)}s.
Prioritise: surprising reveals, hot takes, emotional peaks, humour, controversy, quotable lines.
Return ONLY the JSON array."""

    msg = client.messages.create(model="claude-opus-4-5", max_tokens=8192,
        messages=[{"role":"user","content":prompt}])
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?","",raw); raw = re.sub(r"\n?```$","",raw)
    clips = json.loads(raw)

    valid=[]
    for c in clips:
        try:
            ss  = ts_to_secs(c.get("startTime","0"))
            es  = ts_to_secs(c.get("endTime",str(ss+cmax)))
            dur = max(cmin, min(cmax, int(c.get("durationSecs",es-ss))))
            if 0 <= ss < duration-5:
                c["startSecs"]=ss; c["endSecs"]=min(es,duration); c["durationSecs"]=dur
                valid.append(c)
        except: continue
    return valid[:n]

# ── yt-dlp download ──────────────────────────

def download_video(url, out_dir, quality, jid):
    emit(jid,"download",3,"Fetching video info…")
    info = subprocess.run(["yt-dlp","--no-playlist","--dump-json",url],
        capture_output=True, text=True, timeout=40)
    if info.returncode!=0:
        raise RuntimeError(f"Could not fetch video. Check the URL and try again.")

    data=json.loads(info.stdout)
    title=data.get("title","video"); duration=float(data.get("duration") or 0)
    vid_id=data.get("id","video")

    emit(jid,"download",8,f"Downloading: {title[:55]}…")

    fmt=(f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]"
         f"/bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best")

    proc=subprocess.Popen(
        ["yt-dlp","--no-playlist","-f",fmt,"--merge-output-format","mp4",
         "-o",str(out_dir/f"{vid_id}.%(ext)s"),url],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    last=8
    for line in proc.stdout:
        m=re.search(r"(\d+\.?\d*)%",line)
        if m:
            p=float(m.group(1)); mapped=8+int(p*0.5)
            if mapped>last: last=mapped; emit(jid,"download",mapped,f"Downloading… {p:.0f}%")
    proc.wait()
    if proc.returncode!=0:
        raise RuntimeError("Download failed. The video may be private, age-restricted, or unavailable.")

    mp4s=list(out_dir.glob(f"{vid_id}*.mp4"))
    if not mp4s:
        vids=[f for f in out_dir.glob(f"{vid_id}*") if f.suffix in(".mp4",".mkv",".webm",".mov")]
        if not vids: raise RuntimeError("Downloaded file not found.")
        mp4s=vids

    video_path=mp4s[0]
    if duration<=0:
        probe=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",str(video_path)],
            capture_output=True,text=True)
        if probe.returncode==0:
            duration=float(json.loads(probe.stdout).get("format",{}).get("duration",0))

    emit(jid,"download",60,f"Download complete — {secs_fmt(duration)}")
    return video_path, title, duration

# ── ffmpeg clip maker ────────────────────────

def make_clip(src, clip, dst, subs, sub_style):
    ss=float(clip["startSecs"]); dur=int(clip["durationSecs"])
    probe=subprocess.run(
        ["ffprobe","-v","quiet","-print_format","json","-show_streams","-select_streams","v:0",str(src)],
        capture_output=True,text=True)
    sw,sh=1920,1080
    if probe.returncode==0:
        try:
            st=json.loads(probe.stdout).get("streams",[{}])
            if st: sw=int(st[0].get("width",1920)); sh=int(st[0].get("height",1080))
        except: pass

    TW,TH=1080,1920
    if sw>sh:
        cw=int(sh*9/16)
        vf_base=f"crop={cw}:{sh}:{(sw-cw)//2}:0,scale={TW}:{TH}:flags=lanczos"
    else:
        vf_base=(f"scale={TW}:{TH}:force_original_aspect_ratio=decrease,"
                 f"pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2:black")

    vf_parts=[vf_base]
    if subs:
        raw=clip.get("subtitleText") or clip.get("hook") or ""
        lines=textwrap.wrap(raw,width=28)
        text=(r"\n".join(lines).replace("'",r"\'").replace(":",r"\:").replace("%",r"\%"))
        styles={
            "white": ("white","black","0x000000aa"),
            "yellow":("yellow","black","0x000000aa"),
            "neon":  ("0x00ff99","black","0x000000cc"),
            "bold":  ("white","0x111111","0x000000dd"),
        }
        fc,bc,bx=styles.get(sub_style,styles["white"])
        vf_parts.append(
            f"drawtext=text='{text}':fontsize=52:fontcolor={fc}"
            f":bordercolor={bc}:borderw=3:x=(w-text_w)/2:y=h*0.77"
            f":line_spacing=8:font=Arial Bold:box=1:boxcolor={bx}:boxborderw=14")

    cmd=["ffmpeg","-y","-ss",str(ss),"-i",str(src),"-t",str(dur),
         "-vf",",".join(vf_parts),"-c:v","libx264","-preset","fast","-crf","23",
         "-c:a","aac","-b:a","128k","-movflags","+faststart",
         "-avoid_negative_ts","make_zero",str(dst)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=360)
    if r.returncode!=0: raise RuntimeError(f"ffmpeg: {r.stderr[-200:]}")
    return dst

# ── Job runner ───────────────────────────────

def run_job(jid, payload):
    try:
        api_key  = payload.get("apiKey") or SERVER_API_KEY
        url      = payload["url"]
        n        = min(60, max(5, int(payload.get("numClips",40))))
        cmin     = int(payload.get("clipMin",30))
        cmax     = int(payload.get("clipMax",60))
        quality  = str(payload.get("quality","720"))
        subs     = bool(payload.get("addSubtitles",True))
        style    = str(payload.get("subtitleStyle","white"))

        if not api_key: raise RuntimeError("No Anthropic API key provided.")

        job_dir=WORK_DIR/jid; job_dir.mkdir(parents=True,exist_ok=True)
        JOBS[jid]["status"]="running"

        video_path,title,duration = download_video(url,job_dir,quality,jid)
        JOBS[jid]["title"]=title; JOBS[jid]["duration"]=round(duration)

        emit(jid,"analyze",62,"AI analyzing viral moments…")
        clips=ask_claude(api_key,url,title,duration,n,cmin,cmax)
        JOBS[jid]["totalClips"]=len(clips)
        emit(jid,"analyze",68,f"Found {len(clips)} viral moments")

        done=[]
        for i,clip in enumerate(clips):
            emit(jid,"clips",68+int(i/len(clips)*29),
                 f"Clip {i+1}/{len(clips)}: {clip.get('title','')[:35]}…")
            fname=f"{jid}_{i+1:02d}_{safe_name(clip.get('title','clip'))}.mp4"
            dst=CLIPS_DIR/fname
            try:
                make_clip(video_path,clip,dst,subs,style)
                mb=round(dst.stat().st_size/(1024*1024),1)
                clip.update({"filename":fname,"url":f"/static/clips/{fname}",
                             "index":i+1,"status":"done","sizeMb":mb})
            except Exception as e:
                clip.update({"index":i+1,"status":"error","error":str(e)[:180]})
            done.append(clip); JOBS[jid]["clips"]=done

        ok=sum(1 for c in done if c["status"]=="done")
        emit(jid,"done",100,f"Done! {ok} clips ready to download")
        JOBS[jid]["status"]="done"

    except Exception as e:
        JOBS[jid].update({"status":"error","error":str(e),"message":f"Error: {str(e)[:250]}"})

# ── Routes ───────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", has_server_key=bool(SERVER_API_KEY))

@app.route("/health")
def health():
    return jsonify({"ok":True,"hasServerKey":bool(SERVER_API_KEY)})

@app.route("/static/clips/<path:filename>")
def serve_clip(filename):
    return send_from_directory(CLIPS_DIR, filename)

@app.route("/api/start", methods=["POST"])
def api_start():
    p=request.json or {}
    api_key=p.get("apiKey") or SERVER_API_KEY
    if not api_key: return jsonify({"error":"Anthropic API key required"}),400
    if not p.get("url"): return jsonify({"error":"YouTube URL required"}),400
    jid=str(uuid.uuid4())[:8]
    JOBS[jid]={"status":"queued","step":"start","progress":0,"message":"Starting…",
               "clips":[],"totalClips":0,"title":"","duration":0,"error":"",
               "createdAt":time.time(),"updatedAt":time.time()}
    threading.Thread(target=run_job,args=(jid,p),daemon=True).start()
    return jsonify({"jobId":jid})

@app.route("/api/status/<jid>")
def api_status(jid):
    j=JOBS.get(jid)
    if not j: return jsonify({"error":"Job not found"}),404
    return jsonify(j)

@app.route("/api/server-key")
def api_server_key():
    return jsonify({"hasKey":bool(SERVER_API_KEY)})

@app.route("/api/cleanup/<jid>", methods=["DELETE"])
def api_cleanup(jid):
    job_dir=WORK_DIR/jid
    if job_dir.exists(): shutil.rmtree(job_dir,ignore_errors=True)
    for f in CLIPS_DIR.glob(f"{jid}_*.mp4"): f.unlink(missing_ok=True)
    JOBS.pop(jid,None)
    return jsonify({"ok":True})

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    print(f"\n🎬  ClipForge  →  http://localhost:{port}\n")
    app.run(debug=False,host="0.0.0.0",port=port,threaded=True)
