"""learnctl: the only writer of a course's .learn/ state.

Stdlib only; run with any Python 3.10+. Only `convert` on PDFs needs the
learning-skills venv (Marker), which it locates next to this repo.

    learnctl.py init [--title T]
    learnctl.py scan                          # new / changed / removed sources (JSON)
    learnctl.py convert [--pending | PATH ...] [--dry-run]
    learnctl.py unit add|update --id L01 --order 1 --title T [--sources ...] [--summary S]
                [--kind lecture|pset|exam|project|reading|admin] [--status "active: ..."]
    learnctl.py unit list
    learnctl.py concept import FILE.json      # validate + merge a unit's concepts
    learnctl.py concept list [--upto L05] [--unit L03] [--grep text]
    learnctl.py concept move --to L10 [--ids a,b] [--from-unit L09] [--loc-prefix "NN"]
    learnctl.py position set L05 | show
    learnctl.py context [--query text] [--concepts a,b]   # what is in scope at the position
    learnctl.py evidence add --concept ID --kind KIND --note N
    learnctl.py misc add --concept ID --desc D | set --id M3 --status S --note N | list
    learnctl.py quiz plan [--n 5] [--units L08,L09]   # due reviews, misconceptions to re-test, weak concepts
    learnctl.py quiz add ITEMS.json | show Q007 [--solution] | list | stats
    learnctl.py quiz record Q007 --score 0.6 --confidence 4 [--rating 1-4] --notes N
    learnctl.py log --kind K --text T
    learnctl.py render                        # regenerate index.md
    learnctl.py status
    learnctl.py course set [--title T] [--policy P] | show
    learnctl.py page SOURCE N [N ...]        # render original pages to PNG (.learn/cache/pages/)
    learnctl.py audit                         # flag pages where conversion dropped minus signs

All state is JSON under .learn/ and is written atomically. Run from the course
folder (or any subfolder), or pass --root.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE_EXTS = {".pdf", ".pptx", ".tex", ".md", ".txt", ".ipynb", ".csv"}
UNIT_KINDS = {"lecture", "pset", "exam", "project", "reading", "admin"}
SKIP_DIRS = {".learn", ".claude", ".git", ".venv", "venv", "node_modules", "__pycache__", ".ipynb_checkpoints"}
CONCEPT_KINDS = {"definition", "theorem", "lemma", "proposition", "corollary", "method",
                 "notation", "example", "idea", "assumption", "result"}
EVIDENCE_DELTA = {"asked": 0.0, "explained": 0.15, "correct": 0.2, "partial": 0.05,
                  "incorrect": -0.2, "misconception": -0.25}
MISC_FLOW = {"observed": {"addressed"}, "addressed": {"verified", "observed"}, "verified": {"observed"}}
HALF_LIFE_DAYS = 30.0
REPO = Path(__file__).resolve().parents[2]        # learning-skills/
VENV_PY = REPO / ".venv" / "Scripts" / "python.exe"


# ---------------------------------------------------------------- basics
def today():
    return dt.date.today().isoformat()


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def find_root(start):
    p = Path(start).resolve()
    for q in [p, *p.parents]:
        if (q / ".learn").is_dir():
            return q
    return None


def load(path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(rel):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", rel.replace("\\", "/").replace("/", "__"))


class State:
    def __init__(self, root):
        self.root = Path(root)
        self.dir = self.root / ".learn"
        self.p = {k: self.dir / f"{k}.json" for k in ("manifest", "course", "concepts", "learner")}

    def get(self, k):
        defaults = {
            "manifest": {"version": 1, "sources": {}},
            "course": {"version": 1, "title": self.root.name, "units": [], "position": None},
            "concepts": {"version": 1, "concepts": []},
            "learner": {"version": 1, "concepts": {}, "misconceptions": [], "calibration": []},
        }
        return load(self.p[k], defaults[k])

    def put(self, k, data):
        save(self.p[k], data)

    def log(self, kind, text):
        with open(self.dir / "log.md", "a", encoding="utf-8") as f:
            f.write(f"## [{now()}] {kind}\n{text.strip()}\n\n")


def state_from(args):
    root = Path(args.root) if args.root else find_root(os.getcwd())
    if root is None or not (root / ".learn").is_dir():
        die("no .learn/ here or above; run `learnctl.py init` in the course folder")
    return State(root)


def unit_order(course):
    return {u["id"]: u["order"] for u in course["units"]}


# ---------------------------------------------------------------- sources
def discover(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in SOURCE_EXTS:
                out.append(p.relative_to(root).as_posix())
    return sorted(out)


def adopt_finished(st, rel):
    """Record a Marker output finished by a batch that is still running or was interrupted."""
    outdir = st.dir / "sources" / safe_name(rel)
    tag, md = outdir / ".done", outdir / "content.md"
    if not (tag.exists() and md.exists()):
        return False
    if tag.read_text().strip() != sha256(st.root / rel):
        return False
    record(st, rel, md, "powerpoint+marker" if rel.lower().endswith(".pptx") else "marker")
    return True


def scan(st):
    man = st.get("manifest")["sources"]
    found = discover(st.root)
    res = {"new": [], "changed": [], "removed": [], "unconverted": [], "unchanged": []}
    for rel in found:
        p = st.root / rel
        ent = man.get(rel)
        if (ent is None or not ent.get("output")) and adopt_finished(st, rel):
            ent = st.get("manifest")["sources"][rel]
            man[rel] = ent
        if ent is None:
            res["new"].append(rel)
            continue
        stat = p.stat()
        if stat.st_size == ent.get("size") and abs(stat.st_mtime - ent.get("mtime", 0)) < 1e-3:
            same = True
        else:
            same = sha256(p) == ent.get("sha256")
        if not same:
            res["changed"].append(rel)
        elif not ent.get("output"):
            res["unconverted"].append(rel)
        else:
            res["unchanged"].append(rel)
    res["removed"] = sorted(set(man) - set(found))
    return res


def notebook_md(path, max_out=1500):
    nb = json.loads(Path(path).read_text(encoding="utf-8"))
    parts = []
    for i, c in enumerate(nb.get("cells", [])):
        src = "".join(c.get("source", []))
        if c.get("cell_type") == "markdown":
            parts.append(f"<!-- cell {i} -->\n{src}")
        elif c.get("cell_type") == "code":
            parts.append(f"<!-- cell {i} -->\n```python\n{src}\n```")
            for o in c.get("outputs", []):
                data = o.get("data") or {}
                txt = "".join(o.get("text", [])) or "".join(data.get("text/plain", []))
                if any(k.startswith("image/") for k in data):
                    parts.append("_[image output omitted]_")
                elif txt.strip():
                    txt = txt if len(txt) <= max_out else txt[:max_out] + "\n... [truncated]"
                    parts.append(f"```text\n{txt.rstrip()}\n```")
    return "\n\n".join(parts)


def convert_text(st, rel):
    src = st.root / rel
    out = st.dir / "sources" / (safe_name(rel) + ".md")
    ext = src.suffix.lower()
    if ext == ".ipynb":
        body, conv = notebook_md(src), "notebook"
    else:
        body, conv = src.read_text(encoding="utf-8", errors="replace"), "copy"
        fence = {".tex": "latex", ".csv": "csv"}.get(ext)
        if fence:
            body = f"```{fence}\n{body}\n```"
    out.write_text(f"<!-- source: {rel} -->\n\n{body}\n", encoding="utf-8")
    return out, conv


PPTX_TO_PDF = r"""
$ErrorActionPreference = 'Stop'
$pp = New-Object -ComObject PowerPoint.Application
try {
  $pres = $pp.Presentations.Open($env:LEARN_PPTX_IN, $true, $false, $false)
  $pres.SaveAs($env:LEARN_PPTX_OUT, 32)
  $pres.Close()
} finally {
  if ($pp.Presentations.Count -eq 0) { $pp.Quit() }   # never close the user's open decks
}
"""


def pptx_pdf_path(st, rel):
    return st.dir / "cache" / (safe_name(rel) + ".pdf")


def export_pptx(st, rel):
    """Export a .pptx to PDF with the installed PowerPoint (COM), cached under .learn/cache/."""
    out = pptx_pdf_path(st, rel)
    if out.exists() and out.stat().st_mtime >= (st.root / rel).stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, LEARN_PPTX_IN=str((st.root / rel).resolve()), LEARN_PPTX_OUT=str(out.resolve()))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PPTX_TO_PDF],
                       env=env, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        print(f"pptx export failed for {rel}: {r.stderr.strip()[-500:]}", file=sys.stderr)
        return None
    return out


def convert_pdfs(st, rels):
    if not VENV_PY.exists():
        die(f"Marker env missing: {VENV_PY}. Run `uv sync` in {REPO}.")
    jobs, conv = [], {}
    for rel in rels:
        pdf = st.root / rel
        conv[rel] = "marker"
        if rel.lower().endswith(".pptx"):
            pdf = export_pptx(st, rel)
            conv[rel] = "powerpoint+marker"
            if pdf is None:
                continue
        outdir = st.dir / "sources" / safe_name(rel)
        jobs.append({"pdf": str(pdf), "outdir": str(outdir), "rel": rel, "sha": sha256(st.root / rel)})
    if not jobs:
        return {}
    job_file = st.dir / "sources" / "_marker_jobs.json"
    save(job_file, jobs)
    script = Path(__file__).with_name("marker_convert.py")
    r = subprocess.run([str(VENV_PY), "-I", str(script), str(job_file)])
    job_file.unlink(missing_ok=True)
    if r.returncode != 0:
        die("marker conversion failed (see output above)")
    results = {}
    for j in jobs:
        md = Path(j["outdir"]) / "content.md"
        if md.exists():
            results[j["rel"]] = (md, conv[j["rel"]])
    return results


def record(st, rel, output, converter):
    man = st.get("manifest")
    p = st.root / rel
    stat = p.stat()
    man["sources"][rel] = {
        "sha256": sha256(p), "size": stat.st_size, "mtime": stat.st_mtime,
        "kind": p.suffix.lower().lstrip("."), "converter": converter,
        "output": output.relative_to(st.dir).as_posix() if output else None,
        "converted_at": now(),
    }
    st.put("manifest", man)


# ---------------------------------------------------------------- learner
def effective_mastery(rec):
    m = rec.get("mastery")
    if m is None or not rec.get("last_seen"):
        return m
    days = (dt.date.today() - dt.date.fromisoformat(rec["last_seen"][:10])).days
    return round(m * 0.5 ** (days / HALF_LIFE_DAYS), 2)


def concept_index(st):
    return {c["id"]: c for c in st.get("concepts")["concepts"]}


def in_scope(course, concept):
    pos = course.get("position")
    if pos is None:
        return True
    order = unit_order(course)
    return order.get(concept["unit"], 1e9) <= order.get(pos, -1)


# ---------------------------------------------------------------- commands
def cmd_init(args):
    root = Path(args.root or os.getcwd()).resolve()
    st = State(root)
    (st.dir / "sources").mkdir(parents=True, exist_ok=True)
    for k in ("manifest", "course", "concepts", "learner"):
        if not st.p[k].exists():
            data = st.get(k)
            if k == "course" and args.title:
                data["title"] = args.title
            st.put(k, data)
    st.log("init", f"Created .learn/ in {root}")
    print(f"initialized {st.dir}")


def cmd_scan(args):
    print(json.dumps(scan(state_from(args)), indent=1))


def cmd_convert(args):
    st = state_from(args)
    if args.pending:
        s = scan(st)
        rels = s["new"] + s["changed"] + s["unconverted"]
    else:
        rels = [Path(p).resolve().relative_to(st.root).as_posix() if Path(p).is_absolute() else p.replace("\\", "/")
                for p in args.paths]
    if not rels:
        print("nothing to convert")
        return
    if args.dry_run:
        print(json.dumps(rels, indent=1))
        return
    pdfs = [r for r in rels if r.lower().endswith((".pdf", ".pptx"))]
    for rel in rels:
        if rel not in pdfs:
            out, conv = convert_text(st, rel)
            record(st, rel, out, conv)
            print(f"converted {rel} -> {out.relative_to(st.root).as_posix()}")
    if pdfs:
        done = convert_pdfs(st, pdfs)
        for rel in pdfs:
            if rel in done:
                out, conv = done[rel]
                record(st, rel, out, conv)
                print(f"converted {rel} -> {out.relative_to(st.root).as_posix()}")
            else:
                print(f"FAILED {rel}", file=sys.stderr)
    st.log("convert", "\n".join(f"- {r}" for r in rels))


def cmd_unit(args):
    st = state_from(args)
    course = st.get("course")
    if args.action == "list":
        for u in sorted(course["units"], key=lambda u: u["order"]):
            mark = " <= position" if u["id"] == course.get("position") else ""
            tag = f" ({u['status']})" if u.get("status") else ""
            print(f"{u['order']:>3}  {u['id']:<8} {u.get('kind', 'lecture'):<8} {u['title']}{tag}  "
                  f"[{', '.join(u.get('sources', []))}]{mark}")
        return
    if not args.id:
        die("--id required")
    units = {u["id"]: u for u in course["units"]}
    if args.action == "remove":
        if args.id not in units:
            die(f"no unit {args.id}")
        owned = [c["id"] for c in st.get("concepts")["concepts"] if c["unit"] == args.id]
        if owned:
            die(f"unit {args.id} introduces {len(owned)} concepts; move them first (concept import with a new unit)")
        course["units"] = [u for u in course["units"] if u["id"] != args.id]
        if course.get("position") == args.id:
            course["position"] = None
        st.put("course", course)
        st.log("unit", f"removed {args.id}")
        print(f"unit {args.id} removed")
        return
    if args.action == "add" and args.id in units:
        die(f"unit {args.id} exists; use `unit update`")
    if args.action == "update" and args.id not in units:
        die(f"no unit {args.id}")
    u = units.get(args.id, {"id": args.id, "kind": "lecture", "status": "", "sources": [], "summary": ""})
    if args.action == "add" and (args.order is None or not args.title):
        die("unit add needs --order and --title")
    if args.order is not None:
        u["order"] = args.order
    if args.title:
        u["title"] = args.title
    if args.sources is not None:
        man = st.get("manifest")["sources"]
        missing = [s for s in args.sources if s not in man]
        if missing:
            print(f"warning: not in manifest (scan/convert first?): {missing}", file=sys.stderr)
        u["sources"] = args.sources
    if args.summary is not None:
        u["summary"] = args.summary
    if args.kind is not None:
        if args.kind not in UNIT_KINDS:
            die(f"--kind must be one of {sorted(UNIT_KINDS)}")
        u["kind"] = args.kind
    if args.status is not None:
        u["status"] = args.status
    units[args.id] = u
    course["units"] = sorted(units.values(), key=lambda x: x["order"])
    st.put("course", course)
    print(f"unit {args.id} saved")


CONCEPT_FIELDS = {"id", "name", "kind", "unit", "loc", "uses", "notation", "aliases", "statement"}


def cmd_concept(args):
    st = state_from(args)
    course = st.get("course")
    data = st.get("concepts")
    idx = {c["id"]: c for c in data["concepts"]}
    if args.action == "move":
        # Reassign concepts to another unit (e.g. when the real lecture order differs from the
        # syllabus). `import` never does this because it keeps the earliest introduction.
        if args.to not in unit_order(course):
            die(f"unit {args.to!r} not defined")
        ids = set(filter(None, (args.ids or "").split(",")))
        if args.from_unit:
            ids |= {c["id"] for c in data["concepts"] if c["unit"] == args.from_unit}
        if args.loc_prefix:
            ids = {i for i in ids if idx.get(i, {}).get("loc", "").startswith(args.loc_prefix)}
        missing = sorted(i for i in ids if i not in idx)
        if missing:
            die(f"unknown concepts: {missing}")
        for i in ids:
            idx[i]["unit"] = args.to
        order = unit_order(course)
        data["concepts"] = sorted(idx.values(), key=lambda c: (order.get(c["unit"], 1e9), c["id"]))
        st.put("concepts", data)
        st.log("concept", f"moved {len(ids)} concepts to {args.to}: {', '.join(sorted(ids))}")
        print(f"moved {len(ids)} concepts to {args.to}")
        return
    if args.action == "import":
        items = load(Path(args.file), None)
        if isinstance(items, dict):
            items = items.get("concepts")
        if not isinstance(items, list):
            die("file must be a JSON list of concepts (or {\"concepts\": [...]})")
        units = unit_order(course)
        new_ids = {c.get("id") for c in items}
        errors, warnings = [], []
        for i, c in enumerate(items):
            extra = set(c) - CONCEPT_FIELDS
            if extra:
                errors.append(f"[{i}] unknown fields {sorted(extra)}")
            for f in ("id", "name", "kind", "unit"):
                if not c.get(f):
                    errors.append(f"[{i}] missing {f}")
            if c.get("id") and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", c["id"]):
                errors.append(f"[{i}] id {c['id']!r} must be kebab-case")
            if c.get("kind") and c["kind"] not in CONCEPT_KINDS:
                errors.append(f"[{i}] kind {c['kind']!r} not in {sorted(CONCEPT_KINDS)}")
            if c.get("unit") and c["unit"] not in units:
                errors.append(f"[{i}] unit {c['unit']!r} not defined (unit add first)")
            prev = idx.get(c.get("id"))
            if prev and prev["unit"] != c.get("unit"):
                warnings.append(f"{c['id']}: already introduced in {prev['unit']}; keeping earliest unit")
            for u in c.get("uses", []):
                if u not in idx and u not in new_ids:
                    warnings.append(f"{c.get('id')}: uses unknown concept {u!r}")
        if errors:
            die("\n".join(errors))
        for c in items:
            c.setdefault("uses", [])
            c.setdefault("aliases", [])
            prev = idx.get(c["id"])
            if prev and units.get(prev["unit"], 0) < units.get(c["unit"], 0):
                c["unit"], c["loc"] = prev["unit"], prev.get("loc", "")
            idx[c["id"]] = {k: c.get(k, "") for k in ("id", "name", "kind", "unit", "loc", "uses",
                                                        "notation", "aliases", "statement")}
        data["concepts"] = sorted(idx.values(), key=lambda c: (units.get(c["unit"], 1e9), c["id"]))
        st.put("concepts", data)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        print(f"imported {len(items)} concepts ({len(data['concepts'])} total)")
        return
    # list
    order = unit_order(course)
    lim = order.get(args.upto) if args.upto else None
    pat = re.compile(args.grep, re.I) if args.grep else None
    for c in data["concepts"]:
        if args.unit and c["unit"] != args.unit:
            continue
        if lim is not None and order.get(c["unit"], 1e9) > lim:
            continue
        if pat and not pat.search(" ".join([c["id"], c["name"], *c.get("aliases", [])])):
            continue
        print(f"{c['unit']:<6} {c['kind']:<11} {c['id']:<32} {c['name']}  ({c.get('loc', '')})")


def cmd_position(args):
    st = state_from(args)
    course = st.get("course")
    if args.action == "set":
        if args.unit not in unit_order(course):
            die(f"no unit {args.unit}")
        course["position"] = args.unit
        st.put("course", course)
        st.log("position", f"set to {args.unit}")
    print(course.get("position") or "(none: whole course in scope)")


def audit_warnings(st, course, concept):
    """Pages cited by a concept where `audit` found dropped minus signs."""
    audit = load(st.dir / "audit.json", {})
    pages = set()
    for a, b in re.findall(r"p\.(\d+)(?:-(\d+))?", concept.get("loc", "")):
        pages.update(range(int(a), int(b or a) + 1))
    unit = next((u for u in course["units"] if u["id"] == concept["unit"]), {})
    out = []
    for src in unit.get("sources", []):
        bad = sorted(f["page"] for f in audit.get(src, []) if f["page"] in pages)
        if bad:
            out.append(f"{src} p.{','.join(map(str, bad))} may have dropped minus signs "
                       f"(`learnctl.py page \"{src}\" {' '.join(map(str, bad))}`)")
    return out


def cmd_context(args):
    st = state_from(args)
    course = st.get("course")
    concepts = st.get("concepts")["concepts"]
    learner = st.get("learner")
    pos = course.get("position")
    order = unit_order(course)
    print(f"# Context: {course['title']}")
    print(f"position: {pos or '(not set)'}")
    print_guards(course)
    if pos:
        u = next(u for u in course["units"] if u["id"] == pos)
        print(f"current unit: {u['id']} {u['title']}")
    wanted = set(filter(None, (args.concepts or "").split(",")))
    if args.query:
        pat = re.compile(args.query, re.I)
        hits = [c for c in concepts if pat.search(" ".join([c["id"], c["name"], *c.get("aliases", []),
                                                              c.get("statement", "")]))]
        print(f"\n## Matches for /{args.query}/")
        for c in hits:
            scope = "in scope" if in_scope(course, c) else f"LATER ({c['unit']})"
            print(f"- {c['id']} [{c['unit']} {c.get('loc', '')}] {c['name']} — {scope}")
            wanted.add(c["id"])
    if wanted:
        idx = {c["id"]: c for c in concepts}
        print("\n## Concept details")
        for cid in sorted(wanted):
            c = idx.get(cid)
            if not c:
                print(f"- {cid}: unknown")
                continue
            rec = learner["concepts"].get(cid, {})
            print(f"- {cid} ({c['kind']}, {c['unit']} {c.get('loc', '')}): {c['name']}")
            for w in audit_warnings(st, course, c):
                print(f"  CHECK PAGE IMAGE: {w}")
            if c.get("notation"):
                print(f"  notation: {c['notation']}")
            if c.get("uses"):
                print(f"  uses: {', '.join(c['uses'])}")
            if rec:
                print(f"  learner: mastery {effective_mastery(rec)} (raw {rec.get('mastery')}), "
                      f"last seen {rec.get('last_seen')}, {len(rec.get('evidence', []))} evidence")
            open_m = [m for m in learner["misconceptions"] if m["concept"] == cid and m["status"] != "verified"]
            for m in open_m:
                print(f"  OPEN misconception {m['id']} ({m['status']}): {m['description']}")
    lim = order.get(pos, 1e9) if pos else 1e9
    seen = [c for c in concepts if order.get(c["unit"], 1e9) <= lim]
    print(f"\n## In scope: {len(seen)} of {len(concepts)} concepts (through {pos or 'end'})")
    if args.full:
        for c in seen:
            print(f"- {c['unit']} {c['id']}: {c['name']}")


def print_guards(course):
    if course.get("policy"):
        print(f"AI policy: {course['policy']}")
    for u in course["units"]:
        if u.get("status", "").lower().startswith("active"):
            print(f"ACTIVE ASSIGNMENT {u['id']} {u['title']} ({u['status']}): tutor the ideas; "
                  "give a full solution only when the learner explicitly asks, with a one-line policy reminder")


def cmd_course(args):
    st = state_from(args)
    course = st.get("course")
    if args.action == "set":
        if args.title:
            course["title"] = args.title
        if args.policy is not None:
            course["policy"] = args.policy
        st.put("course", course)
    print(json.dumps({k: course.get(k) for k in ("title", "policy", "position")}, indent=1, ensure_ascii=False))


PAGE_PY = r"""
import sys, pymupdf
src, out_dir, pages = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]]
doc = pymupdf.open(src)
for n in pages:
    out = f"{out_dir}/p{n:03d}.png"
    doc[n - 1].get_pixmap(dpi=150).save(out)
    print(out)
