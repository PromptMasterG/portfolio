"""Tests for the leak scan. Every failing fixture is built at run time, so this file
never contains a real fence, key or path of its own."""
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import leak_scan  # noqa: E402

FENCE = "`" * 3
TICK = "`"


def png_bytes(width=4, height=3):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x00\x00\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def baseline():
    manifest = [{
        "file": "assets/demo/shot.png", "project": "demo", "width": 4, "height": 3,
        "alt": "A small demo picture.", "caption": "A small demo caption.",
    }]
    return {
        "assets-manifest.json": json.dumps(manifest),
        "assets/demo/shot.png": png_bytes(),
        "index.md": "---\ntitle: Home\n---\nA plain sentence about measured work, as of 1 Nov 2026.\n",
        "work/demo.md": "---\ntitle: Demo\n---\nA short paragraph.\n",
        "LICENSE": "All rights reserved. View for evaluation only.\n",
    }


class Fixture:
    def __init__(self, extra=None, remove=()):
        self.files = baseline()
        for name in remove:
            self.files.pop(name, None)
        self.files.update(extra or {})

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for rel, content in self.files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        self.root = root
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def rules(self):
        return {f.rule for f in leak_scan.scan_tree(self.root)}


def body(text):
    return {"work/demo.md": "---\ntitle: Demo\n---\n" + text + "\n"}


class CleanTree(unittest.TestCase):
    def test_baseline_passes(self):
        with Fixture() as fx:
            self.assertEqual(fx.rules(), set())

    def test_mermaid_fence_with_plain_labels_passes(self):
        text = FENCE + "mermaid\nflowchart TD\n  A[Writing page] --> B[Safety screen]\n" + FENCE
        with Fixture(body(text)) as fx:
            self.assertEqual(fx.rules(), set())

    def test_public_brand_names_and_urls_pass(self):
        text = ("I publish on YouTube and LinkedIn and use ChromaDB, ElevenLabs, CapCut and TypeScript. "
                "See https://www.youtube.com/watch?v=Y7XaDXi2uto and [the tool](https://veopromptai.netlify.app).")
        with Fixture(body(text)) as fx:
            self.assertEqual(fx.rules(), set())

    def test_yaml_keys_may_use_underscores_but_values_may_not(self):
        data = "demo:\n  as_of: 2026-11-01\n  claim_id: C45\n  value: a plain value\n"
        with Fixture({"_data/facts.yml": data}) as fx:
            self.assertEqual(fx.rules(), set())

    def test_comments_in_data_files_are_not_published_prose(self):
        data = "# Notes about facts.yml and proof_fact for editors\ndemo:\n  value: a plain value\n"
        with Fixture({"_data/facts.yml": data}) as fx:
            self.assertEqual(fx.rules(), set())

    def test_liquid_tags_are_ignored_in_prose(self):
        text = 'Counted {% include fact.html id="tests-total" %} on 1 Nov 2026.'
        with Fixture(body(text)) as fx:
            self.assertEqual(fx.rules(), set())

    def test_llama_cpp_is_allowed_as_a_public_name(self):
        with Fixture(body("The server is built on llama.cpp.")) as fx:
            self.assertEqual(fx.rules(), set())

    def test_scripts_folder_is_exempt_from_content_rules_but_not_file_types(self):
        extra = {".github/scripts/check.py": "BANNED = ['leverage']\nHOST = 'localhost'\n"}
        with Fixture(extra) as fx:
            self.assertEqual(fx.rules(), set())


