"""Cheap, scrubbable Manim visuals: frames + one self-contained HTML viewer. No video encode.

Run with the ManimGL workspace interpreter, from anywhere:

    PYM=$MANIM_WORKSPACE/.venv/Scripts/python.exe
    $PYM viz.py beats  slug.py SceneName --out DIR [--hd] [--title T] [--description D]
    $PYM viz.py sweep  slug.py SceneName --out DIR [--quality l|m] [--hd] [--n 60] [--title T] [--description D]
    $PYM viz.py viewer DIR [--title T] [--description D]      # rebuild viewer.html from DIR/frames.json

beats  one skipped pass over construct() via the workspace's snapshot.py; a frame after every
       play() (waits only if commented). Caption = the trailing `# comment` on the play line,
       else the code itself. Write captions as comments; $...$ math renders with KaTeX.
sweep  the scene sets up its picture in construct() and declares
           SWEEP = {"tracker": "g", "range": [0.2, 3.2], "n": 60, "label": "g", "fmt": ".2f"}
       with the ValueTracker stored as self.g; after construct() the tracker is stepped
       through the range and a frame saved at each value (updaters / always_redraw follow it).

Output: DIR/frames/*.png, DIR/frames.json, DIR/viewer.html (frames inlined as base64 WebP).
ManimGL runs from the workspace root so custom_config.yml (the 3b1b look) applies.
"""

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if not os.environ.get("MANIM_WORKSPACE"):
    sys.exit("set MANIM_WORKSPACE to the ManimGL workspace root (see README)")
WORKSPACE = Path(os.environ["MANIM_WORKSPACE"])
SNAPSHOT = WORKSPACE / ".claude/skills/manimgl/core/assets/snapshot.py"
CDN = "https://cdnjs.cloudflare.com/ajax/libs"


def check_scene(scene_file, scene):
    if Path(scene_file).name == "scene.py":
        # snapshot.py finds caption lines by file basename; manimlib's own scene/scene.py would match first
        sys.exit("name the scene file after the visual (e.g. wta_nullclines.py), not scene.py")
    src = Path(scene_file).read_text(encoding="utf-8")
    if not re.search(rf"^class {re.escape(scene)}\(", src, re.M):
        # manimgl silently falls back to another scene when the name is unknown
        sys.exit(f"no `class {scene}(` in {scene_file}")


def run_in_workspace(args):
    return subprocess.run([sys.executable, *args], cwd=WORKSPACE, capture_output=True, text=True)


# ---------------------------------------------------------------- beats
SNAP_LINE = re.compile(r"^\s*(\d+)\s+L(\d+)\s+(.*)$")


def caption_of(src):
    m = re.search(r"#\s*(.+)$", src)
    return m.group(1).strip() if m else src.strip()


