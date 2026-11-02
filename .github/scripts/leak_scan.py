#!/usr/bin/env python3
"""Leak scan for the portfolio repository.

Fails when the tree (or the built site) contains anything that could copy, clone or identify
private work: code, odd file types, unlisted images, paths, addresses, secrets, phone numbers,
identifier-like tokens in prose, banned phrases and voice slips.

The script is generic. It carries no private names; those are checked by a local run that is
never committed. Usage:

    python3 .github/scripts/leak_scan.py                 scan the source tree
    python3 .github/scripts/leak_scan.py --site _site    scan the built site
    git log --format=%B base..HEAD | python3 .github/scripts/leak_scan.py --stdin messages
    git log -p --format= base..HEAD | python3 .github/scripts/leak_scan.py --stdin diff
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import unicodedata
from collections import namedtuple
from html.parser import HTMLParser
from pathlib import Path

Finding = namedtuple("Finding", "path line rule message")

ALWAYS_ALLOWED_EMAILS = {"noreply@anthropic.com"}
ALLOWED_EMAIL_SUFFIXES = ("@users.noreply.github.com",)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif", ".bmp", ".tif",
                  ".tiff", ".heic"}
SOURCE_SUFFIXES = {".md", ".yml", ".yaml", ".html", ".css", ".js", ".txt", ".png"}
SITE_SUFFIXES = {".html", ".css", ".js", ".txt", ".xml", ".png", ".json"}
ALLOWED_NAMES = {"LICENSE", "Gemfile", ".gitignore"}
ALLOWED_ROOT_JSON = {"assets-manifest.json"}
SCRIPTS_DIR = ".github/scripts"
SCRIPT_SUFFIXES = {".py", ".js", ".md"}
MANIFEST = "assets-manifest.json"

# Public brand and technology names that legitimately contain a hump or a dot.
NAME_ALLOW = {
    "YouTube", "LinkedIn", "GitHub", "TypeScript", "JavaScript", "ChromaDB", "ElevenLabs", "CapCut",
    "FastAPI", "PromptMasterG", "TikTok", "MeowTok", "MBChB", "LoRA", "llama.cpp", "whisper.cpp",
}
CODE_EXTENSIONS = (
    "py|rs|ts|tsx|jsx|js|mjs|cjs|db|sqlite|sqlite3|gguf|env|bat|ps1|vbs|sh|toml|json|yaml|yml|sql|ini|cfg|"
    "conf|log|csv|exe|dll|bin|md|cpp|java|go|rb|php|lock|pdf|docx|xlsx"
)

BANNED_PATTERNS = [
    r"passionate", r"leverag(?:e|es|ed|ing)", r"cutting[\s-]?edge", r"state[\s-]?of[\s-]?the[\s-]?art",
    r"game[\s-]?changers?", r"game[\s-]?changing", r"seamless(?:ly)?", r"robust(?:ness)?", r"synerg(?:y|ies)",
    r"unlock(?:s|ed|ing)?", r"empower(?:s|ed|ing|ment)?", r"revolutionis(?:e|es|ed|ing)",
    r"revolutioniz(?:e|es|ed|ing)", r"delv(?:e|es|ed|ing)", r"tapestry", r"landscapes?", r"journeys?",
    r"in today's fast[\s-]?paced world", r"at the end of the day", r"it's not just", r"not only\b.{0,80}?\bbut also",
    r"i'm excited to", r"i am thrilled", r"best[\s-]?in[\s-]?class", r"world[\s-]?class", r"next[\s-]?level",
    r"dive into", r"deep dive", r"ever[\s-]?evolving", r"harness the power", r"elevat(?:e|es|ed|ing)",
    r"supercharg(?:e|es|ed|ing)", r"turbocharg(?:e|es|ed|ing)", r"ninjas?", r"rock[\s-]?stars?", r"gurus?", r"wizards?",
]
VOICE_PATTERNS = [
    (r"\b(?:very|really|extremely|incredibly|truly|absolutely|literally|totally)\b", "padding intensifier"),
    (r"\b(?:love|loved|loves|passion|passions|excited|thrilled|proud|enthusiastic|enthusiasm)\b",
     "feeling about the work"),
    (r"\b(?:it's not|it is not|isn't just|not just|not merely|more than just)\b", "not-X-but-Y construction"),
]
BANNED_RE = re.compile(r"\b(?:" + "|".join(BANNED_PATTERNS) + r")\b", re.I)
VOICE_RES = [(re.compile(p, re.I), why) for p, why in VOICE_PATTERNS]

URL_RE = re.compile(r"(?:https?|mailto|tel):[^\s<>\"')\]]+|www\.[^\s<>\"')\]]+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
LIQUID_RE = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.S)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HTML_TAG_RE = re.compile(r"<[^>]+>")
TOKEN_RE = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_])?")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
MERMAID_LINE_RE = re.compile(
    r"^\s*(?:flowchart TD|graph TD|[A-Za-z][A-Za-z0-9]*(?:\[[A-Za-z0-9 ,.'&/-]+\])?"
    r"(?:\s*-->(?:\|[A-Za-z0-9 ,.'-]+\|)?\s*[A-Za-z][A-Za-z0-9]*(?:\[[A-Za-z0-9 ,.'&/-]+\])?)*)?\s*$")
CLI_FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9]+(?:-[a-z0-9]+)*")
SETTING_RE = re.compile(r"\b(?:temperature|top[\s-]?[pk]|min[\s-]?p|ctx[\s-]?size|gpu[\s-]?layers|n[\s-]?predict|"
                        r"batch[\s-]?size|context[\s-]?length)\s*[=:]?\s*\d", re.I)
CREDENTIAL_RES = [
    re.compile(r"(?<![\w-])(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{10,}"),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
]

ABS_PATH_RES = [
    re.compile(r"\b[A-Za-z]:\\"),
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])"),
    re.compile(r"\\\\[\w.-]+\\"),
    re.compile(r"\bfile://", re.I),
    re.compile(r"\$HOME\b|\$USERPROFILE\b|%HOME%"),
    re.compile(r"\\Users\\", re.I),
    re.compile(r"(?<![\w:/.\-])/(?:home|Users|root|etc|var|tmp|usr|opt|mnt|srv|proc|bin|dev)/\w"),
    re.compile(r"(?<![\w])~/\w"),
    re.compile(r"%(?:APPDATA|USERPROFILE|LOCALAPPDATA)%", re.I),
]
LOCAL_RES = [
    re.compile(r"\blocalhost\b", re.I),
    re.compile(r"\b127\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b0\.0\.0\.0\b"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\bports?\s+\d{3,5}\b", re.I),
    re.compile(r"\bport\s*[=:]\s*\d{2,5}\b", re.I),
    re.compile(r"(?<![\w:])::1(?![\w:])"),
    re.compile(r"[A-Za-z0-9\]]:\d{4,5}\b"),
]
SECRET_PREFIX_RES = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\b[A-Z][A-Z0-9_]{4,}_(?:KEY|TOKEN|SECRET|PASSWORD)\s*[=:]"),
]
HEX_RE = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,}(?![0-9A-Za-z])")
BASE64_RE = re.compile(r"(?<![A-Za-z0-9+/=_\-])(?=[A-Za-z0-9+/]*\d)(?=[A-Za-z0-9+/]*[a-z])(?=[A-Za-z0-9+/]*[A-Z])"
                       r"[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9+/=_\-])")
PINNED_ACTION_RE = re.compile(r"uses:\s*\S+@[0-9a-f]{40}\b")
PHONE_RES = [
    re.compile(r"(?<![\w.])\+\d{1,3}[\s().\-]?\d{1,4}[\d\s().\-]{5,}\d"),
    re.compile(r"(?<![\d.])0\d{2}[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"),
    re.compile(r"(?<![\d.])\d{3}[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)"),
    re.compile(r"\(\d{2,4}\)\s?\d{3}[\s.\-]?\d{3,4}"),
    re.compile(r"(?<![\d.,])\d{9,}(?![\d,])"),
]
INVISIBLE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u00ad\ufeff]")


# ---------------------------------------------------------------- helpers

def blank(pattern: re.Pattern, text: str) -> str:
    """Replace matches with spaces, keeping newlines so line numbers stay true."""
    return pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def split_front_matter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            cut = text.find("\n", end + 1)
            cut = len(text) if cut == -1 else cut
            return text[:cut], text[cut:]
    return "", text


def yaml_values_only(text: str) -> str:
    out = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            out.append("")
            continue
        out.append(re.sub(r"^(\s*(?:-\s+)*)[A-Za-z0-9_\-]+:(\s|$)", r"\1 \2", line))
    return "\n".join(out)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def norm_quotes(text: str) -> str:
    return text.replace("\u2019", "'").replace("\u2018", "'")


def add(findings, path, line, rule, message):
    findings.append(Finding(path, line, rule, message))


def lines_of(text: str):
    for number, line in enumerate(text.split("\n"), 1):
        yield number, line


# ---------------------------------------------------------------- generic rules (any text file)

def email_allowed(address: str, allowed: set[str]) -> bool:
    low = address.lower()
    return low in allowed or low in ALWAYS_ALLOWED_EMAILS or low.endswith(ALLOWED_EMAIL_SUFFIXES)


def profile_emails(root: Path) -> set[str]:
    path = Path(root) / "_data" / "profile.yml"
    if not path.exists():
        return set()
    return {m.lower() for m in re.findall(r"^email:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)}


def historical_profile_emails(root: Path) -> set[str]:
    """Every address the profile data has ever held, so history stays scannable after the address changes."""
    try:
        out = subprocess.run(["git", "-C", str(root), "log", "-p", "--format=", "--", "_data/profile.yml"],
                             capture_output=True, text=True).stdout
    except OSError:
        return set()
    return {m.lower() for m in re.findall(r"^[+-]email:\s*(\S+)", out, re.M)}


def hidden_char_rules(path: str, text: str, findings: list) -> None:
    for number, line in lines_of(text):
        if INVISIBLE_RE.search(line) or any(unicodedata.category(c) == "Cf" for c in line):
            add(findings, path, number, "hidden-char", "invisible or bidirectional character")
        elif any(unicodedata.name(c, "").startswith(("CYRILLIC", "GREEK")) for c in line):
            add(findings, path, number, "hidden-char", "look-alike letter from another script")


def secret_rules(path: str, text: str, findings: list, credentials: bool = True) -> None:
    raw = norm_quotes(text)
    raw_lines = raw.split("\n")
    no_liquid = blank(LIQUID_RE, raw)
    for number, line in enumerate(raw_lines, 1):
        if PINNED_ACTION_RE.search(line):
            continue
        for regex in SECRET_PREFIX_RES:
            if regex.search(line):
                add(findings, path, number, "secret", "secret-shaped string (prefix match)")
        for regex in CREDENTIAL_RES if credentials else ():
            if regex.search(line):
                add(findings, path, number, "secret", "credential-shaped text")
    for number, line in lines_of(no_liquid):
        if PINNED_ACTION_RE.search(raw_lines[number - 1]):
            continue
        if HEX_RE.search(line):
            add(findings, path, number, "secret", "long hex string")
        if BASE64_RE.search(line):
            add(findings, path, number, "secret", "long base64-like string")
    hidden_char_rules(path, text, findings)


def generic_rules(path: str, text: str, findings: list, allowed_emails: set[str] | None = None) -> None:
    raw = norm_quotes(text)
    secret_rules(path, text, findings)
    no_liquid = blank(LIQUID_RE, raw)
    for number, line in lines_of(no_liquid):
        if re.search(r"\btel:", line, re.I):
            add(findings, path, number, "phone", "tel link")
        for match in EMAIL_RE.findall(line):
            if not email_allowed(match, allowed_emails or set()):
                add(findings, path, number, "email", "email address other than the profile address")
        for regex in ABS_PATH_RES:
            if regex.search(line):
                add(findings, path, number, "abs-path", "absolute path pattern")
                break
        for regex in LOCAL_RES:
            if regex.search(line):
                add(findings, path, number, "local-address", "loopback, address or port pattern")
                break
        for regex in PHONE_RES:
            if regex.search(blank(EMAIL_RE, line)):
                add(findings, path, number, "phone", "phone or identity-number pattern")
                break


def scan_text(text: str, kind: str = "messages", root: Path | None = None) -> list[Finding]:
    """Scan free text: commit messages (generic rules and banned phrases), a diff (generic rules) or secrets only."""
    findings: list[Finding] = []
    if kind == "secrets":
        secret_rules("<stdin>", text, findings, credentials=False)
        return findings
    if kind == "diff":
        text = "\n".join("" if re.match(r"(?:---|\+\+\+) |diff --git|@@ |index [0-9a-f]+\.\.|Binary files |GIT binary patch|(?:new|deleted) file mode |(?:rename|copy) (?:from|to) |similarity index ", l) else l for l in text.split("\n"))
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    known = profile_emails(root) | (historical_profile_emails(root) if kind == "diff" else set())
    generic_rules("<stdin>", text, findings, known)
    if kind == "messages":
        for number, line in lines_of(norm_quotes(text)):
            match = BANNED_RE.search(line)
            if match:
                add(findings, "<stdin>", number, "banned-phrase", "banned phrase: " + match.group(0).lower())
    return findings


# ---------------------------------------------------------------- prose rules

def prose_view(text: str, is_markdown: bool, is_yaml: bool) -> tuple[str, list[tuple[int, str]]]:
    """Reduce text to what a reader sees. Line numbers are preserved. Mermaid labels come back apart."""
    labels: list[tuple[int, str]] = []
    out: list[str] = []
    lines = text.split("\n")
    in_front = is_markdown and bool(lines) and lines[0] == "---"
    in_mermaid = False
    fence_char = ""
    for number, line in enumerate(lines, 1):
        if in_front:
            if number > 1 and line == "---":
                in_front = False
                out.append("")
            else:
                out.append(yaml_values_only(line) if number > 1 else "")
            continue
        if is_markdown:
            fence = FENCE_RE.match(line)
            if in_mermaid:
                if fence and fence.group(1)[0] == fence_char and not fence.group(2).strip():
                    in_mermaid = False
                else:
                    for m in re.finditer(r"[\[\(\{|]([^\]\)\}|]+)[\]\)\}|]", line):
                        labels.append((number, m.group(1)))
                out.append("")
                continue
            if fence:
                if fence.group(2).strip() == "mermaid":
                    in_mermaid = True
                    fence_char = fence.group(1)[0]
                out.append("")
                continue
        out.append(re.sub(r"^\s*<summary[^>]*>", "## ", line))
    view = "\n".join(out)
    if is_yaml and not is_markdown:
        view = yaml_values_only(view)
    for pattern in (HTML_COMMENT_RE, LIQUID_RE, URL_RE, EMAIL_RE, HTML_TAG_RE):
        view = blank(pattern, view)
    return unicodedata.normalize("NFKC", view), labels


def token_problem(token: str) -> str | None:
    if token in NAME_ALLOW or token.rstrip(".") in NAME_ALLOW:
        return None
    if re.search(r"[A-Za-z0-9]_[A-Za-z0-9]", token):
        return "underscore identifier"
    if re.search(r"[a-z][A-Z]", token):
        return "camelCase or hump identifier"
    if re.search(r"[A-Za-z0-9]\.(?:" + CODE_EXTENSIONS + r")$", token, re.I):
        return "file name with a code or config extension"
    return None


def prose_rules(path: str, view: str, labels, findings: list, check_identifiers=True, first_line=1,
                allow_question=False) -> None:
    for number, line in enumerate(view.split("\n"), first_line):
        plain = norm_quotes(line)
        match = BANNED_RE.search(plain)
        if match:
            add(findings, path, number, "banned-phrase", "banned phrase: " + match.group(0).lower())
        for regex, why in VOICE_RES:
            found = regex.search(plain)
            if found:
                add(findings, path, number, "voice", why + ": " + found.group(0).lower())
        if "!" in plain:
            add(findings, path, number, "voice", "exclamation mark")
        if "\u2014" in plain:
            add(findings, path, number, "voice", "em dash")
        if "?" in plain and not allow_question and not re.match(r"\s*(?:#|[-*+]\s|\d+[.)]\s)", plain):
            add(findings, path, number, "voice", "question in body prose")
        if check_identifiers:
            for token in TOKEN_RE.findall(plain):
                problem = token_problem(token)
                if problem:
                    add(findings, path, number, "identifier", problem + ": " + token)
        if CLI_FLAG_RE.search(plain) or SETTING_RE.search(plain):
            add(findings, path, number, "cli-flag", "command-line flag or model setting in prose")
    # phrases that wrap over a line break
    paragraph, start = [], first_line
    for number, line in enumerate(view.split("\n"), first_line):
        if line.strip():
            if not paragraph:
                start = number
            paragraph.append(norm_quotes(line))
        if (not line.strip() or number == first_line + view.count("\n")) and paragraph:
            whole = re.sub(r"\s+", " ", " ".join(paragraph))
            per_line = {m.group(0).lower() for l in paragraph for m in [BANNED_RE.search(l)] if m}
            for match in BANNED_RE.finditer(whole):
                if match.group(0).lower() not in per_line:
                    add(findings, path, start, "banned-phrase", "banned phrase: " + match.group(0).lower())
            paragraph = []
    for number, label in labels:
        for token in TOKEN_RE.findall(norm_quotes(label)):
            problem = token_problem(token)
            if problem:
                add(findings, path, number, "identifier", "in diagram label, " + problem + ": " + token)
        match = BANNED_RE.search(norm_quotes(label))
        if match:
            add(findings, path, number, "banned-phrase", "banned phrase: " + match.group(0).lower())


def markdown_structure_rules(path: str, text: str, findings: list) -> None:
    in_mermaid, fence_char, opened_at = False, "", 0
    lines = text.split("\n")
    in_front = bool(lines) and lines[0] == "---"
    for number, line in enumerate(lines, 1):
        if in_front:
            if number > 1 and line == "---":
                in_front = False
            continue
        fence = FENCE_RE.match(line)
        if in_mermaid:
            if fence and fence.group(1)[0] == fence_char and not fence.group(2).strip():
                in_mermaid = False
            elif not MERMAID_LINE_RE.match(line):
                add(findings, path, number, "fence", "diagram line outside the allowed plain-flowchart grammar")
            continue
        if fence:
            if fence.group(2).strip() == "mermaid":
                in_mermaid, fence_char, opened_at = True, fence.group(1)[0], number
            else:
                add(findings, path, number, "fence", "fenced block other than an exact mermaid diagram")
            continue
        if "`" in line:
            add(findings, path, number, "code-span", "inline code span")
        if re.match(r"^(?: {4,}|\t)\S", line):
            add(findings, path, number, "fence", "indented code block")
        if re.search(r"\{%-?\s*(?:highlight|raw)\b", line):
            add(findings, path, number, "fence", "Liquid highlight or raw block")
        if "<!--" in line:
            add(findings, path, number, "comment", "HTML comment in Markdown")
        if re.search(r"<\s*(?:pre|code|kbd|samp|script|style|svg)\b", line, re.I):
            add(findings, path, number, "raw-code-html", "raw code element in Markdown")
    if in_mermaid:
        add(findings, path, opened_at, "fence", "diagram fence is never closed")


# ---------------------------------------------------------------- file-type and image rules

def png_size(data: bytes):
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    return None


def load_manifest(root: Path):
    path = root / MANIFEST
    if not path.exists():
        return {}
    try:
        return {entry["file"]: entry for entry in json.loads(path.read_text(encoding="utf-8"))}
    except (ValueError, KeyError, TypeError):
        return {}


def file_type_ok(relpath: str, site: bool) -> bool:
    path = Path(relpath)
    if site:
        return path.suffix.lower() in SITE_SUFFIXES
    if relpath.startswith(SCRIPTS_DIR + "/"):
        return path.suffix.lower() in SCRIPT_SUFFIXES
    if relpath.startswith(".github/"):
        return path.suffix.lower() in {".yml", ".yaml", ".md"}
    if path.name in ALLOWED_NAMES and len(path.parts) == 1:
        return True
    if path.suffix.lower() == ".json":
        return relpath in ALLOWED_ROOT_JSON
    return path.suffix.lower() in SOURCE_SUFFIXES


def kind_of(relpath: str) -> str:
    path = Path(relpath)
    name, suffix = path.name, path.suffix.lower()
    if relpath.startswith(SCRIPTS_DIR + "/"):
        return "tooling"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if relpath == MANIFEST:
        return "manifest"
    if relpath.startswith(".github/"):
        return "config"
    if relpath.startswith("_data/") and suffix in {".yml", ".yaml"}:
        return "data"
    if suffix == ".md" or name == "LICENSE":
        return "prose"
    if suffix in {".html", ".css", ".js"}:
        return "markup"
    return "config"


# ---------------------------------------------------------------- tree scan

def git_listed(root: Path):
    """Files that git tracks or would track (not ignored), or None when root is not a repository top level."""
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != Path(root).resolve():
            return None
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard"],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [name for name in out.decode("utf-8", "surrogateescape").split("\0") if name]


def iter_files(root: Path, all_files: bool = False):
    """Every file that counts. Folder names never exempt anything: in a repository, only git-ignored,
    untracked files are skipped; elsewhere (and for the built site) every file is checked."""
    listed = None if all_files else git_listed(root)
    if listed is not None:
        for name in sorted(listed):
            path = Path(root) / name
            if path.is_file() or path.is_symlink():
                yield path
        return
    for path in sorted(Path(root).rglob("*")):
        if ".git" in path.relative_to(root).parts:
            continue
        if path.is_file() or path.is_symlink():
            yield path


def check_images(root: Path, files: list[Path], findings: list, site: bool, manifest_root: Path | None = None) -> None:
    manifest = load_manifest(manifest_root or root)
    seen = set()
    for path in files:
        relpath = rel(path, root)
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        seen.add(relpath)
        if relpath not in manifest:
            add(findings, relpath, 0, "image-unlisted", "image is not listed in the asset manifest")
            continue
        entry = manifest[relpath]
        size = png_size(path.read_bytes())
        if size != (entry.get("width"), entry.get("height")):
            add(findings, relpath, 0, "image-size", "image dimensions differ from the manifest")
    if not site:
        for listed in manifest:
            if listed not in seen:
                add(findings, listed, 0, "image-missing", "image listed in the manifest is missing")


def scan_tree(root: Path) -> list[Finding]:
    root = Path(root)
    findings: list[Finding] = []
    files = list(iter_files(root))
    emails = profile_emails(root)
    check_images(root, [p for p in files if not p.is_symlink()], findings, site=False)
    for path in files:
        relpath = rel(path, root)
        if path.is_symlink():
            add(findings, relpath, 0, "symlink", "symbolic links are not allowed")
            continue
        if not file_type_ok(relpath, site=False):
            add(findings, relpath, 0, "file-type", "file type is not allowed in this repository")
            continue
        kind = kind_of(relpath)
        if kind == "image":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            add(findings, relpath, 0, "file-type", "file is not valid UTF-8 text")
            continue
        if kind == "tooling":
            secret_rules(relpath, text, findings, credentials=False)
            continue
        generic_rules(relpath, text, findings, emails)
        if kind == "manifest":
            for entry in json.loads(text):
                for key in ("alt", "caption"):
                    prose_rules(relpath, entry.get(key, ""), [], findings)
        elif kind in {"prose", "data"}:
            is_md = path.suffix.lower() == ".md" or path.name == "LICENSE"
            if path.suffix.lower() == ".md":
                markdown_structure_rules(relpath, text, findings)
            view, labels = prose_view(text, is_markdown=is_md, is_yaml=(kind == "data"))
            prose_rules(relpath, view, labels, findings)
    return findings


# ---------------------------------------------------------------- built-site scan

class VisibleText(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}
    QUESTION_OK = {"li", "summary", "h1", "h2", "h3", "h4", "h5", "h6", "figcaption", "dt"}
    META_KEYS = {"description", "og:title", "og:description", "twitter:title", "twitter:description",
                 "og:image:alt", "twitter:image:alt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[tuple[int, str, bool]] = []
        self.skip = 0
        self.ld = False
        self.ld_text = ""
        self.ld_line = 0
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.SKIP:
            if tag == "script" and attrs.get("type") == "application/ld+json":
                self.ld, self.ld_text, self.ld_line = True, "", self.getpos()[0]
            else:
                self.skip += 1
        if tag not in {"br", "img", "meta", "link", "input", "hr"}:
            self.stack.append(tag)
        for key in ("alt", "title", "aria-label"):
            if attrs.get(key):
                self.chunks.append((self.getpos()[0], attrs[key], False))
        if tag == "meta":
            name = attrs.get("name") or attrs.get("property") or ""
            if name in self.META_KEYS and attrs.get("content"):
                self.chunks.append((self.getpos()[0], attrs["content"], False))

    def handle_endtag(self, tag):
        if tag == "script" and self.ld:
            self.ld = False
            self.chunks.extend((self.ld_line, v, False) for v in json_values(self.ld_text))
        elif tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self.ld:
            self.ld_text += data
        elif not self.skip and data.strip():
            self.chunks.append((self.getpos()[0], data, bool(self.QUESTION_OK & set(self.stack))))


def json_values(text: str) -> list[str]:
    """String values of a JSON-LD block, leaving out keys and the schema vocabulary."""
    try:
        data = json.loads(text)
    except ValueError:
        return [text]
    out: list[str] = []

    def walk(node, key=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key not in {"@context", "@type"}:
            out.append(node)

    walk(data)
    return out


def scan_site(site_root: Path, manifest_root: Path | None = None) -> list[Finding]:
    site_root = Path(site_root)
    findings: list[Finding] = []
    files = list(iter_files(site_root, all_files=True))
    emails = profile_emails(manifest_root or site_root)
    check_images(site_root, [p for p in files if not p.is_symlink()], findings, site=True,
                 manifest_root=Path(manifest_root) if manifest_root else None)
    for path in files:
        relpath = rel(path, site_root)
        if path.suffix.lower() in IMAGE_SUFFIXES:
            continue
        if not file_type_ok(relpath, site=True):
            add(findings, relpath, 0, "file-type", "file type is not allowed in the built site")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        suffix = path.suffix.lower()
        scan_body = text
        if suffix == ".html":
            scan_body = re.sub(r"<svg\b.*?</svg>", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
        if suffix not in {".js", ".css", ".json"}:
            generic_rules(relpath, scan_body, findings, emails)
        else:
            secret_rules(relpath, text, findings)
        if suffix == ".html":
            parser = VisibleText()
            parser.feed(text)
            for number, chunk, question_ok in parser.chunks:
                view = blank(URL_RE, blank(EMAIL_RE, chunk))
                prose_rules(relpath, view, [], findings, first_line=number, allow_question=question_ok)
    return findings


# ---------------------------------------------------------------- entry point

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]), help="repository root")
    parser.add_argument("--site", help="scan a built site directory instead of the source tree")
    parser.add_argument("--stdin", choices=["messages", "diff", "secrets"], help="scan text from standard input")
    args = parser.parse_args(argv)
    if args.stdin:
        findings = scan_text(sys.stdin.read(), args.stdin, Path(args.root))
        for f in sorted(set(findings)):
            print(f.path + ":" + str(f.line) + "  [" + f.rule + "]  " + f.message)
        print(("\n%d finding(s). The leak scan failed." % len(set(findings))) if findings else "Leak scan passed (stdin, " + args.stdin + ").")
        return 1 if findings else 0
    findings = scan_site(Path(args.site), Path(args.root)) if args.site else scan_tree(Path(args.root))
    for f in sorted(set(findings)):
        where = f.path + (":" + str(f.line) if f.line else "")
        print(where + "  [" + f.rule + "]  " + f.message)
    if findings:
        print("\n" + str(len(set(findings))) + " finding(s). The leak scan failed.")
        return 1
    print("Leak scan passed (" + ("built site" if args.site else "source tree") + ").")
    return 0


if __name__ == "__main__":
    sys.exit(main())
