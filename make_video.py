import os, json, subprocess, requests, asyncio, urllib.parse, time, datetime
import edge_tts

KEY = os.environ["GEMINI_API_KEY"]
topics = [t for t in open("topics.txt").read().splitlines() if t.strip()]
topic = topics[datetime.date.today().timetuple().tm_yday % len(topics)]

prompt = f"""Write a short kids nursery rhyme: {topic}.
Return ONLY JSON with keys:
title (YouTube title under 90 chars, ending with | Rock Block Rhymes),
description (3 short lines plus hashtags),
lyrics (8 to 12 short lines in one string, separated by newlines),
scenes (list of 6 image prompts, each: 3D Pixar style, cute 3 year old boy Johnny,
curly black hair, yellow t-shirt, blue shorts, bright colorful background, plus the scene action)."""

r = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
    headers={"x-goog-api-key": KEY},
    json={"contents": [{"parts": [{"text": prompt}]}],
          "generationConfig": {"responseMimeType": "application/json"}},
    timeout=120)
if "candidates" not in r.json():
    raise SystemExit(r.text)
data = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])

os.makedirs("out", exist_ok=True)
open("out/info.txt", "w").write(data["title"] + "\n\n" + data["description"] + "\n\n" + data["lyrics"])

scenes = data["scenes"]
for i, s in enumerate(scenes):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(s)
           + "?width=1024&height=576&nologo=true&seed=" + str(i))
    ok = False
    for _ in range(3):
        try:
            resp = requests.get(url, timeout=60)
            if resp.ok and len(resp.content) > 5000:
                open(f"out/s{i}.jpg", "wb").write(resp.content)
                ok = True
                break
        except Exception:
            pass
        time.sleep(5)
    if not ok:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x3399ff:s=1280x720",
             "-frames:v", "1", f"out/s{i}.jpg"], check=True)

async def tts():
    text = data["lyrics"].replace("\n", ". ")
    await edge_tts.Communicate(text, "en-US-AnaNeural", rate="-15%").save("out/voice.mp3")

try:
    asyncio.run(tts())
except Exception:
    subprocess.run(["pip", "install", "gTTS"], check=True)
    from gtts import gTTS
    gTTS(data["lyrics"].replace("\n", ". "), lang="en").save("out/voice.mp3")

dur = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "csv=p=0", "out/voice.mp3"]))
per = dur / len(scenes)

with open("out/list.txt", "w") as f:
    for i in range(len(scenes)):
        subprocess.run(
            ["ffmpeg", "-y", "-i", f"out/s{i}.jpg", "-vf",
             f"scale=2560:1440,zoompan=z='min(zoom+0.0015,1.25)':d={int(per*25)}:s=1280x720:fps=25,format=yuv420p",
             "-t", str(per), "-c:v", "libx264", f"out/c{i}.mp4"], check=True)
        f.write(f"file 'c{i}.mp4'\n")

subprocess.run(
    ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "out/list.txt",
     "-i", "out/voice.mp3", "-c:v", "copy", "-c:a", "aac", "-shortest",
     "out/final.mp4"], check=True)
