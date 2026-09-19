#!/usr/bin/env python3
"""Convert a Claude Code session transcript (JSONL) to a PDF (via pandoc + xelatex).

Usage: convo2pdf.py [basename] [--session ID | --file PATH] [--tools] [--thinking] [--skills]
Writes <basename>.pdf and <basename>.md; refuses to overwrite existing files.
Defaults to the most recently modified transcript for the current directory's project.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
NOISE = re.compile(r"<(system-reminder|ide_[a-z_]+|command-[a-z-]+|local-command-[a-z-]+)>.*?</\1>", re.S)
CMD = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>(?:.*?<command-args>(.*?)</command-args>)?", re.S)

# raw_tex is off: transcripts can contain LaTeX (or hostile \input) that must be printed, not run.
# The header and Lua filters (next to this script) wrap long code lines, inline code and URLs at the margin
# and leave only http(s) links clickable.
HERE = Path(__file__).resolve().parent
PANDOC_PDF = ["--pdf-engine=xelatex", "-f", "markdown+lists_without_preceding_blankline+autolink_bare_uris-raw_tex",
              "-V", "geometry:margin=1in", "-V", "fontsize=11pt", "-V", "colorlinks=true", "-V", "papersize=a4",
              "-H", str(HERE / "pdf-header.tex"), "--lua-filter", str(HERE / "pdf-code.lua"),
              "--lua-filter", str(HERE / "pdf-links.lua")]

# Preferred fonts (VS Code preview look), first installed one wins; Windows fonts come last, and
# Latin Modern (ships with TeX Live) is used when none is installed.
SANS = ["Segoe UI", "Inter", "Ubuntu", "Noto Sans", "Roboto", "Open Sans", "Lato", "Liberation Sans", "DejaVu Sans",
        "Calibri", "Verdana", "Tahoma", "Trebuchet MS", "Arial"]
MONO = ["Cascadia Mono", "JetBrains Mono", "Consolas", "Ubuntu Mono", "Noto Sans Mono", "Liberation Mono", "DejaVu Sans Mono",
        "Lucida Console", "Courier New"]
FALLBACK = ("Latin Modern Sans", "Latin Modern Mono")

def pick_fonts():
    r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True) if shutil.which("fc-list") else None
    have = {f.strip() for line in (r.stdout.splitlines() if r else []) for f in line.split(",")}
    first = lambda names, default: next((n for n in names if n in have), default)
    return ["-V", f"mainfont={first(SANS, FALLBACK[0])}", "-V", f"monofont={first(MONO, FALLBACK[1])}", "-V", "monofontoptions=Scale=MatchLowercase"]

def find_transcript(a):
    if a.file: return Path(a.file)
    if a.session:
        hits = glob.glob(str(PROJECTS / "*" / f"{a.session}.jsonl"))
        if hits: return Path(hits[0])
        sys.exit(f"No transcript found for session {a.session}")
    proj = PROJECTS / re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
    files = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files: sys.exit(f"No transcripts in {proj}")
    return files[-1]

def blocks(msg):
    c = msg.get("content")
    return [{"type": "text", "text": c}] if isinstance(c, str) else (c or [])

def fence(s, lang=""):
    tick = "```" if "```" not in s else "~~~~"
    return f"\n{tick}{lang}\n{s.rstrip()}\n{tick}\n"

def call(name, args):
    return "`" + " ".join(f"/{name} {args or ''}".split()).replace("`", "'") + "`"

def parse(path, tools, thinking, skills=False):
    turns, title, first_ts, pending = [], None, None, False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try: d = json.loads(line)
        except json.JSONDecodeError: continue
        t = d.get("type")
        if t == "ai-title": title = d.get("aiTitle") or d.get("title") or title
        if t not in ("user", "assistant") or d.get("isSidechain"): continue
        first_ts = first_ts or d.get("timestamp")
        if d["type"] == "user" and d.get("isMeta") and pending:
            pending = False
            body = NOISE.sub("", "\n".join(b.get("text", "") for b in blocks(d["message"]) if b.get("type") == "text")).strip()
            if skills and body and turns: turns[-1][1] += "\n\n**Skill prompt**" + fence(body)
            continue
        parts = []
        for b in blocks(d["message"]):
            bt = b.get("type")
            if bt == "text":
                m = CMD.search(b["text"])
                if m: pending = True
                txt = call(*m.groups()) if m else NOISE.sub("", b["text"]).strip()
                if txt: parts.append(txt)
            elif bt == "thinking" and thinking and b.get("thinking"):
                parts.append("*Thinking:* " + b["thinking"].strip())
            elif bt == "tool_use" and b.get("name") == "Skill" and (b.get("input") or {}).get("skill"):
                pending = True
                parts.append(call(b["input"]["skill"], b["input"].get("args")))
            elif bt == "tool_use" and tools:
                inp = b.get("input", {})
                summ = inp.get("command") or inp.get("file_path") or inp.get("description") or json.dumps(inp)[:300]
                parts.append(f"**Tool: {b.get('name')}**" + fence(str(summ)))
            elif bt == "tool_result" and tools:
                out = b.get("content")
                if isinstance(out, list): out = "\n".join(x.get("text", "") for x in out if isinstance(x, dict))
                out = str(out or "")
                parts.append("**Result**" + fence(out[:2000] + ("\n… [truncated]" if len(out) > 2000 else "")))
        if not parts: continue
        is_result = d["type"] == "user" and all(b.get("type") == "tool_result" for b in blocks(d["message"]))
        role = "aux" if is_result else d["type"]
        text = "\n\n".join(parts)
        if turns and turns[-1][0] == role and role != "user":
            turns[-1][1] += "\n\n" + text
        else:
            turns.append([role, text])
    return turns, title, first_ts

LABELS = {"user": "You", "assistant": "Claude", "aux": "Tool output"}

def to_markdown(turns, title, first_ts, path):
    date = datetime.fromisoformat(first_ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M") if first_ts else ""
    out = [f"# {title or 'Claude conversation'}", f"*{date} · session {path.stem}*"]
    for role, text in turns:
        out.append(f"## {LABELS[role]}\n\n{text}")
    return "\n\n".join(out) + "\n"

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "conversation"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("basename", nargs="*", help="output file basename (no extension needed; may include a directory)")
    ap.add_argument("--session"); ap.add_argument("--file")
    ap.add_argument("--tools", action="store_true", help="include tool calls and results")
    ap.add_argument("--thinking", action="store_true", help="include thinking blocks")
    ap.add_argument("--skills", action="store_true", help="include the full prompt of each skill call")
    a = ap.parse_args()
    if not shutil.which("pandoc"): sys.exit("pandoc is required but not found on PATH (https://pandoc.org/installing.html).")
    if not shutil.which("xelatex"): sys.exit("xelatex is required but not found on PATH (install texlive-xetex).")
    if shutil.which("kpsewhich") and not subprocess.run(["kpsewhich", "fvextra.sty"], capture_output=True, text=True).stdout.strip():
        sys.exit("The LaTeX package fvextra is required but not found (install texlive-latex-extra).")
    path = find_transcript(a)
    turns, title, ts = parse(path, a.tools, a.thinking, a.skills)
    if not turns: sys.exit("Transcript has no printable messages.")
    base = " ".join(a.basename).strip()
    base = re.sub(r"\.(pdf|md)$", "", base, flags=re.I)
    base = Path(base or f"convo-{slug(title or '')}-{datetime.now():%Y%m%d-%H%M%S}").expanduser().resolve()
    out, md = base.parent / (base.name + ".pdf"), base.parent / (base.name + ".md")
    taken = [f for f in (out, md) if f.exists()]
    if taken:
        sys.exit("Nothing was written because these files already exist:\n"
                 + "".join(f"  {f}\n" for f in taken)
                 + "Re-run with a different name, e.g. /convo2pdf " + base.name + "-2, or delete/rename the existing file(s).")
    if not base.parent.is_dir(): sys.exit(f"Folder does not exist: {base.parent}")
    md.write_text(to_markdown(turns, title, ts, path), encoding="utf-8")
    r = subprocess.run(["pandoc", str(md), "-o", str(out), *PANDOC_PDF, *pick_fonts()], capture_output=True, text=True)
    if r.returncode or not out.exists():
        md.unlink(missing_ok=True)
        sys.exit(f"PDF generation failed:\n{r.stderr[-800:]}")
    print(out); print(md)

if __name__ == "__main__":
    main()
