# convo2pdf

A [Claude Code](https://claude.com/claude-code) skill that turns your current conversation into a PDF, plus a Markdown copy, with one command:

```
/convo2pdf
/convo2pdf design-chat
```

It reads the session transcript Claude Code already keeps on disk, so nothing is re-summarized or re-generated. The output is your messages and Claude's replies, with code blocks, tables and lists intact.

## Requirements

- Claude Code (CLI, desktop, or IDE extension)
- Python 3.8+ (standard library only)
- [pandoc](https://pandoc.org/installing.html)
- A XeLaTeX install, which pandoc uses as its PDF engine (`texlive-xetex` on Debian/Ubuntu), plus the `fvextra` and `xurl` LaTeX packages (`texlive-latex-extra` on Debian/Ubuntu), which wrap long lines

Tested on Linux. macOS should work; Windows is untested.

## Install

Clone into your personal skills folder. The folder name must be `convo2pdf`, because `SKILL.md` refers to the script by that path.

```bash
git clone <this-repo-url> ~/.claude/skills/convo2pdf
```

Start a new Claude Code session (or reload skills) and `/convo2pdf` will be available in every project.

### Installing pandoc and XeLaTeX

pandoc converts the Markdown copy of the transcript to PDF through XeLaTeX, so the skill won't run without both. Install them with your package manager:

```bash
sudo apt install pandoc texlive-xetex texlive-latex-extra   # Debian, Ubuntu
sudo dnf install pandoc texlive-xetex texlive-fvextra texlive-xurl   # Fedora
sudo pacman -S pandoc texlive-xetex texlive-latexextra      # Arch
brew install pandoc && brew install --cask mactex-no-gui   # macOS (Homebrew)
```

Other platforms and standalone installers are listed on the [pandoc install page](https://pandoc.org/installing.html). Check that they work with `pandoc --version` and `xelatex --version`.

## Usage

```
/convo2pdf [basename] [--tools] [--thinking] [--skills] [--page-size a4|letter]
```

| Argument | Effect |
| --- | --- |
| *(none)* | Writes `convo-<title>-<YYYYMMDD-HHMMSS>.pdf` and `.md` in the current directory |
| `basename` | Writes `<basename>.pdf` and `<basename>.md`. A `.pdf`/`.md` extension or a directory prefix is accepted; spaces are fine |
| `--tools` | Also include tool calls and their output (each result truncated to 2000 characters) |
| `--thinking` | Also include Claude's thinking blocks |
| `--skills` | Also include the full prompt each skill call expands to (otherwise a skill call is just `/skillname`) |
| `--page-size a4\|letter` | PDF page size (default `a4`) |

**It never overwrites.** If either output file already exists, nothing is written and you get an error naming the files in the way.

### Using the script directly

You can convert any transcript, including old sessions, without Claude Code running:

```bash
python3 convo2pdf.py --file ~/.claude/projects/<project>/<session-id>.jsonl my-export
python3 convo2pdf.py --session <session-id>
```

Without `--file` or `--session`, it uses the newest transcript for the current directory's project.

## What is and isn't included

Included: your messages, Claude's replies, skill calls as `/skillname`, the conversation title and start time.

Left out by default: tool calls and results, thinking, skill prompts, IDE context tags, system reminders, and sub-agent (sidechain) messages.

## Privacy and safety

- Everything runs locally. No network access is needed or used.
- Exports contain your full conversation text. Check them before sharing, since conversations can include file contents, paths or secrets that came up along the way.
- Transcripts can contain raw HTML (for example from fetched web pages). Raw HTML is dropped from the PDF, and raw LaTeX is disabled (`-raw_tex`), so LaTeX in a transcript is printed literally instead of being run by XeLaTeX.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests use a synthetic transcript in `tests/sample.jsonl`. The CLI tests are skipped if pandoc or xelatex is missing. See [CLAUDE.md](CLAUDE.md) for the code layout and conventions.

## Limitations

- The transcript file format is an internal detail of Claude Code and may change between versions. If exports come out empty or garbled, please open an issue with your Claude Code version.
- Images pasted into the conversation are not embedded.
- Only Internet links (`http://` and `https://`) are clickable in the PDF; links to local files (such as `[file.ts](src/file.ts)`) appear as plain text. The `.md` copy keeps every link.
- The PDF uses the first installed sans-serif font from a preferred list (Segoe UI, Inter, Ubuntu, Noto Sans, …, then Windows fonts ending in Arial, and Latin Modern Sans if none is installed) and a matching monospace font, so characters they lack (emoji, some symbols, CJK) can come out blank. Long lines in code blocks and inline code wrap at the margin (code blocks show a small arrow at each wrap). The `.md` copy always has the full text.
- Very long tool output is truncated; use the `.md` or the raw transcript if you need everything.

## License

GPLv3. See [LICENSE](LICENSE).
