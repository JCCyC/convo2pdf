# convo2pdf

Claude Code skill: `/convo2pdf` exports the current session transcript to `<name>.pdf` and `<name>.md`.

## Layout

- `SKILL.md`: the skill definition. It runs the script with `--session ${CLAUDE_SESSION_ID} $ARGUMENTS`. The path `~/.claude/skills/convo2pdf/convo2pdf.py` is hardcoded in the command and in `allowed-tools`, so keep the install folder name.
- `convo2pdf.py`: the whole implementation, standard library only.
- `tests/`: `unittest` tests and a synthetic fixture (`sample.jsonl`).

## Pipeline

`find_transcript` → `parse` (JSONL → list of `[role, markdown]` turns) → `to_markdown` (the `.md` output) → `pandoc <md> -o <pdf> --pdf-engine=xelatex` (flags in `PANDOC_PDF`), with `pdf-header.tex` (fvextra/xurl so code blocks and URLs wrap) `pdf-code.lua` (inline code that can wrap) and `pdf-links.lua` (only http(s) links stay clickable) next to the script. The PDF is built from the `.md` file, so there is no HTML or CSS step.

## Commands

- Run tests: `python3 -m unittest discover -s tests -v`
- Try it: `python3 convo2pdf.py --file tests/sample.jsonl /tmp/demo`

## Rules to keep

- **Never overwrite existing files.** The collision check happens before any work and covers both `.pdf` and `.md`. If PDF generation fails, the `.md` written in that run is removed.
- **Standard library only.** External tools are pandoc and xelatex (`texlive-xetex`), both checked up front with a clear error, as is the `fvextra` LaTeX package (`texlive-latex-extra`).
- **Keep `-raw_tex` in `PANDOC_PDF`** (the input format is `markdown+lists_without_preceding_blankline-raw_tex`). Transcripts can hold LaTeX or hostile `\input`, which must be printed, not run. Raw HTML is dropped by pandoc's LaTeX writer.
- **Errors go through `sys.exit("message")`** in plain language, since `SKILL.md` tells Claude to show them to the user unchanged.
- **Fixtures must be synthetic.** Never commit a real transcript; they contain private data.
- Transcript format (`~/.claude/projects/<cwd with non-alphanumerics as "-">/<session>.jsonl`) is undocumented and can change. `parse` skips lines and blocks it does not understand instead of failing.
- Keep the code style compact and comment-light, matching the existing file.

## When changing behavior

Update `SKILL.md` (Claude reads it), `README.md` (users read it), and add or adjust a test.
