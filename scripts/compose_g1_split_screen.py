#!/usr/bin/env python3
"""Compose an existing saved G1 portfolio video with a synchronized top-down map.

Presentation-only: reads a completed trajectory and video, never edits source
experiment artifacts. Requires Pillow and FFmpeg/ffprobe; no MuJoCo rendering.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke"
DEFAULT_VIDEO = ROOT / "results/phase2_mujoco/portfolio_export_g1_native_style_restore_v1/portfolio_demo.mp4"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/g1_split_screen_portfolio"
PANEL_W, HEIGHT = 960, 720


def font(size: int, bold: bool = False):
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for p in candidates:
        if Path(p).is_file():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def ffprobe(video: Path) -> dict:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate,duration,width,height:format=duration",
        "-of", "json", str(video)
    ], text=True)
    d = json.loads(raw)
    video_stream = d.get("streams", [{}])[0]
    return {
        "frames": int(video_stream["nb_frames"]) if video_stream.get("nb_frames", "N/A") not in ("N/A", "") else None,
        "duration": float(video_stream.get("duration") or d.get("format", {}).get("duration") or 0),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
    }


def read_saved_run(result_dir: Path):
    trajectory = json.loads((result_dir / "trajectory.json").read_text(encoding="utf-8"))
    scenario = json.loads((result_dir / "scenario.json").read_text(encoding="utf-8"))
    root = ET.parse(result_dir / "scene.xml").getroot()
    walls = set()
    for geom in root.iter("geom"):
        n = geom.get("name", "")
        if n.startswith("wall_"):
            parts = n.split("_")
            if len(parts) == 3:
                walls.add((int(parts[1]), int(parts[2])))
    if not walls or len(trajectory) < 2:
        raise ValueError("Expected a saved maze scene and multi-step trajectory")
    if "start" not in scenario:
        scenario["start"] = trajectory[0]["position"]
    if "goal" not in scenario:
        scenario["goal"] = trajectory[-1]["position"]
    return trajectory, scenario, walls


def color(hexv: str):
    return tuple(bytes.fromhex(hexv.lstrip("#")))


def create_base_map(scenario: dict, walls: set[tuple[int, int]], *, size=(PANEL_W, HEIGHT)):
    width, height = size
    im = Image.new("RGB", size, color("f9fbfd"))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, width, 65), fill=color("f5f8fb"))
    d.text((42, 19), "SPATIAL MEMORY  /  TOP-DOWN VIEW", font=font(23, True), fill=color("182b3d"))
    d.text((42, 50), "Recorded maze geometry and G1 position", font=font(11), fill=color("748397"))
    count_x, count_y = scenario["width"], scenario["height"]
    # 25x25 cells across a large 600px map area with a compact legend to the right.
    cell = min(23, int(580 / max(count_x, count_y)))
    x0, y0 = 53, 84
    xmax, ymax = x0 + count_x * cell, y0 + count_y * cell
    d.rounded_rectangle((x0-11,y0-11,xmax+11,ymax+11), radius=13, fill="white", outline="#dfe6eb", width=2)
    for y in range(count_y):
        for x in range(count_x):
            u, v = x0+x*cell, y0+(count_y-1-y)*cell
            fill = "#526173" if (x,y) in walls else "#f2f5f8"
            d.rounded_rectangle((u+0.5,v+0.5,u+cell-1,v+cell-1), radius=2, fill=fill)
    d.text((688,108), "ROUTE TRACKING", font=font(16, True), fill=color("24364b"))
    d.ellipse((688,172,706,190),fill=color("0ea5e9"))
    d.text((718,170), "START", font=font(16, True), fill=color("37465a"))
    d.ellipse((688,218,706,236),fill=color("d6a320"))
    d.text((718,216), "GOAL", font=font(16, True), fill=color("37465a"))
    d.ellipse((688,264,706,282),fill=color("1772d0"))
    d.text((718,262), "G1  /  REPLAY", font=font(15, True), fill=color("37465a"))
    d.line((681,329,915,329),fill=color("e1e7ed"),width=2)
    d.text((688,593), "TOP-DOWN REFERENCE", font=font(13, True), fill=color("557084"))
    d.text((688,618), "Visualization of saved", font=font(13), fill=color("748397"))
    d.text((688,636), "simulator state, not", font=font(13), fill=color("748397"))
    d.text((688,654), "the robot's observed map.", font=font(13), fill=color("748397"))
    def map_pt(pos):
        return (x0+(float(pos[0])+.5)*cell,
                y0+(count_y-1-float(pos[1])+.5)*cell)
    return im,map_pt


def interpolate_heading(a,b,t):
    delta = (float(b)-float(a)+math.pi)%(2*math.pi)-math.pi
    return float(a)+t*delta


def pose_at(trajectory, index, frames_per_action):
    n = len(trajectory)
    k = min(index//frames_per_action,n-1)
    if k >= n-1:
        last = trajectory[-1]
        return (tuple(map(float,last["position"])),float(last.get("heading_yaw",0)),n-1)
    a,b=trajectory[k],trajectory[k+1]
    t=(index%frames_per_action)/frames_per_action
    x=(1-t)*a["position"][0]+t*b["position"][0]
    y=(1-t)*a["position"][1]+t*b["position"][1]
    h=interpolate_heading(a.get("heading_yaw",0),b.get("heading_yaw",0),t)
    return ((x,y),h,k)


def render_map_frames(trajectory,scenario,walls,frames_dir,num_frames,fps,speed, *, size=(PANEL_W,HEIGHT)):
    base,pt = create_base_map(scenario,walls,size=size)
    frames_per_action=math.ceil(speed*fps)
    total_segment_frames=(len(trajectory)-1)*frames_per_action
    if num_frames < total_segment_frames:
        raise ValueError(f"Video has {num_frames} frames but trajectory requires at least {total_segment_frames}; verify fps and speed")
    route=[pt(x["position"]) for x in trajectory]
    start,goal=pt(scenario["start"]),pt(scenario["goal"])
    frames_dir.mkdir(parents=True,exist_ok=False)
    for idx in range(num_frames):
        im=base.copy()
        d=ImageDraw.Draw(im)
        # Full recorded route in pale gray and explored route in bright teal.
        d.line(route,fill=color("c5d3da"),width=6,joint="curve")
        (x,y),yaw,k=pose_at(trajectory,idx,frames_per_action)
        current=pt((x,y))
        trail=route[:k+1]+[current]
        if len(trail)>=2:
            d.line(trail,fill=color("0d9488"),width=6,joint="curve")
        for coord,clr,label in ((start,"#079cc3","S"),(goal,"#d7a118","G")):
            a,b=coord
            d.ellipse((a-14,b-14,a+14,b+14),fill="white",outline=clr,width=4)
            d.text((a-5,b-9),label,font=font(13,True),fill=clr)
        a,b=current
        d.ellipse((a-20,b-20,a+20,b+20),fill="#d6e9ff",outline="#ffffff",width=2)
        d.ellipse((a-13,b-13,a+13,b+13),fill="#1772d0",outline="#ffffff",width=2)
        # Heading needle follows saved robot orientation but map stays fixed.
        tip=(a+19*math.cos(yaw),b-19*math.sin(yaw))
        d.line((a,b,tip[0],tip[1]),fill="white",width=4)
        d.ellipse((tip[0]-3,tip[1]-3,tip[0]+3,tip[1]+3),fill="#ffffff")
        d.text((688,350),"CURRENT STEP",font=font(12,True),fill=color("748397"))
        d.text((687,371),f"{k:02d} / {len(trajectory)-1:02d}",font=font(32,True),fill=color("1d3550"))
        progress=idx/max(1,num_frames-1)
        d.rounded_rectangle((687,432,914,447),radius=7,fill="#dbe4eb")
        if progress>0:
            d.rounded_rectangle((687,432,687+max(10,227*progress),447),radius=7,fill="#0d9488")
        d.text((688,471),f"Grid position: ({round(x)}, {round(y)})",font=font(14),fill=color("526479"))
        d.text((688,506),"G1 route (kinematic replay)",font=font(13),fill=color("718195"))
        im.save(frames_dir/f"frame_{idx:05d}.png")
    return {"frames":num_frames,"frames_per_action":frames_per_action,"source_steps":len(trajectory)-1}


def encode_split_video(left:Path,map_dir:Path,out:Path,fps:int,frame_count:int):
    left_filter=(f"[0:v]fps={fps},scale={PANEL_W}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                 f"pad={PANEL_W}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x101923,setsar=1[left];"
                 "[left][1:v]hstack=inputs=2:shortest=1[v]")
    cmd=["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(left),
         "-framerate",str(fps),"-i",str(map_dir/"frame_%05d.png"),
         "-filter_complex",left_filter,"-map","[v]","-frames:v",str(frame_count),
         "-an","-c:v","libx264","-crf","20","-preset","medium","-pix_fmt","yuv420p","-movflags","+faststart",str(out)]
    subprocess.run(cmd,check=True)


def encode_gif(mp4:Path,out:Path,width:int=1280,fps:int=16):
    palette=out.with_suffix(".palette.png")
    vf=f"fps={fps},scale={width}:-1:flags=lanczos"
    try:
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(mp4),
                        "-vf",vf+",palettegen=stats_mode=diff",str(palette)],check=True)
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(mp4),"-i",str(palette),
                        "-lavfi",f"[0:v]{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",str(out)],check=True)
    finally:
        palette.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--left-video",type=Path,default=DEFAULT_VIDEO,help="Existing fully rendered G1 MP4 or GIF")
    p.add_argument("--result-dir",type=Path,default=DEFAULT_RUN,help="Trajectory/scene used by the existing video")
    p.add_argument("--output-dir",type=Path,default=DEFAULT_OUTPUT)
    p.add_argument("--fps",type=int,default=24)
    p.add_argument("--speed",type=float,default=0.18,help="Seconds per saved action in original export")
    p.add_argument("--gif-width",type=int,default=1280)
    p.add_argument("--no-gif",action="store_true")
    args=p.parse_args()
    if not args.left_video.exists():p.error(f"Left video missing: {args.left_video}")
    if args.output_dir.exists():p.error(f"Output folder already exists: {args.output_dir}")
    if not 1<=args.fps<=60 or args.speed<=0:p.error("FPS must be 1..60 and speed positive")
    if not all(shutil.which(x) for x in ("ffmpeg","ffprobe")):p.error("FFmpeg/ffprobe required")
    trajectory,scenario,walls=read_saved_run(args.result_dir)
    info=ffprobe(args.left_video)
    meta_path=args.left_video.parent/"metadata.json"
    metadata=json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if metadata:
        expected=metadata.get("source_trajectory_sha256")
        actual=hashlib.sha256((args.result_dir/"trajectory.json").read_bytes()).hexdigest()
        if expected and expected!=actual:
            p.error("Left video metadata references a different trajectory; use the matching saved run")
        if metadata.get("output_frames") is not None and info["frames"] is not None and info["frames"]!=int(metadata["output_frames"]):
            p.error("Video frame count differs from its metadata")
        if metadata.get("fps") is not None and int(metadata["fps"])!=args.fps:
            p.error("FPS differs from source metadata: use --fps matching original export")
        if metadata.get("seconds_per_saved_action") is not None and abs(float(metadata["seconds_per_saved_action"])-args.speed)>1e-4:
            p.error("Action speed differs from source metadata: use --speed matching original export")
    num_frames=info["frames"] or round(info["duration"]*args.fps)
    if num_frames<=0:p.error("Could not determine left video frame count")
    # Create only after all checks. Never overwrite existing scientific results.
    args.output_dir.mkdir(parents=True)
    temp=args.output_dir/"_right_frames"
    details=render_map_frames(trajectory,scenario,walls,temp,num_frames,args.fps,args.speed)
    video=args.output_dir/"g1_split_screen.mp4"
    encode_split_video(args.left_video,temp,video,args.fps,num_frames)
    gif=args.output_dir/"g1_split_screen.gif"
    if not args.no_gif:encode_gif(video,gif,args.gif_width)
    shutil.copyfile(temp/f"frame_{num_frames//2:05d}.png",args.output_dir/"map_preview.png")
    shutil.rmtree(temp)
    settings={"source_video":str(args.left_video),"saved_run":str(args.result_dir),
             "video_sha256":hashlib.sha256(args.left_video.read_bytes()).hexdigest(),
             "trajectory_sha256":hashlib.sha256((args.result_dir/"trajectory.json").read_bytes()).hexdigest(),
             "composite_mp4":video.name,"composite_gif":gif.name if gif.exists() else None,
             "output_size":[PANEL_W*2,HEIGHT],"fps":args.fps,"action_speed":args.speed,**details,
             "visualization_note":"Right panel shows evaluator ground-truth maze geometry and saved pose, not the robot's perceived map."}
    (args.output_dir/"metadata.json").write_text(json.dumps(settings,indent=2)+"\n")
    artifacts=[]
    for path in sorted(args.output_dir.iterdir()):
        if path.is_file():
            artifacts.append({"path":path.name,"size":path.stat().st_size,
                              "sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    (args.output_dir/"artifact_manifest.json").write_text(json.dumps(artifacts,indent=2)+"\n")
    print(json.dumps({"success":True,"output":str(args.output_dir),"frames":num_frames,
                      "mp4":str(video),"gif":str(gif) if gif.exists() else None},indent=2))


if __name__=="__main__":main()
