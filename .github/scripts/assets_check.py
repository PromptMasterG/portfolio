#!/usr/bin/env python3
"""Guard for the screenshots and their manifest.

Every manifest entry and image that is present must match the base branch byte for byte. An image may be
removed, but only together with its manifest entry. An image may be added only together with its manifest
entry, and only if its bytes match a file named by `--supplied ref:folder`. Without `--supplied`, no image may
be added, so a new screenshot needs the owner's review and a deliberate change to this check.

    python3 .github/scripts/assets_check.py --base origin/main
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

MANIFEST = "assets-manifest.json"


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def supplied_hashes(root: Path, supplied: str | None) -> set[str] | None:
    """Blob ids of every file in `ref:folder`, or None when no supplied source was given or it cannot be read."""
    if not supplied or ":" not in supplied:
        return None
    ref, folder = supplied.split(":", 1)
    listed = git(root, "ls-tree", "-r", ref, "--", folder)
    if listed.returncode != 0:
        return None
    return {line.split()[2] for line in listed.stdout.decode("utf-8").splitlines() if line.strip()}


def check(root: Path, base: str, supplied: str | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    removed: list[str] = []
    allowed = supplied_hashes(root, supplied)
    shown = git(root, "show", f"{base}:{MANIFEST}")
    if shown.returncode != 0:
        return [f"cannot read {MANIFEST} from {base}"], removed
    before = {e["file"]: e for e in json.loads(shown.stdout.decode("utf-8"))}
    current_path = root / MANIFEST
    now = {e["file"]: e for e in json.loads(current_path.read_text(encoding="utf-8"))} if current_path.exists() else {}
    for name, entry in now.items():
        if name not in before:
            path = root / name
            if allowed is None:
                errors.append(f"{name}: new image or manifest entry, which is not allowed")
            elif not path.exists():
                errors.append(f"{name}: new manifest entry without an image")
            elif git(root, "hash-object", str(path)).stdout.decode().strip() not in allowed:
                errors.append(f"{name}: new image that does not match any supplied file")
        elif entry != before[name]:
            errors.append(f"{name}: manifest entry differs from {base}")
    for name in before:
        path = root / name
        if name in now:
            if not path.exists():
                errors.append(f"{name}: listed in the manifest but missing")
                continue
            was = git(root, "rev-parse", f"{base}:{name}").stdout.decode().strip()
            is_now = git(root, "hash-object", str(path)).stdout.decode().strip()
            if was != is_now:
                errors.append(f"{name}: image differs from {base}")
        else:
            if path.exists():
                errors.append(f"{name}: dropped from the manifest but the file is still there")
            else:
                removed.append(name)
    return errors, removed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--supplied", default=None, help="ref:folder holding images the owner supplied")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args(argv)
    errors, removed = check(Path(args.root), args.base, args.supplied)
    for name in removed:
        print("removed together with its manifest entry: " + name)
    for error in errors:
        print(error)
    print(("\n%d problem(s) with the supplied assets." % len(errors)) if errors else "Supplied assets match the base branch, apart from the removals above.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