"""


AUDIT_PY = r"""
import json, re, sys, pymupdf
jobs = json.loads(sys.argv[1])
MATH = re.compile(r"\$\$.*?\$\$|\$[^$]*\$", re.S)
out = {}
for rel, pdf, md in jobs:
    text = open(md, encoding="utf-8").read()
    pages = re.split(r"<!-- page (\d+) -->", text)
    conv = {int(pages[i]): pages[i + 1] for i in range(1, len(pages) - 1, 2)}
    doc, flags = pymupdf.open(pdf), []
    for n, page in enumerate(doc, 1):
        ref = page.get_text().count("−")          # true minus glyphs in the PDF text layer
        got = sum(m.count("-") + m.count("−") for m in MATH.findall(conv.get(n, "")))
        if ref and got < ref:
            flags.append([n, ref, got])
    out[rel] = flags
print(json.dumps(out))
"""


def cmd_audit(args):
    """Flag pages where Marker's math has fewer minus signs than the PDF's text layer."""
    st = state_from(args)
    man = st.get("manifest")["sources"]
    jobs = []
    for rel, ent in man.items():
        if not ent.get("output") or not ent.get("converter", "").endswith("marker"):
            continue
        pdf = pptx_pdf_path(st, rel) if rel.lower().endswith(".pptx") else st.root / rel
        if pdf.exists():
            jobs.append([rel, str(pdf), str(st.dir / ent["output"])])
    r = subprocess.run([str(VENV_PY), "-I", "-c", AUDIT_PY, json.dumps(jobs)], capture_output=True, text=True)
    if r.returncode:
        die(f"audit failed: {r.stderr[-400:]}")
    res = json.loads(r.stdout)
    audit = {rel: [{"page": n, "pdf_minus": a, "converted_minus": b} for n, a, b in flags] for rel, flags in res.items()}
    save(st.dir / "audit.json", audit)
    total = 0
    for rel, flags in sorted(audit.items()):
        if flags:
            total += len(flags)
            print(f"{rel}: pages " + ", ".join(f"{f['page']}({f['converted_minus']}/{f['pdf_minus']})" for f in flags))
    print(f"{total} pages with possibly dropped minus signs (converted/pdf); saved .learn/audit.json. "
          "PDFs without a text layer (scans, handwriting) can't be audited this way.")


def cmd_page(args):
    """Render original pages to PNG, for reading a garbled formula or a figure."""
    st = state_from(args)
    rel = args.source.replace("\\", "/")
    src = pptx_pdf_path(st, rel) if rel.lower().endswith(".pptx") else st.root / rel
    if not src.exists():
        die(f"no PDF for {rel} (for .pptx, convert it first)")
    out_dir = st.dir / "cache" / "pages" / safe_name(rel)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(VENV_PY), "-I", "-c", PAGE_PY, str(src), str(out_dir), *map(str, args.pages)])
    if r.returncode:
        die("page render failed")

# ---------------------------------------------------------------- quiz
ITEM_TYPES = {"derive", "explain-why", "predict", "find-error", "counterexample", "limiting-case",
              "drop-assumption", "transfer", "which-method", "compute", "interpret-figure", "recall"}
ITEM_FIELDS = {"prompt", "type", "concepts", "reference_solution", "rubric", "check", "source",
               "targets_misconception", "unit"}


def fsrs_mod():
    """py-fsrs is pure Python; borrow it from the learning-skills venv so this script stays stdlib-run."""
    site = REPO / ".venv" / "Lib" / "site-packages"
    if str(site) not in sys.path:
        sys.path.append(str(site))
    try:
        import fsrs
    except ImportError:
        die(f"fsrs not found in {site}; run `uv sync` in {REPO}")
    return fsrs


def scheduler(fsrs):
    # One short learning step: a missed derivation comes back later in the same session,
    # then FSRS spacing takes over. Flashcard-style 1-minute steps make no sense for these items.
    step = (dt.timedelta(minutes=10),)
    return fsrs.Scheduler(learning_steps=step, relearning_steps=step, enable_fuzzing=True)


def quiz_state(st):
    return load(st.dir / "quiz.json", {"version": 1, "items": []})


def item_due(item):
    return dt.datetime.fromisoformat(item["card"]["due"])


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def scope_units(course, only=None):
    order = unit_order(course)
    lim = order.get(course.get("position"), 1e9) if course.get("position") else 1e9
    ok = {u for u, o in order.items() if o <= lim}
    return ok & set(only) if only else ok


def cmd_quiz(args):
    st = state_from(args)
    course = st.get("course")
    q = quiz_state(st)
    items = {i["id"]: i for i in q["items"]}
    concepts = concept_index(st)
    learner = st.get("learner")

    if args.action == "add":
        new = load(Path(args.file), None)
        new = new if isinstance(new, list) else [new]
        fsrs = fsrs_mod()
        order = unit_order(course)
        errors, added = [], []
        for k, it in enumerate(new):
            extra = set(it) - ITEM_FIELDS
            if extra:
                errors.append(f"[{k}] unknown fields {sorted(extra)}")
            for f in ("prompt", "type", "concepts", "reference_solution", "rubric"):
                if not it.get(f):
                    errors.append(f"[{k}] missing {f}")
            if it.get("type") and it["type"] not in ITEM_TYPES:
                errors.append(f"[{k}] type {it['type']!r} not in {sorted(ITEM_TYPES)}")
            bad = [c for c in it.get("concepts", []) if c not in concepts]
            if bad:
                errors.append(f"[{k}] unknown concepts {bad}")
            rub = it.get("rubric", [])
            if not isinstance(rub, list) or not all(isinstance(r, dict) and r.get("criterion") and
                                                   isinstance(r.get("points"), (int, float)) for r in rub):
                errors.append(f"[{k}] rubric must be a list of {{criterion, points}}")
            m = it.get("targets_misconception")
            if m and not any(x["id"] == m for x in learner["misconceptions"]):
                errors.append(f"[{k}] no misconception {m}")
        if errors:
            die("\n".join(errors))
        n = len(q["items"])
        for it in new:
            n += 1
            it["id"] = f"Q{n:03d}"
            it.setdefault("unit", max((concepts[c]["unit"] for c in it["concepts"]),
                                      key=lambda u: order.get(u, 0)))
            it["created"] = now()
            it["card"] = fsrs.Card().to_dict()
            it["history"] = []
            q["items"].append(it)
            added.append(it["id"])
        save(st.dir / "quiz.json", q)
        print("added " + ", ".join(added))
        return

    if args.action == "show":
        it = items.get(args.id) or die(f"no item {args.id}")
        print(f"{it['id']} [{it['type']}, {it['unit']}; concepts: {', '.join(it['concepts'])}]")
        print(it["prompt"])
        if args.solution:
            print("\n--- reference solution ---\n" + it["reference_solution"])
            print("\n--- rubric ---")
            for r in it["rubric"]:
                print(f"- ({r['points']}) {r['criterion']}")
            if it.get("check"):
                print(f"\ncheck: {it['check']}")
        return

    if args.action == "plan":
        only = set(filter(None, (args.units or "").split(",")))
        units = scope_units(course, only or None)
        t = utcnow()
        due = sorted((i for i in q["items"] if i["unit"] in units and item_due(i) <= t), key=item_due)
        retest = [m for m in learner["misconceptions"] if m["status"] == "addressed"
                  and concepts.get(m["concept"], {}).get("unit") in units]
        covered = {c for i in q["items"] for c in i["concepts"]}
        # cold-start tie-break: concepts many others build on, and results/methods over ideas
        dependents = {}
        for c in concepts.values():
            for u in c.get("uses", []):
                dependents[u] = dependents.get(u, 0) + 1
        kind_w = {"theorem": 2, "result": 2, "method": 2, "definition": 1.5, "proposition": 2, "lemma": 1.5}
        cands = []
        for c in concepts.values():
            if c["unit"] not in units or c["kind"] in ("example", "notation"):
                continue
            rec = learner["concepts"].get(c["id"], {})
            m = effective_mastery(rec)
            imp = dependents.get(c["id"], 0) + kind_w.get(c["kind"], 0.5)
            cands.append(((0.3 if m is None else m), c["id"] in covered, -imp, c))
        cands.sort(key=lambda x: (x[0], x[1], x[2]))
        cands = [(m, cov, c) for m, cov, _, c in cands]
        # interleave across units: round-robin over units, weakest first within each
        by_unit = {}
        for m, cov, c in cands:
            by_unit.setdefault(c["unit"], []).append((m, cov, c))
        picks, want = [], max(0, args.n - len(due[:args.n]))
        while len(picks) < want and any(by_unit.values()):
            for u in sorted(by_unit, key=lambda u: by_unit[u][0][0] if by_unit[u] else 9):
                if by_unit[u] and len(picks) < want:
                    picks.append(by_unit[u].pop(0))
        with_concepts = sorted({c["unit"] for c in concepts.values()} & units, key=lambda u: unit_order(course)[u])
        print(f"# Quiz plan (scope: {', '.join(with_concepts)})")
        print(f"\n## Due reviews ({len(due)})")
        for i in due[:args.n]:
            print(f"- {i['id']} [{i['type']}, {i['unit']}] due {i['card']['due'][:16]}: {i['prompt'][:90]}")
        print(f"\n## Misconceptions to re-test ({len(retest)})")
        for m in retest:
            print(f"- {m['id']} `{m['concept']}`: {m['description']}")
        print(f"\n## New items to write ({len(picks)}), weakest first, interleaved")
        for m, cov, c in picks:
            where = f"{c['unit']} {c['loc']}" if c.get("loc") else c["unit"]
            print(f"- {c['id']} ({where}, {c['kind']}; mastery {m}"
                  f"{'; has items' if cov else ''}): {c['name']}")
        return

    if args.action == "record":
        it = items.get(args.id) or die(f"no item {args.id}")
        if not 0 <= args.score <= 1:
            die("--score is the rubric fraction in [0, 1]")
        if args.confidence not in (1, 2, 3, 4, 5):
            die("--confidence must be 1-5 (asked BEFORE feedback)")
        fsrs = fsrs_mod()
        rating = args.rating or (1 if args.score < 0.5 else 2 if args.score < 0.8 else
                                 4 if args.score >= 0.95 and args.confidence >= 4 else 3)
        card, _ = scheduler(fsrs).review_card(fsrs.Card.from_dict(it["card"]), fsrs.Rating(rating))
        it["card"] = card.to_dict()
        it["history"].append({"date": now(), "score": args.score, "confidence": args.confidence,
                              "rating": rating, "notes": args.notes})
        kind = "correct" if args.score >= 0.8 else "partial" if args.score >= 0.5 else "incorrect"
        for cid in it["concepts"]:
            rec = touch_concept(learner, cid)
            rec["evidence"].append({"date": now(), "kind": kind, "note": f"{it['id']}: {args.notes}",
                                    "via": "quiz"})
            base = 0.3 if rec["mastery"] is None else rec["mastery"]
            rec["mastery"] = round(min(1.0, max(0.0, base + EVIDENCE_DELTA[kind])), 2)
            rec["last_seen"] = now()
        learner["calibration"].append({"date": now(), "item": it["id"], "confidence": args.confidence,
                                       "score": args.score})
        save(st.dir / "quiz.json", q)
        st.put("learner", learner)
        names = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
        print(f"{it['id']}: score {args.score}, confidence {args.confidence} -> {names[rating]}; "
              f"next due {it['card']['due'][:16]} UTC")
        m = it.get("targets_misconception")
        if m and args.score >= 0.8:
            print(f"NOTE: {m} was re-tested and answered correctly; if it was 'addressed', run "
                  f"`misc set --id {m} --status verified --note \"{it['id']} correct\"`")
        return

    if args.action == "list":
        t = utcnow()
        for i in q["items"]:
            flag = "DUE " if item_due(i) <= t else "    "
            last = i["history"][-1]["score"] if i["history"] else "-"
            print(f"{flag}{i['id']} [{i['type']:<15} {i['unit']}] last {last} due {i['card']['due'][:10]}: "
                  f"{i['prompt'][:70]}")
        return

    # stats
    cal = learner["calibration"]
    t = utcnow()
    print(f"items: {len(q['items'])}  due now: {sum(item_due(i) <= t for i in q['items'])}  "
          f"reviews: {sum(len(i['history']) for i in q['items'])}")
    if cal:
        print("\nconfidence  n  mean score")
        for c in range(1, 6):
            xs = [x["score"] for x in cal if x["confidence"] == c]
            if xs:
                print(f"{c:>10} {len(xs):>3}  {sum(xs) / len(xs):.2f}")
        bias = sum((x["confidence"] - 1) / 4 - x["score"] for x in cal) / len(cal)
        print(f"\nover/under-confidence (mean of confidence-as-fraction minus score): {bias:+.2f}"
              f"  ({'overconfident' if bias > 0.1 else 'underconfident' if bias < -0.1 else 'well calibrated'})")


def touch_concept(learner, cid):
    return learner["concepts"].setdefault(cid, {"mastery": None, "evidence": [], "last_seen": None})


def cmd_evidence(args):
    st = state_from(args)
    if args.concept not in concept_index(st):
        die(f"unknown concept {args.concept!r} (concept list --grep ...)")
    if args.kind not in EVIDENCE_DELTA:
        die(f"kind must be one of {sorted(EVIDENCE_DELTA)}")
    learner = st.get("learner")
    rec = touch_concept(learner, args.concept)
    rec["evidence"].append({"date": now(), "kind": args.kind, "note": args.note, "via": args.via})
    delta = EVIDENCE_DELTA[args.kind]
    if delta or rec["mastery"] is not None:
        base = 0.3 if rec["mastery"] is None else rec["mastery"]
        rec["mastery"] = round(min(1.0, max(0.0, base + delta)), 2)
    rec["last_seen"] = now()
    st.put("learner", learner)
    print(f"{args.concept}: mastery {rec['mastery']}")


def cmd_misc(args):
    st = state_from(args)
    learner = st.get("learner")
    ms = learner["misconceptions"]
    if args.action == "list":
        for m in ms:
            print(f"{m['id']:<5} {m['status']:<10} {m['concept']:<28} {m['description']}")
        return
    if args.action == "add":
        if args.concept not in concept_index(st):
            die(f"unknown concept {args.concept!r}")
        mid = f"M{len(ms) + 1}"
        ms.append({"id": mid, "concept": args.concept, "description": args.desc, "status": "observed",
                   "first_seen": now(), "history": [{"date": now(), "status": "observed", "note": args.note or ""}]})
        touch_concept(learner, args.concept)["last_seen"] = now()
        st.put("learner", learner)
        print(f"{mid} observed")
        return
    m = next((m for m in ms if m["id"] == args.id), None)
    if not m:
        die(f"no misconception {args.id}")
    if args.status not in MISC_FLOW.get(m["status"], set()):
        die(f"{m['status']} -> {args.status} not allowed; flow is observed -> addressed -> verified "
            "(verified only after a LATER item re-tests it and the learner gets it right)")
    if not args.note:
        die("--note required: say what evidence justifies the change")
    m["status"] = args.status
    m["history"].append({"date": now(), "status": args.status, "note": args.note})
    st.put("learner", learner)
    print(f"{m['id']} -> {args.status}")


def cmd_log(args):
    st = state_from(args)
    st.log(args.kind, args.text)
    print("logged")


def cmd_render(args):
    st = state_from(args)
    course, concepts = st.get("course"), st.get("concepts")["concepts"]
    man, learner = st.get("manifest")["sources"], st.get("learner")
    by_unit = {}
    for c in concepts:
        by_unit.setdefault(c["unit"], []).append(c)
    lines = [f"# {course['title']}", "",
             "Generated by learnctl.py render; do not edit by hand.", "",
             f"Position: **{course.get('position') or 'not set'}** · "
             f"{len(course['units'])} units · {len(concepts)} concepts · {len(man)} sources", ""]
    if course.get("policy"):
        lines += ["## Course AI policy", "", course["policy"], ""]
    lines += ["## Units", ""]
    for u in course["units"]:
        outs = [man[s]["output"] for s in u.get("sources", []) if s in man and man[s].get("output")]
        tag = "" if u.get("kind", "lecture") == "lecture" else f" [{u['kind']}]"
        lines.append(f"### {u['id']} — {u['title']}{tag}" + (f" — *{u['status']}*" if u.get("status") else ""))
        if u.get("summary"):
            lines.append(u["summary"])
        if outs:
            lines.append("Sources: " + ", ".join(f"`.learn/{o}`" for o in outs))
        cs = by_unit.get(u["id"], [])
        if cs:
            lines.append("Introduces: " + "; ".join(f"{c['name']} (`{c['id']}`)" for c in cs))
        lines.append("")
    unassigned = sorted(set(man) - {s for u in course["units"] for s in u.get("sources", [])})
    if unassigned:
        lines += ["## Sources not assigned to a unit", ""] + [f"- {s}" for s in unassigned] + [""]
    open_m = [m for m in learner["misconceptions"] if m["status"] != "verified"]
    if open_m:
        lines += ["## Open misconceptions", ""] + [f"- {m['id']} ({m['status']}) `{m['concept']}`: "
                                                  f"{m['description']}" for m in open_m] + [""]
    (st.dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {st.dir / 'index.md'}")


def cmd_status(args):
    st = state_from(args)
    course, concepts, learner = st.get("course"), st.get("concepts")["concepts"], st.get("learner")
    s = scan(st)
    pending = len(s["new"]) + len(s["changed"]) + len(s["unconverted"])
    print(f"course: {course['title']}  ({st.root})")
    print(f"position: {course.get('position') or 'not set'}")
    print_guards(course)
    print(f"units: {len(course['units'])}  concepts: {len(concepts)}  sources: "
          f"{len(st.get('manifest')['sources'])} (pending {pending}, removed {len(s['removed'])})")
    q = quiz_state(st)
    if q["items"]:
        t = utcnow()
        print(f"quiz: {len(q['items'])} items, {sum(item_due(i) <= t for i in q['items'])} due now")
    print(f"learner: {len(learner['concepts'])} concepts touched, "
          f"{sum(m['status'] != 'verified' for m in learner['misconceptions'])} open misconceptions")
    if pending:
        print("pending:", ", ".join(s["new"] + s["changed"] + s["unconverted"]))


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--title"); p.set_defaults(f=cmd_init)
    sub.add_parser("scan").set_defaults(f=cmd_scan)
    p = sub.add_parser("convert"); p.add_argument("paths", nargs="*"); p.add_argument("--pending", action="store_true")
    p.add_argument("--dry-run", action="store_true"); p.set_defaults(f=cmd_convert)

    p = sub.add_parser("unit"); p.add_argument("action", choices=["add", "update", "remove", "list"])
    p.add_argument("--id"); p.add_argument("--order", type=int); p.add_argument("--title")
    p.add_argument("--sources", nargs="*"); p.add_argument("--summary"); p.add_argument("--kind")
    p.add_argument("--status", help="e.g. 'active: no solutions released' or 'solutions released'")
    p.set_defaults(f=cmd_unit)

    p = sub.add_parser("course"); p.add_argument("action", choices=["set", "show"])
    p.add_argument("--title"); p.add_argument("--policy", help="the course's rules on AI use")
    p.set_defaults(f=cmd_course)

    sub.add_parser("audit").set_defaults(f=cmd_audit)

    p = sub.add_parser("page"); p.add_argument("source"); p.add_argument("pages", nargs="+", type=int)
    p.set_defaults(f=cmd_page)

    p = sub.add_parser("concept"); p.add_argument("action", choices=["import", "list", "move"])
    p.add_argument("--to"); p.add_argument("--ids"); p.add_argument("--from-unit", dest="from_unit")
    p.add_argument("--loc-prefix", dest="loc_prefix")
    p.add_argument("file", nargs="?"); p.add_argument("--upto"); p.add_argument("--unit"); p.add_argument("--grep")
    p.set_defaults(f=cmd_concept)

    p = sub.add_parser("position"); p.add_argument("action", choices=["set", "show"]); p.add_argument("unit", nargs="?")
    p.set_defaults(f=cmd_position)

    p = sub.add_parser("context"); p.add_argument("--query"); p.add_argument("--concepts")
    p.add_argument("--full", action="store_true"); p.set_defaults(f=cmd_context)

    p = sub.add_parser("evidence"); p.add_argument("action", choices=["add"]); p.add_argument("--concept", required=True)
    p.add_argument("--kind", required=True); p.add_argument("--note", default=""); p.add_argument("--via", default="learn")
    p.set_defaults(f=cmd_evidence)

    p = sub.add_parser("misc"); p.add_argument("action", choices=["add", "set", "list"])
    p.add_argument("--concept"); p.add_argument("--desc"); p.add_argument("--id"); p.add_argument("--status")
    p.add_argument("--note"); p.set_defaults(f=cmd_misc)

    p = sub.add_parser("quiz"); p.add_argument("action", choices=["add", "show", "plan", "record", "list", "stats"])
    p.add_argument("target", nargs="?", help="FILE.json for add, item id for show/record")
    p.add_argument("--solution", action="store_true"); p.add_argument("--n", type=int, default=5)
    p.add_argument("--units", help="comma-separated unit ids to restrict to")
    p.add_argument("--score", type=float); p.add_argument("--confidence", type=int)
    p.add_argument("--rating", type=int, choices=[1, 2, 3, 4]); p.add_argument("--notes", default="")
    p.set_defaults(f=cmd_quiz)

    p = sub.add_parser("log"); p.add_argument("--kind", required=True); p.add_argument("--text", required=True)
    p.set_defaults(f=cmd_log)
    sub.add_parser("render").set_defaults(f=cmd_render)
    sub.add_parser("status").set_defaults(f=cmd_status)

    args = ap.parse_args()
    if args.cmd == "concept" and args.action == "import" and not args.file:
        die("concept import needs FILE")
    if args.cmd == "quiz":
        if args.action in ("add", "show", "record") and not args.target:
            die(f"quiz {args.action} needs a target")
        args.file = args.id = args.target
        if args.action == "record" and (args.score is None or args.confidence is None):
            die("quiz record needs --score and --confidence")
    args.f(args)


if __name__ == "__main__":
    main()
