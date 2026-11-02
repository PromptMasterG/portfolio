#!/usr/bin/env python3
"""Link checker for the built site.

Internal links, images, scripts, styles and in-page anchors must resolve: any miss is an error.
External links are checked with retries; sites that block bots can be skipped.

    python3 .github/scripts/links.py --site _site --base /portfolio [--external] [--skip linkedin.com]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlparse

UA = "Mozilla/5.0 (compatible; portfolio-link-check/1.0)"


class Refs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href") is not None:
            self.refs.append(("a", a["href"]))
        elif tag in ("img", "script") and a.get("src"):
            self.refs.append((tag, a["src"]))
        elif tag == "link" and a.get("href") and a.get("rel") in ("stylesheet", "icon"):
            self.refs.append(("link", a["href"]))


def target_file(site: Path, base: str, url_path: str):
    path = unquote(url_path)
    if not path.startswith(base + "/") and path != base:
        return None
    rel = path[len(base):].lstrip("/")
    candidate = site / rel
    if candidate.is_dir() or path.endswith("/") or rel == "":
        candidate = candidate / "index.html"
    return candidate


def check_external(url: str, retries: int = 3, timeout: int = 20):
    last = "no response"
    for attempt in range(retries):
        for method in ("HEAD", "GET"):
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status < 400:
                        return None
                    last = f"HTTP {resp.status}"
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code == 429:
                    return None  # rate limited: the page exists
                if e.code in (404, 410) and method == "GET":
                    break
            except Exception as e:  # network trouble: retry
                last = type(e).__name__ + ": " + str(e)[:80]
        time.sleep(2 * (attempt + 1))
    return last


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="_site")
    ap.add_argument("--base", default="/portfolio")
    ap.add_argument("--external", action="store_true", help="also check external links")
    ap.add_argument("--skip", action="append", default=[], help="host to skip (sites that block bots)")
    args = ap.parse_args(argv)
    site = Path(args.site).resolve()
    base = args.base.rstrip("/")
    pages = {}
    for path in sorted(site.rglob("*.html")):
        parser = Refs()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path] = parser
    errors: list[str] = []
    external: dict[str, str] = {}
    for path, parser in pages.items():
        here = "/" + path.relative_to(site).as_posix()
        here_url = base + (here[: -len("index.html")] if here.endswith("index.html") else here)
        for tag, ref in parser.refs:
            if re.match(r"(mailto|tel|data|javascript):", ref):
                continue
            absolute = urljoin("http://site" + here_url, ref)
            parsed = urlparse(absolute)
            if parsed.netloc != "site":
                if tag == "a" and parsed.scheme in ("http", "https"):
                    external.setdefault(urldefrag(absolute)[0], path.relative_to(site).as_posix())
                continue
            file = target_file(site, base, parsed.path)
            where = path.relative_to(site).as_posix()
            if file is None or not file.exists():
                errors.append(f"{where}: broken internal link {ref}")
                continue
            if parsed.fragment and file.suffix == ".html":
                ids = pages[file].ids if file in pages else set()
                if parsed.fragment not in ids:
                    errors.append(f"{where}: anchor #{parsed.fragment} not found in {file.relative_to(site).as_posix()}")
    internal_count = sum(len(p.refs) for p in pages.values())
    print(f"Checked {internal_count} references on {len(pages)} pages.")
    if args.external:
        for url, source in sorted(external.items()):
            host = urlparse(url).netloc
            if any(host.endswith(s) for s in args.skip):
                print(f"skipped (blocks bots): {url}")
                continue
            problem = check_external(url)
            print(("ok       " if problem is None else "FAILED   ") + url)
            if problem:
                errors.append(f"{source}: external link failed ({problem}): {url}")
    for e in errors:
        print(e)
    print(("\n%d link problem(s)." % len(errors)) if errors else "Links passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
