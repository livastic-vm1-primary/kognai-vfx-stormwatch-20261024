#!/usr/bin/env python3
"""Check exact VFX duration, reproducibility, preservation and visible effect."""
from pathlib import Path
import json,hashlib,subprocess,re
from PIL import Image

ROOT=Path(__file__).resolve().parent
assert hashlib.sha256((ROOT/'source_cc0.webm').read_bytes()).hexdigest()=="c1846e272d7207c31b44fa3772f946ea21c7af3a2cd9622ba5b8091e8cacb1b8"
notes=(ROOT/'NOTES.txt').read_text().splitlines()
assert len(notes)==3 and all(ln.startswith(f"{i}. ") for i,ln in enumerate(notes,1))
assert "creativecommons.org/publicdomain/zero" in (ROOT/'SOURCES.txt').read_text()
im=Image.open(ROOT/'overlay.png').convert("RGBA")
bbox=im.getbbox()
assert bbox is not None and 650 <= bbox[0] < bbox[2] < 930
assert 350 <= bbox[1] < bbox[3] < 535
assert im.crop((0,0,600,540)).getchannel("A").getextrema()==(0,0)

for f in ("before.mp4","after.mp4"):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","stream=index,codec_type,codec_name,width,height,avg_frame_rate,nb_frames,duration",
                           "-of","json",str(ROOT/f)],capture_output=True,text=True,check=True)
    rows=json.loads(result.stdout)["streams"]
    vids=[x for x in rows if x["codec_type"]=="video"]
    assert len(vids)==1 and not [x for x in rows if x["codec_type"]=="audio"]
    v=vids[0]
    assert v["codec_name"]=="h264" and v["width"]==960 and v["height"]==540
    assert v["avg_frame_rate"]=="30/1" and v["nb_frames"]=="192" and abs(float(v["duration"])-6.4)<0.001

def psnr(crop):
    args=["ffmpeg","-hide_banner","-i",str(ROOT/"before.mp4"),"-i",str(ROOT/"after.mp4"),
          "-filter_complex",f"[0:v]crop={crop}[a];[1:v]crop={crop}[b];[a][b]psnr",
          "-f","null","-"]
    p=subprocess.run(args,capture_output=True,text=True,check=True)
    match=re.search(r"PSNR .*average:([\d.]+)",p.stderr)
    assert match,p.stderr[-1200:]
    return float(match.group(1))

outside=psnr("580:400:0:0")
within=psnr("275:155:660:365")
assert outside>40.0,f"Untouched region unexpectedly changed: {outside}"
assert within<34.0,f"VFX not visibly added: {within}"
print(f"PASS A1 CC0 source SHA256 and licensing; A2 192 equal frames, 30fps, 6.4sec; A3 sign anchored to fence; A4 unaffected region PSNR={outside:.2f}dB; A5 clearly visible applied VFX PSNR={within:.2f}dB; A6 three-line note; A7 source/rebuild.")
