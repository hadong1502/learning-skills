"""Make one throwaway copy of a course's .learn state per eval case, so eval runs never touch the
learner's real record:  python make_sandboxes.py cases.json OUT_DIR [CASE_ID ...]

- .learn/*.json, index/log and the converted sources/*.md are copied (cheap, writable).
- The course's original folders and .learn/cache are linked in as Windows junctions, so `status`
  doesn't report every source as removed and `page` can render originals. Agents must treat
  them as read-only.
- Write each reply to OUT_DIR/<id>_response.md, outside the sandbox: a file inside the course
  root would be picked up as a new source.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

cases = json.load(open(sys.argv[1], encoding="utf-8"))
out = Path(sys.argv[2])
only = set(sys.argv[3:])
course = Path(cases["course"])
src = course / ".learn"
lc = Path.home() / ".claude/skills/learn/scripts/learnctl.py"


def junction(link, target):
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)


for c in cases["cases"]:
    if only and c["id"] not in only:
        continue
    root = out / c["id"]
    if root.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(root)], check=True)  # removes junctions, not targets
    dst = root / ".learn"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("cache", "viz", "tmp", "*.jpeg", "*.jpg", "*.png", ".done"))
    (dst / "tmp").mkdir()
    junction(dst / "cache", src / "cache")
    for item in course.iterdir():
        if item.name.startswith("."):
            continue
        if item.is_dir():
            junction(root / item.name, item)
        else:
            shutil.copy2(item, root / item.name)
    subprocess.run([sys.executable, "-I", str(lc), "--root", str(root), "position", "set", c["position"]],
                   check=True, capture_output=True)
    print(root)
