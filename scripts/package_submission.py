"""Build the submission zip in the folder structure the brief asks for.

    python scripts/package_submission.py PP01

Produces dist/PP01.zip containing:
    docs/PP01.docx
    source/readme.txt, source/requirements.txt, source/src/...
Excludes .git, venv, __pycache__, db.sqlite3 and media uploads.
"""
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".git", "venv", ".venv", "__pycache__", "media"}
EXCLUDE_FILES = {"db.sqlite3"}


def main(group: str):
    report = ROOT / "docs" / f"{group}.docx"
    if not report.exists():
        sys.exit(f"Missing {report.relative_to(ROOT)}; put the final report there first.")
    out = ROOT / "dist" / f"{group}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(report, f"docs/{report.name}")
        for p in (ROOT / "source").rglob("*"):
            rel = p.relative_to(ROOT)
            if p.is_dir() or EXCLUDE_DIRS & set(rel.parts) or p.name in EXCLUDE_FILES:
                continue
            z.write(p, rel.as_posix())
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "PPXX")
