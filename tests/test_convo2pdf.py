import json, re, subprocess, sys, unittest, tempfile, shutil
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import convo2pdf as c  # noqa: E402

SAMPLE = HERE / "sample.jsonl"
SCRIPT = HERE.parent / "convo2pdf.py"


class ParseTests(unittest.TestCase):
    def test_default_hides_noise_thinking_tools_and_sidechains(self):
        turns, title, ts = c.parse(SAMPLE, tools=False, thinking=False)
        text = c.to_markdown(turns, title, ts, SAMPLE)
        self.assertEqual(title, "Sample chat")
        self.assertIn("How do I list files?", text)
        for hidden in ("secret/path.py", "hidden", "pondering", "ls -la", "file1", "SIDECHAIN", "SKILL-BODY", "Launching skill"):
            self.assertNotIn(hidden, text)

    def test_tools_and_thinking_flags(self):
        turns, title, ts = c.parse(SAMPLE, tools=True, thinking=True)
        text = c.to_markdown(turns, title, ts, SAMPLE)
        for shown in ("pondering", "ls -la", "file1"):
            self.assertIn(shown, text)

    def test_skill_calls_show_only_the_name_unless_skills_flag(self):
        turns, title, ts = c.parse(SAMPLE, tools=False, thinking=False)
        text = c.to_markdown(turns, title, ts, SAMPLE)
        self.assertIn("`/demo --fast now`", text)
        self.assertIn("`/init`", text)
        turns, title, ts = c.parse(SAMPLE, tools=False, thinking=False, skills=True)
        text = c.to_markdown(turns, title, ts, SAMPLE)
        for shown in ("SLASH-SKILL-BODY", "TOOL-SKILL-BODY"):
            self.assertIn(shown, text)


@unittest.skipUnless(shutil.which("pandoc"), "needs pandoc")
class LinkTests(unittest.TestCase):
    def test_only_http_links_stay_clickable(self):
        md = "[a](src/x.ts#L4) [b](/etc/passwd) [c](file:///tmp/x) [d](#top) [e](HTTPS://example.com/e) [f](http://example.com/f) https://example.com/g"
        filters = [a for a in c.PANDOC_PDF if a.endswith(".lua") and "links" in a]
        out = subprocess.run(["pandoc", "-f", "markdown+autolink_bare_uris", "-t", "latex", "--lua-filter", filters[0]],
                             input=md, capture_output=True, text=True).stdout
        self.assertEqual(sorted(re.findall(r"\\(?:href|url)\{([^}]*)\}", out)),
                         ["HTTPS://example.com/e", "http://example.com/f", "https://example.com/g"])
        for text in ("a", "b", "c", "d"):
            self.assertRegex(out, rf"(^|\s){text}(\s|$)")


class FontTests(unittest.TestCase):
    def test_pick_fonts_returns_a_sans_and_mono_from_the_lists(self):
        args = dict(a.split("=", 1) for a in c.pick_fonts() if "=" in a)
        self.assertIn(args["mainfont"], c.SANS + [c.FALLBACK[0]])
        self.assertIn(args["monofont"], c.MONO + [c.FALLBACK[1]])


@unittest.skipUnless(shutil.which("pandoc") and shutil.which("xelatex"), "needs pandoc and xelatex")
class CliTests(unittest.TestCase):
    def run_cli(self, cwd, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--file", str(SAMPLE), *args],
                              cwd=cwd, capture_output=True, text=True)

    def test_writes_pdf_and_md_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(d, "my", "chat.pdf")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(d) / "my chat.pdf").read_bytes().startswith(b"%PDF"))
            self.assertTrue((Path(d) / "my chat.md").exists())
            before = (Path(d) / "my chat.md").read_text()
            r = self.run_cli(d, "my chat")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("already exist", r.stderr)
            self.assertEqual((Path(d) / "my chat.md").read_text(), before)

    def test_long_lines_stay_inside_margins(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "long.jsonl"
            long = "x" * 400
            body = f"`{'/a-b' * 60}`\n\n```\n{long}\n```\n\nhttps://example.com/{long}"
            src.write_text('{"type":"user","message":{"content":%s}}\n' % json.dumps(body))
            r = subprocess.run([sys.executable, str(SCRIPT), "--file", str(src), str(Path(d) / "o")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            if shutil.which("pdftotext"):
                bbox = subprocess.run(["pdftotext", "-bbox", str(Path(d) / "o.pdf"), "-"], capture_output=True, text=True).stdout
                xmax = max(float(m) for m in re.findall(r'xMax="([\d.]+)"', bbox))
                self.assertLess(xmax, 595.3 - 72 + 1)  # A4 width minus 1in margin

    def test_page_size_option(self):
        if not shutil.which("pdfinfo"): self.skipTest("needs pdfinfo")
        for args, size in (((), "595"), (("--page-size", "a4"), "595"), (("--page-size", "Letter"), "612")):
            with tempfile.TemporaryDirectory() as d:
                r = self.run_cli(d, "o", *args)
                self.assertEqual(r.returncode, 0, r.stderr)
                info = subprocess.run(["pdfinfo", str(Path(d) / "o.pdf")], capture_output=True, text=True).stdout
                self.assertRegex(info, rf"Page size:\s+{size}")
        r = self.run_cli(tempfile.gettempdir(), "x", "--page-size", "legal")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
