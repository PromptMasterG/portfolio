#!/usr/bin/env python3
"""Structure, traceability and security checks for the portfolio.

    python3 .github/scripts/site_checks.py --source          checks on the repository files
    python3 .github/scripts/site_checks.py --site _site      checks on the built site

Generic by design: it carries no private names. Needs PyYAML for the source checks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

JS_BUDGET_BYTES = 6144
CASE_WORDS = (450, 800)
SITE_URL = "https://promptmasterg.github.io"
MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
# Numbers that are names or versions, not measurements.
NAMED_NUMBERS = [r"[Vv][Ee][Oo] 3", r"Tauri 2", r"React 19", r"Gemma 4", r"M2 Biosciences", r"\b3D\b", r"UTC\+2", r"BM25",
                 r"\bM2\b", r"\bv\d+(?:\.\d+)*\b"]
SKIP_PAGES = {"README.md"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def yaml_load(text: str):
    import yaml
    return yaml.safe_load(text)


def split_front(text: str):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return yaml_load(text[4:end]) or {}, text[text.find("\n", end + 1):] if text.find("\n", end + 1) != -1 else ""
    return {}, text


def pages(root: Path):
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel in SKIP_PAGES or rel.startswith(("profile-readme/", ".github/", "vendor/", "node_modules/", "_site/")):
            continue
        yield rel, path


# ---------------------------------------------------------------- source checks

def check_source(root: Path) -> list[str]:
    errors: list[str] = []
    data = root / "_data"
    facts = yaml_load(read(data / "facts.yml"))
    projects = yaml_load(read(data / "projects.yml"))
    skills = yaml_load(read(data / "skills.yml"))

    # images.yml mirrors the supplied manifest exactly
    manifest = json.loads(read(root / "assets-manifest.json"))
    images = yaml_load(read(data / "images.yml"))
    keys = ("file", "project", "width", "height", "alt", "caption")
    if [{k: e[k] for k in keys} for e in manifest] != [{k: e[k] for k in keys} for e in images]:
        errors.append("_data/images.yml differs from assets-manifest.json")

    # facts: shape
    seen_keys = re.findall(r"^([a-z0-9-]+):\s*$", read(data / "facts.yml"), re.M)
    if len(seen_keys) != len(set(seen_keys)):
        errors.append("facts.yml has a duplicate id")
    for fid, f in facts.items():
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fid):
            errors.append(f"fact {fid}: id must be lower-case kebab-case")
        for key in ("label", "value", "as_of", "claim", "status"):
            if not f.get(key):
                errors.append(f"fact {fid}: missing {key}")
        if not re.fullmatch(r"(?:C|CV)\d{2}", str(f.get("claim", ""))):
            errors.append(f"fact {fid}: claim must look like C00 or CV00")
        if f.get("status") not in ("S", "Q"):
            errors.append(f"fact {fid}: status must be S or Q")
        if f.get("status") == "Q" and not f.get("qualifier"):
            errors.append(f"fact {fid}: a qualified claim needs its qualifier")
        if f.get("as_of") and str(f["as_of"]) > "2026-11-01":
            errors.append(f"fact {fid}: as_of is in the future")
        for sid in f.get("sum_of", []):
            if sid not in facts:
                errors.append(f"fact {fid}: sum_of names unknown fact {sid}")

    # projects and skills reference real facts and images
    image_files = {e["file"] for e in manifest}
    for p in projects:
        if p.get("proof_fact") and p["proof_fact"] not in facts:
            errors.append(f"project {p['id']}: unknown proof_fact")
        if p.get("image") and p["image"] not in image_files:
            errors.append(f"project {p['id']}: image not in manifest")
    for row in skills:
        for fid in row.get("facts", []):
            if fid not in facts:
                errors.append(f"skill {row['id']}: unknown fact {fid}")

    # pages
    titles, descriptions = {}, {}
    all_text = " ".join(" ".join(str(f.get(k, "")) for k in ("value", "short", "label", "detail", "basis", "strip_label"))
                        for f in facts.values())
    for rel, path in pages(root):
        text = read(path)
        front, body = split_front(text)
        for key in ("layout", "title", "description"):
            if not front.get(key):
                errors.append(f"{rel}: front matter needs {key}")
        for key, bag in (("title", titles), ("description", descriptions)):
            v = front.get(key)
            if v:
                if v in bag:
                    errors.append(f"{rel}: duplicate {key} (also {bag[v]})")
                bag[v] = rel
        d = str(front.get("description", ""))
        if d and not 50 <= len(d) <= 160:
            errors.append(f"{rel}: description is {len(d)} characters, want 50 to 160")
        for key in ("title", "description", "dek", "eyebrow", "role", "period", "stack"):
            if isinstance(front.get(key), str):
                errors += number_trace(f"{rel} (front matter {key})", front[key])
        listed = set(front.get("facts") or [])
        for fid in listed:
            if fid not in facts:
                errors.append(f"{rel}: front matter lists unknown fact {fid}")
        used = set(re.findall(r"include (?:fact|evidence)\.html id=\"([a-z0-9-]+)\"", body))
        for list_name in re.findall(r"assign \w+ = \"([a-z0-9,-]+)\" \| split", body):
            used |= set(list_name.split(","))
        for key in ("scale", "key_facts", "ledger"):
            used |= set(front.get(key) or [])
        for item in front.get("proof") or []:
            used.add(item["fact"])
        if front.get("layout") == "case-study":
            proj = next((p for p in projects if p["id"] == front.get("project")), {})
            if not front.get("screens"):
                used |= set(proj.get("visual_facts", []))
        if front.get("layout") == "home":
            used |= {f for p in projects if p.get("featured") and p.get("visual") for f in p.get("visual_facts", [])}
        if front.get("layout") == "home":
            used |= {p["proof_fact"] for p in projects if p.get("featured") and p.get("proof_fact")}
        for m in re.finditer(r"fit-list\.html role=\"(\w+)\"", body):
            role = {"engineer": "engineer", "creator": "creator"}[m.group(1)]
            for row in skills:
                if role in row["roles"]:
                    used |= set(row.get("facts", []))
        for fid in sorted(used - listed):
            errors.append(f"{rel}: figure {fid} is used but not listed in the page's facts")
        for fid in sorted(used):
            if fid not in facts:
                errors.append(f"{rel}: unknown fact {fid}")
        errors += number_trace(rel, body)
        for m in re.finditer(r"\]\((https?://[^)\s]+)\)(\{:[^}]*\})?", body):
            if not m.group(2) or "noopener noreferrer" not in m.group(2):
                errors.append(f"{rel}: external link without rel noopener noreferrer: {m.group(1)}")
        if re.search(r"<[^>]+\sstyle=|<[^>]+\son\w+=|<iframe|<embed|<object", body, re.I):
            errors.append(f"{rel}: inline style, event handler or embed in Markdown")

    # free text in data files may not carry figures either; only facts.yml may
    for name, keys in (("projects.yml", ("what", "proof_text", "status", "area", "title")),
                       ("skills.yml", ("requirement", "proof")),
                       ("profile.yml", ("name", "headline", "positioning", "availability", "location"))):
        data_obj = yaml_load(read(data / name))
        rows = data_obj if isinstance(data_obj, list) else [data_obj]
        for row in rows:
            for key in keys:
                if isinstance(row.get(key), str):
                    errors += number_trace(f"_data/{name} ({key})", row[key])

    # layouts and includes: no inline style, handlers or third-party loads
    for folder in ("_layouts", "_includes"):
        for path in sorted((root / folder).glob("*.html")):
            t = read(path)
            if re.search(r"\sstyle=\"|\son[a-z]+=\"|<iframe|<embed|<object", t):
                errors.append(f"{folder}/{path.name}: inline style, event handler or embed")
            for m in re.finditer(r"(?:src|href|action)=\"((?:https?:)?//[^\"]+)\"", t):
                if not ("{{" in m.group(1) or path.name in ("head.html",) and "schema.org" in m.group(1)):
                    errors.append(f"{folder}/{path.name}: absolute external URL in markup: {m.group(1)}")
    css = read(root / "assets/css/site.css")
    if re.search(r"@import|url\(\s*[\"']?(?:https?:)?//", css):
        errors.append("site.css loads something from outside the site")
    js_size = len((root / "assets/js/site.js").read_bytes())
    if js_size > JS_BUDGET_BYTES:
        errors.append(f"site.js is {js_size} bytes, budget is {JS_BUDGET_BYTES}")

    # profile README: every number must be a figure that exists in the facts file
    readme = root / "profile-readme" / "README.md"
    if readme.exists():
        text = read(readme)
        if len(text.splitlines()) >= 60:
            errors.append("profile-readme/README.md must be under 60 lines")
        for pat, why in ((r"img\.shields\.io|github-readme-stats|streak|visitor|komarev|skillicons", "banned widget"),
                         (r"```", "code fence")):
            if re.search(pat, text, re.I):
                errors.append(f"profile-readme/README.md: {why}")
        stripped = re.sub(r"https?://\S+|\]\([^)]*\)|\b(?:alt|width|height)=\"[^\"]*\"", " ", text)
        stripped = re.sub(rf"\b\d{{1,2}} (?:{MONTHS}) \d{{4}}|\b(?:{MONTHS}) \d{{4}}|\b20\d\d\b", " ", stripped)
        for pattern in NAMED_NUMBERS:
            stripped = re.sub(pattern, " ", stripped)
        for token in re.findall(r"\d[\d,.]*\+?[KkMm%]?", stripped):
            if token.strip(".,") and token.strip(".,") not in all_text:
                errors.append(f"profile-readme/README.md: number {token!r} is not in the facts file")
    return errors


def number_trace(rel: str, body: str) -> list[str]:
    text = re.sub(r"```mermaid.*?```", " ", body, flags=re.S)
    text = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"\]\([^)]*\)", "] ", text)
    text = re.sub(r"https?://\S+|\{[:#][^}]*\}", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^#{1,6}\s+\d+\.\s", "### ", text, flags=re.M)
    text = re.sub(rf"\b\d{{1,2}} (?:{MONTHS}) \d{{4}}|\b\d{{1,2}} (?:{MONTHS})\b|\b(?:{MONTHS}) \d{{4}}|\b(?:19|20)\d\d\b", " ", text)
    for pattern in NAMED_NUMBERS:
        text = re.sub(pattern, " ", text)
    out = []
    for lineno, line in enumerate(text.split("\n"), 1):
        for token in re.findall(r"\d[\d,.]*\+?[KkMm%]?", line):
            out.append(f"{rel}: number {token!r} in prose is not rendered from the facts file (near: {line.strip()[:60]!r})")
    return out


# ---------------------------------------------------------------- built-site checks

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings: list[int] = []
        self.title = ""
        self.in_title = False
        self.meta: dict[str, str] = {}
        self.links: list[dict] = []
        self.imgs: list[dict] = []
        self.loads: list[tuple[str, str]] = []
        self.violations: list[str] = []
        self.ld: list[str] = []
        self.in_ld = False
        self.lang = ""
        self.canonical = ""
        self.csp = ""
        self.pending_pre = False
        self.text_stack: list[str] = []
        self.words = 0
        self.count_depth = 0
        self.skip_depth = 0
        self.prose_depth = 0

    SKIP = {"table", "pre", "figure", "script", "style", "svg"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def handle_comment(self, data):
        self.violations.append("HTML comment")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        diagram = tag == "code" and "language-mermaid" in a.get("class", "").split()
        if self.pending_pre:
            self.pending_pre = False
            if not diagram:
                self.violations.append("<pre> that is not the diagram fallback")
        if tag == "pre":
            self.pending_pre = True
        elif tag in ("code", "kbd", "samp", "style", "svg") and not diagram:
            self.violations.append(f"<{tag}> element")
        if tag == "html":
            self.lang = a.get("lang", "")
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = a.get("name") or a.get("property") or a.get("http-equiv")
            if key:
                self.meta[key] = a.get("content", "")
            if a.get("http-equiv", "").lower() == "content-security-policy":
                self.csp = a.get("content", "")
        if tag == "link":
            if a.get("rel") == "canonical":
                self.canonical = a.get("href", "")
            if a.get("href"):
                self.loads.append((tag, a["href"]))
        if tag == "script":
            if a.get("type") == "application/ld+json":
                self.in_ld = True
            elif a.get("src"):
                self.loads.append((tag, a["src"]))
            else:
                self.violations.append("inline script")
        if tag == "a" and a.get("href"):
            self.links.append(a)
        if tag == "img":
            self.imgs.append(a)
            self.loads.append((tag, a.get("src", "")))
        if tag in ("iframe", "embed", "object", "video", "audio", "source", "form"):
            self.violations.append(f"<{tag}> element")
        if "style" in a:
            self.violations.append("inline style attribute")
        if any(k.startswith("on") for k in a):
            self.violations.append("inline event handler")
        if tag in self.VOID:
            return
        if tag in self.SKIP or a.get("class", "").split()[:1] in (["figcap"], ["case-side"], ["figures-note"], ["evidence-row"], ["evidence"], ["access"], ["team"], ["keyfigs"], ["keyfigs-note"]):
            self.skip_depth += 1
            self.text_stack.append(tag)
        else:
            self.text_stack.append("")
        if "prose" in a.get("class", "").split():
            self.prose_depth += 1
            self.text_stack[-1] = self.text_stack[-1] or "prose"

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return  # a self-closing void tag such as <img /> reaches here without ever being pushed
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_ld = False
        if self.text_stack:
            top = self.text_stack.pop()
            if top == "prose":
                self.prose_depth -= 1
            elif top:
                self.skip_depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_ld:
            self.ld.append(data)
        if self.prose_depth and not self.skip_depth:
            self.words += len(re.findall(r"[A-Za-z0-9][\w'’.,%+/-]*", data))


def check_site(site: Path) -> list[str]:
    errors: list[str] = []
    html_files = sorted(p for p in site.rglob("*.html"))
    titles, descriptions = {}, {}
    urls = set()
    for path in html_files:
        rel = path.relative_to(site).as_posix()
        page = Page()
        page.feed(read(path))
        is_404 = rel == "404.html"
        if page.headings.count(1) != 1:
            errors.append(f"{rel}: expected one h1, found {page.headings.count(1)}")
        for before, after in zip(page.headings, page.headings[1:]):
            if after - before > 1:
                errors.append(f"{rel}: heading level jumps from h{before} to h{after}")
        if not page.lang:
            errors.append(f"{rel}: missing lang")
        t, d = page.title.strip(), page.meta.get("description", "")
        for what, value, bag in (("title", t, titles), ("description", d, descriptions)):
            if not value:
                errors.append(f"{rel}: missing {what}")
            elif value in bag:
                errors.append(f"{rel}: duplicate {what} (also {bag[value]})")
            else:
                bag[value] = rel
        if not page.canonical.startswith(SITE_URL + "/"):
            errors.append(f"{rel}: canonical must be an absolute URL on the site")
        urls.add(page.canonical)
        for key in ("og:title", "og:description", "og:image", "og:url", "twitter:card", "twitter:image"):
            if not page.meta.get(key):
                errors.append(f"{rel}: missing {key}")
        if not page.meta.get("og:image", "").startswith(SITE_URL):
            errors.append(f"{rel}: og:image must be absolute")
        robots = page.meta.get("robots", "")
        if "noai" not in robots or "noimageai" not in robots:
            errors.append(f"{rel}: robots meta needs noai and noimageai")
        for directive in ("default-src 'none'", "script-src 'self'", "base-uri 'self'"):
            if directive not in page.csp:
                errors.append(f"{rel}: CSP lacks {directive}")
        if "unsafe-inline" in page.csp or "unsafe-eval" in page.csp:
            errors.append(f"{rel}: CSP must not allow unsafe-inline or unsafe-eval")
        for v in sorted(set(page.violations)):
            errors.append(f"{rel}: {v}")
        for tag, ref in page.loads:
            if re.match(r"(?:https?:)?//", ref) and not ref.startswith(SITE_URL):
                errors.append(f"{rel}: <{tag}> loads a third-party resource: {ref}")
        for a in page.links:
            href = a["href"]
            if re.match(r"https?://", href) and not href.startswith(SITE_URL):
                rels = a.get("rel", "").split()
                if "noopener" not in rels or "noreferrer" not in rels:
                    errors.append(f"{rel}: external link without rel noopener noreferrer: {href}")
            if href.startswith("tel:"):
                errors.append(f"{rel}: tel link")
        for i, img in enumerate(page.imgs):
            if not (img.get("width") and img.get("height")):
                errors.append(f"{rel}: image without width and height: {img.get('src')}")
            if not img.get("alt"):
                errors.append(f"{rel}: image without alt text: {img.get('src')}")
        if sum(1 for img in page.imgs if img.get("loading") != "lazy") > 1:
            errors.append(f"{rel}: more than one image is not lazy-loaded")
        for block in page.ld:
            try:
                ld = json.loads(block)
            except ValueError:
                errors.append(f"{rel}: JSON-LD is not valid JSON")
                continue
            if ld.get("@type") != "Person":
                errors.append(f"{rel}: JSON-LD should describe a Person")
            if "telephone" in ld or set(ld.get("address", {})) - {"@type", "addressLocality", "addressCountry"}:
                errors.append(f"{rel}: JSON-LD carries a phone or a detailed address")
            if "email" in ld:
                errors.append(f"{rel}: JSON-LD carries an email address")
        if re.fullmatch(r"work/(?!writing)[a-z-]+/index\.html", rel):
            lo, hi = CASE_WORDS
            if not lo <= page.words <= hi:
                errors.append(f"{rel}: case study is {page.words} words, want {lo} to {hi} (ledger, figures and diagrams excluded)")
            for needle in ("What went wrong", "Verification and results", "Skills this demonstrates", "What I would do next",
                           "The source is private. I am happy to walk through it live."):
                if needle not in read(path):
                    errors.append(f"{rel}: missing section or line: {needle}")
        if rel == "index.html":
            for needle in ("See the work", "Email me"):
                if needle not in read(path):
                    errors.append(f"{rel}: missing {needle!r}")
        if rel == "about/index.html":
            if not 300 <= page.words <= 400:
                errors.append(f"{rel}: about page is {page.words} words, want 300 to 400")
    for name in ("sitemap.xml", "robots.txt"):
        if not (site / name).exists():
            errors.append(f"{name} is missing from the built site")
    js = site / "assets/js/site.js"
    if js.exists() and len(js.read_bytes()) > JS_BUDGET_BYTES:
        errors.append("built site.js is over budget")
    if (site / "sitemap.xml").exists():
        sitemap = read(site / "sitemap.xml")
        for url in sorted(u for u in urls if not u.endswith("404.html")):
            if url not in sitemap:
                errors.append(f"sitemap.xml does not list {url}")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--source", action="store_true", help="check the repository files")
    parser.add_argument("--site", help="check a built site directory")
    args = parser.parse_args(argv)
    errors: list[str] = []
    if args.source:
        errors += check_source(Path(args.root))
    if args.site:
        errors += check_site(Path(args.site))
    if not (args.source or args.site):
        parser.error("choose --source, --site or both")
    for e in errors:
        print(e)
    print(("\n%d problem(s) found." % len(errors)) if errors else "Site checks passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
