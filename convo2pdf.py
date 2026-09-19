#!/usr/bin/env python3
"""Convert a Claude Code session transcript (JSONL) to a PDF.

Usage: convo2pdf.py [basename] [--session ID | --file PATH] [--tools] [--thinking]
Writes <basename>.pdf and <basename>.md; refuses to overwrite existing files.
Defaults to the most recently modified transcript for the current directory's project.
"""
import argparse, glob, html, json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
NOISE = re.compile(r"<(system-reminder|ide_[a-z_]+|command-[a-z-]+|local-command-[a-z-]+)>.*?</\1>", re.S)

# Transcripts can contain raw HTML (e.g. fetched web pages); never let it run script or hit the network.
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font: 10.5pt/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1f2328; }
h1.title { font-size: 20pt; margin: 0 0 2pt; } .meta { color: #656d76; font-size: 9pt; margin-bottom: 14pt; }
.turn { margin: 0 0 12pt; padding: 8pt 12pt; border-left: 3px solid; border-radius: 3px; }
.user { background: #eef4fd; border-color: #4a90e2; } .assistant { background: #f6f8fa; border-color: #8c959f; }
.role { font-weight: 700; font-size: 8.5pt; text-transform: uppercase; letter-spacing: .06em; color: #57606a; margin-bottom: 3pt; }
.aux { background: #fffbea; border-color: #d4a72c; font-size: 9pt; }
pre { background: #f0f2f4; padding: 6pt 8pt; border-radius: 3px; white-space: pre-wrap; word-wrap: break-word; font-size: 8.5pt; }
code { font-family: "DejaVu Sans Mono", Menlo, monospace; font-size: 88%; }
table { border-collapse: collapse; } th, td { border: 1px solid #d0d7de; padding: 3pt 7pt; }
img { max-width: 100%; } p { margin: 4pt 0; } .turn { break-inside: auto; }
"""

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

def parse(path, tools, thinking):
    turns, title, first_ts = [], None, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try: d = json.loads(line)
        except json.JSONDecodeError: continue
        t = d.get("type")
        if t == "ai-title": title = d.get("aiTitle") or d.get("title") or title
        if t not in ("user", "assistant") or d.get("isSidechain"): continue
        first_ts = first_ts or d.get("timestamp")
        parts = []
        for b in blocks(d["message"]):
            bt = b.get("type")
            if bt == "text":
                txt = NOISE.sub("", b["text"]).strip()
                if txt: parts.append(txt)
            elif bt == "thinking" and thinking and b.get("thinking"):
                parts.append("*Thinking:* " + b["thinking"].strip())
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

def render(turns, title, first_ts, path):
    md = []
    for role, text in turns:
        label = LABELS[role]
        md.append(f'<div class="turn {role}">\n<div class="role">{label}</div>\n\n{text}\n\n</div>\n')
    body = subprocess.run(["pandoc", "-f", "gfm+raw_html", "-t", "html5"], input="\n".join(md),
                          capture_output=True, text=True, check=True).stdout
    date = datetime.fromisoformat(first_ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M") if first_ts else ""
    t = html.escape(title or "Claude conversation")
    return (f'<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{CSP}">'
            f'<title>{t}</title><style>{CSS}</style>'
            f'<h1 class="title">{t}</h1><div class="meta">{date} · session {path.stem}</div>{body}')

BROWSERS = ("chromium", "google-chrome", "google-chrome-stable", "chromium-browser", "chrome",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium")

def find_browser():
    return next((p for b in BROWSERS if (p := shutil.which(b))), None)

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "conversation"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("basename", nargs="*", help="output file basename (no extension needed; may include a directory)")
    ap.add_argument("--session"); ap.add_argument("--file")
    ap.add_argument("--tools", action="store_true", help="include tool calls and results")
    ap.add_argument("--thinking", action="store_true", help="include thinking blocks")
    a = ap.parse_args()
    if not shutil.which("pandoc"): sys.exit("pandoc is required but not found on PATH (https://pandoc.org/installing.html).")
    browser = find_browser()
    if not browser: sys.exit("Chromium or Google Chrome is required but not found on PATH.")
    path = find_transcript(a)
    turns, title, ts = parse(path, a.tools, a.thinking)
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
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "c.html"; h.write_text(render(turns, title, ts, path), encoding="utf-8")
        cmd = [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
               f"--user-data-dir={td}/prof", f"--print-to-pdf={out}", h.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not out.exists():  # Chrome refuses to sandbox as root / in some containers
            r = subprocess.run(cmd[:2] + ["--no-sandbox"] + cmd[2:], capture_output=True, text=True)
    if not out.exists():
        md.unlink(missing_ok=True)
        sys.exit(f"PDF generation failed:\n{r.stderr[-800:]}")
    print(out); print(md)

if __name__ == "__main__":
    main()
