"""Prevent non-English project text and stale document exports on this branch."""

from pathlib import Path
import re
import subprocess
import unittest
from zipfile import ZipFile
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u4e00-\u9fff]")
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".html",
    ".svg",
    ".dot",
    ".css",
    ".toml",
    ".json",
}


class RepositoryLanguageTests(unittest.TestCase):
    def test_project_text_is_english(self):
        paths = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        failures = []
        for name in paths:
            p = ROOT / name
            if not p.is_file():
                continue
            if p.suffix in TEXT_SUFFIXES or p.name == ".gitignore":
                if CJK.search(p.read_text()):
                    failures.append(name)
        self.assertEqual(failures, [], "Unexpected Chinese text in project files")

    def test_english_prd_exports(self):
        directory = ROOT / "docs/prd/exports"
        pdf = PdfReader(directory / "CariAgent_PRD_en_v0.4.pdf")
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn("Product Requirements", text)
        self.assertFalse(CJK.search(text))
        with ZipFile(directory / "CariAgent_PRD_en_v0.4.docx") as document:
            self.assertIsNone(document.testzip())
            text = document.read("word/document.xml").decode()
            self.assertFalse(CJK.search(text))
            self.assertEqual(
                len(
                    [
                        name
                        for name in document.namelist()
                        if name.startswith("word/media/")
                    ]
                ),
                2,
            )
        self.assertFalse(list(directory.glob("*_zh_*")))


if __name__ == "__main__":
    unittest.main()
