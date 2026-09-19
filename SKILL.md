---
name: convo2pdf
description: Convert the current Claude conversation (session transcript) to a PDF file. Use when the user invokes /convo2pdf or asks to export, save, or print this conversation as a PDF.
disable-model-invocation: true
argument-hint: "[basename] [--tools] [--thinking] [--skills] [--page-size a4|letter]"
allowed-tools: Bash(python3 ~/.claude/skills/convo2pdf/convo2pdf.py:*)
---

Export this conversation to PDF by running the bundled script. Do not summarize or rewrite the conversation; the script reads the raw transcript.

```bash
python3 ~/.claude/skills/convo2pdf/convo2pdf.py --session ${CLAUDE_SESSION_ID} $ARGUMENTS
```

Arguments (all optional):
- A file basename (e.g. `/convo2pdf design-chat`) names the output files `design-chat.pdf` and `design-chat.md`. A `.pdf`/`.md` extension or a directory prefix is accepted. If omitted, a name is generated from the conversation title and timestamp.
- `--tools` includes tool calls and their (truncated) output. Default is only your messages and Claude's replies.
- `--thinking` includes thinking blocks.
- `--skills` includes the full prompt of each skill call. By default a skill call is shown only as `/skillname`.
- `--page-size a4|letter` sets the PDF page size. Default is `a4`.

By default the PDF is written to the current directory as `convo-<title>-<YYYYMMDD-HHMMSS>.pdf`, with a Markdown copy of the conversation saved next to it under the same name (`.md`). The script prints both absolute paths; report them to the user in one line. The script never overwrites: if either output file already exists it writes nothing and exits with a friendly error. If it fails, show the user that error message as-is and suggest a different name.