def cmd_beats(a):
    check_scene(a.scene_file, a.scene)
    scene_file = str(Path(a.scene_file).resolve())
    t0 = time.time()
    p = run_in_workspace([str(SNAPSHOT), scene_file, a.scene, "--list"])
    beats = [SNAP_LINE.match(l) for l in p.stdout.splitlines()]
    beats = [(int(m.group(1)), m.group(3)) for m in beats if m]
    if p.returncode or not beats:
        sys.exit("snapshot --list failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-15:]))
    # frame k is taken just before beat k runs, i.e. it shows the result of beat k-1
    keep = [(k, src) for k, src in beats if "self.wait" not in src or "#" in src]
    want = [k + 1 for k, _ in keep if k + 1 < len(beats)]
    raw = Path(a.out) / "frames"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [str(SNAPSHOT), scene_file, a.scene, *map(str, want), "--out", tmp, "--quiet"]
        if a.hd:
            cmd.append("--hd")
        p = run_in_workspace(cmd)
        if p.returncode:
            sys.exit("snapshot failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-15:]))
        p_final = run_in_workspace([str(SNAPSHOT), scene_file, a.scene, "--out", tmp, "--quiet"]
                                   + (["--hd"] if a.hd else []))
        frames = []
        for i, (k, src) in enumerate(keep):
            name = f"{a.scene}_{k + 1:03d}.png" if k + 1 < len(beats) else f"{a.scene}_final.png"
            path = Path(tmp) / name
            if not path.exists():
                continue
            dst = raw / f"f{i:03d}.png"
            shutil.copyfile(path, dst)
            frames.append({"file": f"frames/{dst.name}", "caption": caption_of(src)})
    if p_final.returncode:
        print("warning: final frame failed", file=sys.stderr)
    meta = {"mode": "beats", "scene": a.scene, "frames": frames, "seconds": round(time.time() - t0, 1)}
    finish(a, meta)


# ---------------------------------------------------------------- sweep
SWEEP_RUN = r'''
import json, os, sys, time
sys.argv = ["manimgl", {file!r}, {scene!r}, "-s", "-w", {quality!r}, "--video_dir", {tmp!r}, "--file_name", "_sweep"]
from manimlib.scene.scene import Scene
OUT, N_OVERRIDE = {out!r}, {n!r}
_orig = Scene.tear_down

def tear_down(self):
    spec = getattr(self, "SWEEP", None)
    if spec:
        tr = getattr(self, spec["tracker"])
        a, b = spec["range"]
        n = N_OVERRIDE or spec.get("n", 60)
        fmt = spec.get("fmt", ".2f")
        frames, t0 = [], time.time()
        for k in range(n):
            v = a + (b - a) * k / (n - 1)
            tr.set_value(v)
            self.update_mobjects(0)
            self.update_frame(force_draw=True)
            name = f"f{{k:03d}}.png"
            self.get_image().save(os.path.join(OUT, name))
            frames.append({{"file": "frames/" + name, "value": v,
                            "caption": spec.get("label", "value") + " = " + format(v, fmt)}})
        json.dump({{"frames": frames, "label": spec.get("label", "value"), "sweep_seconds": round(time.time() - t0, 2)}},
                  open(os.path.join(OUT, "_sweep.json"), "w"))
        print("SWEEP_OK", n, flush=True)
    else:
        print("SWEEP_MISSING: scene has no SWEEP dict", flush=True)
    _orig(self)

Scene.tear_down = tear_down
from manimlib.__main__ import main
main()
'''


def cmd_sweep(a):
    check_scene(a.scene_file, a.scene)
    raw = Path(a.out) / "frames"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        code = SWEEP_RUN.format(file=str(Path(a.scene_file).resolve()), scene=a.scene, tmp=tmp,
                                quality="--hd" if a.hd else {"l": "-l", "m": "-m"}[a.quality], out=str(raw.resolve()), n=a.n)
        p = run_in_workspace(["-c", code])
    if "SWEEP_OK" not in p.stdout:
        sys.exit("sweep failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-20:]))
    data = json.loads((raw / "_sweep.json").read_text())
    (raw / "_sweep.json").unlink()
    meta = {"mode": "sweep", "scene": a.scene, "label": data["label"], "frames": data["frames"],
            "seconds": round(time.time() - t0, 1)}
    finish(a, meta)


# ---------------------------------------------------------------- viewer
def finish(a, meta):
    meta["title"] = a.title or meta["scene"]
    meta["description"] = a.description or ""
    out = Path(a.out)
    (out / "frames.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    html = build_viewer(out, meta)
    kb = html.stat().st_size // 1024
    print(f"{meta['mode']}: {len(meta['frames'])} frames in {meta['seconds']}s -> {html} ({kb} KB)")


def build_viewer(out, meta):
    from PIL import Image
    imgs = []
    for f in meta["frames"]:
        buf = io.BytesIO()
        Image.open(out / f["file"]).convert("RGB").save(buf, "WEBP", quality=85, method=4)
        imgs.append("data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode())
    data = {"title": meta["title"], "description": meta["description"], "mode": meta["mode"],
            "captions": [f.get("caption", "") for f in meta["frames"]], "images": imgs}
    html = VIEWER.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__TITLE__", meta["title"]) \
                 .replace("__CDN__", CDN)
    path = out / "viewer.html"
    path.write_text(html, encoding="utf-8")
    return path


VIEWER = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="__CDN__/KaTeX/0.16.9/katex.min.css">
<script defer src="__CDN__/KaTeX/0.16.9/katex.min.js"></script>
<script defer src="__CDN__/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
<style>
:root{--bg:#0b0b0c;--panel:#161618;--fg:#e8e8ea;--muted:#9a9aa2;--accent:#58c4dd}
:root[data-theme="light"]{--bg:#f6f6f7;--panel:#ffffff;--fg:#1b1b1f;--muted:#5d5d66;--accent:#1f7a99}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f6f6f7;--panel:#ffffff;--fg:#1b1b1f;--muted:#5d5d66;--accent:#1f7a99}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 32px}
h1{font-size:20px;margin:0 0 4px}
.desc{color:var(--muted);margin:0 0 14px}
.stage{background:#000;border-radius:10px;overflow:hidden}
.stage img{display:block;width:100%;height:auto}
.caption{min-height:3em;margin:12px 2px;font-size:17px}
.controls{display:flex;gap:10px;align-items:center;background:var(--panel);padding:10px 12px;border-radius:10px}
button{background:transparent;color:var(--fg);border:1px solid var(--muted);border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer}
button:hover{border-color:var(--accent);color:var(--accent)}
input[type=range]{flex:1;accent-color:var(--accent)}
.count{color:var(--muted);font-variant-numeric:tabular-nums;min-width:5.5em;text-align:right}
.hint{color:var(--muted);font-size:13px;margin-top:8px}
</style></head>
<body><main>
<h1 id="title"></h1><p class="desc" id="desc"></p>
<div class="stage"><img id="frame" alt="frame"></div>
<div class="caption" id="caption"></div>
<div class="controls">
 <button id="prev" aria-label="previous">&#8592;</button>
 <button id="play" aria-label="play">&#9654;</button>
 <button id="next" aria-label="next">&#8594;</button>
 <input type="range" id="slider" min="0" value="0" aria-label="frame">
 <span class="count" id="count"></span>
</div>
<div class="hint">Arrow keys step &middot; space plays &middot; drag the slider to scrub</div>
</main>
<script>
const D = __DATA__;
const img = document.getElementById('frame'), cap = document.getElementById('caption'),
      sl = document.getElementById('slider'), cnt = document.getElementById('count'),
      play = document.getElementById('play');
document.getElementById('title').textContent = D.title;
document.getElementById('desc').textContent = D.description;
sl.max = D.images.length - 1;
const pre = D.images.map(s => { const i = new Image(); i.src = s; return i; });
let k = 0, timer = null;
function math(el){ if (window.renderMathInElement) renderMathInElement(el,
  {delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}], throwOnError:false}); }
function show(i){
  k = Math.max(0, Math.min(D.images.length - 1, i));
  img.src = pre[k].src; sl.value = k; cap.textContent = D.captions[k] || ''; math(cap);
  cnt.textContent = (D.mode === 'sweep' ? '' : 'step ') + (k + 1) + ' / ' + D.images.length;
}
function toggle(){
  if (timer){ clearInterval(timer); timer = null; play.innerHTML = '&#9654;'; return; }
  play.innerHTML = '&#10074;&#10074;';
  timer = setInterval(() => show(k + 1 >= D.images.length ? 0 : k + 1), D.mode === 'sweep' ? 60 : 1200);
}
sl.addEventListener('input', () => show(+sl.value));
document.getElementById('prev').onclick = () => show(k - 1);
document.getElementById('next').onclick = () => show(k + 1);
play.onclick = toggle;
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight') show(k + 1); else if (e.key === 'ArrowLeft') show(k - 1);
  else if (e.key === ' ') { e.preventDefault(); toggle(); }
});
window.addEventListener('load', () => show(k));
show(0);
</script></body></html>
"""


def cmd_viewer(a):
    out = Path(a.out_dir)
    meta = json.loads((out / "frames.json").read_text(encoding="utf-8"))
    if a.title:
        meta["title"] = a.title
    if a.description:
        meta["description"] = a.description
    print(build_viewer(out, meta))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, f in (("beats", cmd_beats), ("sweep", cmd_sweep)):
        p = sub.add_parser(name)
        p.add_argument("scene_file"); p.add_argument("scene"); p.add_argument("--out", required=True)
        p.add_argument("--hd", action="store_true"); p.add_argument("--title"); p.add_argument("--description")
        if name == "sweep":
            p.add_argument("--n", type=int, default=0, help="override SWEEP['n']")
            p.add_argument("--quality", choices=["l", "m"], default="m", help="480p / 720p (default); --hd for 1080p")
        p.set_defaults(f=f)
    p = sub.add_parser("viewer"); p.add_argument("out_dir"); p.add_argument("--title"); p.add_argument("--description")
    p.set_defaults(f=cmd_viewer)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
