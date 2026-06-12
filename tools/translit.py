#!/usr/bin/env python3
"""Транслитерация имён PDF: кириллица -> латиница, пригодная для URL.

Использование (из папки tools/):
    uv run python translit.py [папка]            # dry-run: показать план
    uv run python translit.py [папка] --apply    # переименовать

'2014_Кориков_TeX.pdf' -> '2014-korikov-tex.pdf'
"""

import sys
from pathlib import Path

from models import slugify


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv
    folder = Path(args[0]) if args else Path(".")

    files = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".pdf")
    if not files:
        sys.exit(f"No PDF files in {folder.resolve()}")

    plan, targets = [], set()
    for p in files:
        new_name = slugify(p.stem) + p.suffix.lower()
        if new_name == p.name:
            continue
        if new_name in targets or (folder / new_name).exists():
            sys.exit(f"Name collision: {p.name} -> {new_name} (already taken)")
        targets.add(new_name)
        plan.append((p, new_name))

    if not plan:
        print("All names are already fine.")
        return

    width = max(len(p.name) for p, _ in plan)
    for p, new_name in plan:
        print(f"{p.name:<{width}}  ->  {new_name}")

    if apply:
        for p, new_name in plan:
            p.rename(p.with_name(new_name))
        print(f"\nRenamed: {len(plan)}")
    else:
        print("\nDry-run, files untouched. To rename, add --apply")


if __name__ == "__main__":
    main()
