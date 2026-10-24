#!/usr/bin/env python3
"""Reproducible Kognai VFX audition: a perspective-anchored, weather-lit sign.
Source shot: Wikimedia Commons CC0, static-camera Scud Clouds, Rubbish computer.
No third-party Python packages except Pillow. Requires ffmpeg, ffprobe.
"""
from __future__ import annotations
from pathlib import Path
import subprocess, json, hashlib
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT, FPS, FRAMES = 960, 540, 30, 192
SRC = ROOT / "source_cc0.webm"
OVERLAY = ROOT / "overlay.png"
BEFORE = ROOT / "before.mp4"
AFTER = ROOT / "after.mp4"

def call(*cmd: str) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

def linear_solve(A, b):
    n = len(b)
    T = [list(map(float, row))+[float(y)] for row,y in zip(A,b)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda i:abs(T[i][col]))
        if abs(T[pivot][col]) < 1e-12:
            raise ValueError("Singular perspective transform")
        T[col],T[pivot]=T[pivot],T[col]
        div=T[col][col]
        T[col]=[x/div for x in T[col]]
        for r in range(n):
            if r==col:continue
            v=T[r][col]
            T[r]=[p-v*q for p,q in zip(T[r],T[col])]
    return [row[-1] for row in T]

def inverse_perspective_coeffs(dst, src):
    # Output coords -> card coords:
    # u=(ax+by+c)/(gx+hy+1), v=(dx+ey+f)/(gx+hy+1)
    rows=[];outs=[]
    for (x,y),(u,v) in zip(dst,src):
        rows.append([x,y,1,0,0,0,-u*x,-u*y]); outs.append(u)
        rows.append([0,0,0,x,y,1,-v*x,-v*y]); outs.append(v)
    return linear_solve(rows,outs)

def make_overlay():
    # A matte pigment sign, perspectively fixed to the right hand wooden fence.
    # The entire source is a locked-off sky timelapse, so the fence doesn't move.
    card=Image.new("RGBA",(700,225),(0,0,0,0))
    d=ImageDraw.Draw(card)
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    f1=ImageFont.truetype(font,106)
    f2=ImageFont.truetype(font,106)
    s1,s2="STORM","WATCH"
    for line,y,fontface in [(s1,1,f1),(s2,110,f2)]:
        box=d.textbbox((0,0),line,font=fontface,stroke_width=0)
        x=(700-(box[2]-box[0]))//2
        # Soft shadow follows fence perspective, warm face follows amber sky.
        d.text((x+4,y+4),line,font=fontface,fill=(30,25,19,122))
        d.text((x,y),line,font=fontface,fill=(238,220,164,196),stroke_width=1,stroke_fill=(75,62,41,170))
    # Polygon chosen from the fixed building-plane geometry on the original
    # CC0 shot. Lettering is part of the wooden wall, not a screen HUD.
    dest=[(650,431),(909,365),(922,480),(670,515)]
    src=[(0,0),(699,0),(699,224),(0,224)]
    coeffs=inverse_perspective_coeffs(dest,src)
    transformed=card.transform((WIDTH,HEIGHT),Image.Transform.PERSPECTIVE,
                               coeffs,resample=Image.Resampling.BICUBIC)
    transformed.save(OVERLAY)
    assert transformed.getbbox() is not None

def render():
    assert SRC.is_file() and SRC.stat().st_size>2_000_000
    make_overlay()
    # Exact same preprocessing for both renders, no audio for clean comparison.
    # No flicker or tracking drift: a single static projected sign over a static fence.
    base=["ffmpeg","-y","-hide_banner","-loglevel","error",
          "-ss","0.350","-i",str(SRC),
          "-vf",f"fps={FPS},scale={WIDTH}:{HEIGHT}:flags=lanczos",
          "-frames:v",str(FRAMES),"-an","-c:v","libx264",
          "-preset","medium","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart"]
    call(*base,str(BEFORE))
    effect=["ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i",str(BEFORE),"-loop","1","-i",str(OVERLAY),
            "-filter_complex","[1:v]format=rgba[sign];[0:v][sign]overlay=0:0:format=auto:shortest=1,format=yuv420p[v]",
            "-map","[v]","-frames:v",str(FRAMES),"-an","-c:v","libx264",
            "-preset","medium","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(AFTER)]
    call(*effect)

def probe(path):
    result=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                           "-show_entries","stream=width,height,r_frame_rate,nb_frames,duration",
                           "-of","json",str(path)],check=True,capture_output=True,text=True)
    o=json.loads(result.stdout)["streams"][0]
    return {k:o.get(k) for k in ("width","height","r_frame_rate","nb_frames","duration")}

if __name__=="__main__":
    render()
    print("ORIGINAL_SHA256",hashlib.sha256(SRC.read_bytes()).hexdigest())
    for file in (BEFORE,AFTER):
        print(file.name, file.stat().st_size, probe(file))