class MustFail(unittest.TestCase):
    def assert_fails(self, rule, extra=None, remove=()):
        with Fixture(extra, remove) as fx:
            self.assertIn(rule, fx.rules())

    def test_fenced_python_block(self):
        self.assert_fails("fence", body(FENCE + "python\nprint(1)\n" + FENCE))

    def test_fence_without_a_language(self):
        self.assert_fails("fence", body(FENCE + "\nplain\n" + FENCE))

    def test_tilde_fence(self):
        self.assert_fails("fence", body("~~~\nplain\n~~~"))

    def test_inline_code_span(self):
        self.assert_fails("code-span", body("Call " + TICK + "thing" + TICK + " now."))

    def test_raw_pre_element_in_markdown(self):
        self.assert_fails("raw-code-html", body("<pre>text</pre>"))

    def test_fake_api_key(self):
        self.assert_fails("secret", body("key " + "AIza" + "Sy" + "A" * 33))

    def test_provider_token_prefixes(self):
        self.assert_fails("secret", body("token " + "gh" + "p_" + "a1B2" * 9))
        self.assert_fails("secret", body("key " + "sk" + "-" + "abcd1234" * 3))

    def test_long_hex_string(self):
        self.assert_fails("secret", body("hash " + "0123456789abcdef" * 3))

    def test_long_base64_like_string(self):
        self.assert_fails("secret", body("blob " + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7" * 2))

    def test_unlisted_image(self):
        self.assert_fails("image-unlisted", {"assets/demo/other.png": png_bytes()})

    def test_unlisted_image_of_another_type(self):
        self.assert_fails("image-unlisted", {"assets/demo/logo.svg": "<svg></svg>"})

    def test_listed_image_that_is_missing(self):
        self.assert_fails("image-missing", remove=["assets/demo/shot.png"])

    def test_listed_image_with_wrong_dimensions(self):
        self.assert_fails("image-size", {"assets/demo/shot.png": png_bytes(9, 9)})

    def test_forbidden_file_types(self):
        for name in ("run.sh", "store.db", "model.gguf", "notes.env", "doc.pdf", "data/blob.bin", "main.rs"):
            with self.subTest(name=name):
                self.assert_fails("file-type", {name: "x"})

    def test_python_outside_scripts_folder(self):
        self.assert_fails("file-type", {"tools/helper.py": "x = 1\n"})

    def test_windows_path(self):
        self.assert_fails("abs-path", body("See " + "C:" + "\\" + "Users" + "\\" + "someone" + "\\" + "work."))

    def test_unix_home_path(self):
        self.assert_fails("abs-path", body("See /ho" + "me/someone/work for it."))

    def test_loopback_address_and_localhost(self):
        self.assert_fails("local-address", body("Open http://local" + "host:80" + "80/ now."))
        self.assert_fails("local-address", body("Bound to 127" + ".0.0.1 only."))

    def test_phone_numbers(self):
        for number in ("+27 " + "82 555 0123", "082 " + "555 0123", "(021) " + "555-0123", "082" + "5550123"):
            with self.subTest(number=number):
                self.assert_fails("phone", body("Call " + number + " today."))

    def test_thirteen_digit_identity_number(self):
        self.assert_fails("phone", body("Number " + "9001015800" + "086."))

    def test_snake_case_identifier_in_prose(self):
        self.assert_fails("identifier", body("It uses the load_" + "config helper."))

    def test_camel_case_identifier_in_prose(self):
        self.assert_fails("identifier", body("It calls loadCon" + "fig first."))

    def test_file_name_with_extension_in_prose(self):
        self.assert_fails("identifier", body("It reads settings" + ".toml at start."))

    def test_identifier_inside_a_mermaid_label(self):
        text = FENCE + "mermaid\nflowchart TD\n  A[run_" + "job] --> B[Done]\n" + FENCE
        self.assert_fails("identifier", body(text))

    def test_banned_phrases(self):
        for phrase in ("lever" + "age", "seam" + "less", "cutting" + "-edge", "deep " + "dive", "gu" + "ru",
                       "it’s not " + "just a tool", "not only fast " + "but also cheap"):
            with self.subTest(phrase=phrase):
                self.assert_fails("banned-phrase", body("A sentence with " + phrase + " inside."))

    def test_exclamation_mark_and_em_dash(self):
        self.assert_fails("voice", body("It works!"))
        self.assert_fails("voice", body("It works — mostly."))

    def test_question_in_body_prose_but_not_in_a_heading(self):
        self.assert_fails("voice", body("Who is this for?"))
        with Fixture(body("## Why is there no code?\n\nThe work is private.")) as fx:
            self.assertEqual(fx.rules(), set())

    def test_questions_are_fine_in_list_items_and_summaries(self):
        with Fixture(body("- Why did it fail?\n\n<details>\n<summary>Why is there no code?</summary>\n<p>It is private.</p>\n</details>")) as fx:
            self.assertEqual(fx.rules(), set())

    def test_feeling_words(self):
        self.assert_fails("voice", body("I lo" + "ve this work."))

    def test_banned_phrase_in_data_value(self):
        self.assert_fails("banned-phrase", {"_data/facts.yml": "demo:\n  value: a lever" + "age story\n"})


class Hardening(unittest.TestCase):
    """Bypasses found by a red-team pass. Each fixture is assembled at run time."""

    def assert_fails(self, rule, extra=None, remove=()):
        with Fixture(extra, remove) as fx:
            self.assertIn(rule, fx.rules())

    def test_folder_names_that_look_ignored_do_not_hide_content(self):
        for folder in ("vendor", "node_modules", "_site", "__pycache__", "sub/vendor", ".bundle"):
            with self.subTest(folder=folder):
                self.assert_fails("fence", {folder + "/x.md": "---\ntitle: X\n---\n" + FENCE + "python\nx\n" + FENCE + "\n"})

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_in_a_git_repository_only_ignored_untracked_files_are_skipped(self):
        bad = "---\ntitle: X\n---\n" + FENCE + "python\nx\n" + FENCE + "\n"
        with Fixture({".gitignore": "vendor/\n", "vendor/tracked.md": bad, "vendor/loose.md": bad}) as fx:
            run = lambda *a: subprocess.run(["git", "-C", str(fx.root), *a], check=True, capture_output=True)
            run("init", "-q")
            run("add", "-f", "vendor/tracked.md")
            paths = {f.path for f in leak_scan.scan_tree(fx.root)}
            self.assertIn("vendor/tracked.md", paths)
            self.assertNotIn("vendor/loose.md", paths)

    def test_indented_code_block_and_liquid_highlight_and_comments(self):
        self.assert_fails("fence", body("Intro.\n\n    print(1)\n"))
        self.assert_fails("fence", body("{% highlight text %}\nx\n{% endhighlight %}"))
        self.assert_fails("comment", body("A line.\n<!-- private note -->\n"))

    def test_diagram_fence_must_be_exact_closed_and_plain(self):
        self.assert_fails("fence", body(FENCE + "mermaid python\nflowchart TD\n  A[One] --> B[Two]\n" + FENCE))
        self.assert_fails("fence", body(FENCE + "mermaid\nflowchart TD\n  A[One] --> B[Two]\n"))
        self.assert_fails("fence", body(FENCE + "mermaid\nflowchart TD\n  A[Run $(thing)] --> B[Two]\n" + FENCE))
        self.assert_fails("fence", body(FENCE + "mermaid\nflowchart TD\n  A --> B\n  curl something\n" + FENCE))
        ok = FENCE + "mermaid\nflowchart TD\n  A[One] -->|labelled| B[Two]\n  A --> C[Three, with a comma]\n" + FENCE
        with Fixture(body(ok)) as fx:
            self.assertEqual(fx.rules(), set())

    def test_secrets_in_urls_and_credentials(self):
        self.assert_fails("secret", body("See https://example.org/a?k=" + "0123456789abcdef" * 2 + " now."))
        self.assert_fails("secret", body("See https://us" + "er:pa" + "ss@example.org/x now."))
        self.assert_fails("secret", body("The pass" + "word = hunter2 here."))
        self.assert_fails("secret", body("Header Bear" + "er abcdefghijklmnop12345 here."))
        self.assert_fails("phone", body("Chat at https://example.org/c/" + "27825550123" + " now."))

    def test_path_and_port_variants(self):
        self.assert_fails("abs-path", body("See C" + ":/Us" + "ers/someone/work."))
        self.assert_fails("abs-path", body("See " + "\\\\" + "server" + "\\" + "share."))
        self.assert_fails("abs-path", body("Open file" + ":///" + "tmp/x now."))
        self.assert_fails("abs-path", body("See $HO" + "ME/work now."))
        self.assert_fails("local-address", body("Bound to ::" + "1 only."))
        self.assert_fails("local-address", body("Reach it at example.org:" + "80" + "80 now."))
        self.assert_fails("local-address", body("Set POR" + "T=80" + "80 first."))

    def test_hidden_and_lookalike_characters(self):
        self.assert_fails("hidden-char", body("A sea" + "\u200b" + "mless path."))
        self.assert_fails("hidden-char", body("A sea" + "\u00ad" + "mless path."))
        self.assert_fails("hidden-char", body("A word with a Cyrillic \u0430 inside."))

    def test_banned_phrase_variants_and_line_wrapping(self):
        for phrase in ("cutting " + "edge", "state of the " + "art", "best in " + "class", "game" + "changer", "rock " + "star"):
            with self.subTest(phrase=phrase):
                self.assert_fails("banned-phrase", body("A sentence with " + phrase + " inside."))
        self.assert_fails("banned-phrase", body("It is not only fast\nbut also cheap."))
        self.assert_fails("voice", body("What a fine day\uff01"))

    def test_other_email_addresses_are_flagged_but_the_profile_address_is_not(self):
        self.assert_fails("email", body("Write to someone" + "@example.org today."))
        profile = {"_data/profile.yml": "email: me" + "@example.org\n"}
        with Fixture({**profile, **body("Write to me" + "@example.org today.")}) as fx:
            self.assertEqual(fx.rules(), set())

    def test_package_specs_are_not_email_addresses_and_code_annotations_are_not_credentials(self):
        yaml = "run: npm install playwright-core@1.63.0 @lhci/cli@0.15.1\n"
        with Fixture({".github/workflows/x.yml": yaml, ".github/scripts/x.py": "def f(token: str) -> str:\n    return token\n"}) as fx:
            self.assertEqual(fx.rules(), set())

    def test_diff_headers_are_not_content(self):
        diff = "--- /dev/null\n+++ b/page.md\n@@ -0,0 +1 @@\n+A plain line.\n"
        self.assertEqual({f.rule for f in leak_scan.scan_text(diff, "diff")}, set())

    def test_binary_file_lines_in_a_diff_are_headers_not_content(self):
        diff = "diff --git a/x.png b/x.png\ndeleted file mode 100644\nBinary files a/x.png and /dev/null differ\n"
        self.assertEqual({f.rule for f in leak_scan.scan_text(diff, "diff")}, set())

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_diff_scan_allows_earlier_profile_addresses_but_no_others(self):
        with Fixture({"_data/profile.yml": "email: old" + "@example.org\n"}) as fx:
            def run(*args):
                subprocess.run(["git", "-C", str(fx.root), "-c", "user.name=t", "-c", "user.email=t" + "@example.org", *args],
                               check=True, capture_output=True)
            run("init", "-q")
            run("add", "-A")
            run("commit", "-q", "-m", "one")
            (fx.root / "_data/profile.yml").write_text("email: new" + "@example.org\n")
            run("commit", "-qam", "two")
            history = "-email: old" + "@example.org\n+email: new" + "@example.org\n"
            self.assertEqual({f.rule for f in leak_scan.scan_text(history, "diff", fx.root)}, set())
            other = "+Write to someone" + "@example.net today.\n"
            self.assertIn("email", {f.rule for f in leak_scan.scan_text(other, "diff", fx.root)})

    def test_symlink_is_flagged(self):
        with Fixture() as fx:
            try:
                (fx.root / "link.md").symlink_to(fx.root / "index.md")
            except OSError:
                self.skipTest("symlinks not available")
            self.assertIn("symlink", fx.rules())

    def test_tooling_files_are_scanned_for_secrets_but_not_for_patterns(self):
        self.assert_fails("secret", {".github/scripts/x.py": "KEY = '" + "AIza" + "Sy" + "A" * 33 + "'\n"})
        self.assert_fails("hidden-char", {".github/scripts/x.py": "x = 1\u200b\n"})

    def test_cli_flags_and_sampler_settings_in_prose(self):
        self.assert_fails("cli-flag", body("Start it with --ctx" + "-size and go."))
        self.assert_fails("cli-flag", body("It ran at tempera" + "ture 0.7 for a week."))

    def test_commit_messages_and_diffs(self):
        clean = "Add pages\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01KQr1sTgAP3WwSjAiRpxRUv\n"
        self.assertEqual({f.rule for f in leak_scan.scan_text(clean, "messages")}, set())
        self.assertIn("phone", {f.rule for f in leak_scan.scan_text("Call 082 555 " + "0123 now", "messages")})
        self.assertIn("banned-phrase", {f.rule for f in leak_scan.scan_text("A seam" + "less change", "messages")})
        self.assertIn("secret", {f.rule for f in leak_scan.scan_text("+key " + "gh" + "p_" + "a1B2" * 9, "diff")})
        self.assertEqual({f.rule for f in leak_scan.scan_text("A seam" + "less change", "diff")}, set())


class BuiltSite(unittest.TestCase):
    def scan(self, html, extra=None):
        files = {"assets-manifest.json": baseline()["assets-manifest.json"],
                 "assets/demo/shot.png": png_bytes(), "page.html": html}
        files.update(extra or {})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, content in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content, encoding="utf-8")
            return {f.rule for f in leak_scan.scan_site(root)}

    def test_clean_page_passes(self):
        html = ('<html><head><title>Home</title><meta name="description" content="A plain page.">'
                '<script>var x_y = 1;</script></head><body><p>Plain text on YouTube.</p>'
                '<img src="assets/demo/shot.png" alt="A small demo picture."></body></html>')
        self.assertEqual(self.scan(html), set())

    def test_visible_text_is_checked_for_identifiers_and_phrases(self):
        self.assertIn("identifier", self.scan("<html><body><p>See load_" + "config here.</p></body></html>"))
        self.assertIn("banned-phrase", self.scan("<html><body><p>A seam" + "less path.</p></body></html>"))

    def test_alt_text_and_meta_description_are_checked(self):
        self.assertIn("banned-phrase", self.scan('<html><body><img alt="A cutting' + '-edge view" src="a.png"></body></html>'))
        self.assertIn("banned-phrase", self.scan('<html><head><meta name="description" content="Pure lever' + 'age."></head></html>'))

    def test_unlisted_png_in_site_output(self):
        self.assertIn("image-unlisted", self.scan("<html></html>", {"assets/demo/stray.png": png_bytes()}))

    def test_json_ld_vocabulary_is_not_prose_but_its_values_are(self):
        ld = '<script type="application/ld+json">{"@type":"Person","jobTitle":"Builder","sameAs":["https://example.org/a"]}</script>'
        self.assertEqual(self.scan("<html><head>" + ld + "</head><body><p>Text.</p></body></html>"), set())
        bad = '<script type="application/ld+json">{"@type":"Person","jobTitle":"A seam' + 'less builder"}</script>'
        self.assertIn("banned-phrase", self.scan("<html><head>" + bad + "</head></html>"))

    def test_questions_in_list_items_and_headings_are_allowed_in_the_built_site(self):
        self.assertEqual(self.scan("<html><body><h2>Why no code?</h2><ul><li>Why did it fail?</li></ul></body></html>"), set())
        self.assertIn("voice", self.scan("<html><body><p>Who is this for?</p></body></html>"))

    def test_manifest_can_come_from_the_repository_root(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as site:
            Path(repo, "assets-manifest.json").write_text(baseline()["assets-manifest.json"])
            target = Path(site, "assets/demo")
            target.mkdir(parents=True)
            (target / "shot.png").write_bytes(png_bytes())
            self.assertEqual({f.rule for f in leak_scan.scan_site(Path(site), Path(repo))}, set())

    def test_xml_and_text_output_are_allowed(self):
        self.assertEqual(self.scan("<html></html>", {"sitemap.xml": "<urlset/>", "robots.txt": "User-agent: *\n"}), set())


if __name__ == "__main__":
    unittest.main()
