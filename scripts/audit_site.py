#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///

"""Black-box audit of a clean generated site artifact.

The audit observes only the deployable tree and the frozen migration
manifests. It does not import Typst helpers or build internals.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_DIR = REPO_ROOT / "docs" / "migration" / "freeze"
DEFAULT_SITE = REPO_ROOT / "_site"

REQUIRED_MANIFESTS = (
    "baseline.json",
    "legacy-production-manifest.json",
    "standalone-research-manifest.json",
)

# Paths every production-equivalent replacement build must emit today.
REQUIRED_BUILD_PATHS = (
    "index.html",
    "sitemap.xml",
    "robots.txt",
    "feed.xml",
)

LOCAL_REF_ATTRS = ("href", "src", "poster", "data")
CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.I)
SKIP_SCHEMES = ("http://", "https://", "//", "mailto:", "data:", "javascript:", "tel:")


class AuditError(Exception):
    """One audit failure with a stable message."""


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: v for k, v in attrs if v}
        for key in LOCAL_REF_ATTRS:
            if key in attr_map:
                self.refs.append(attr_map[key])
        if tag == "source" and "srcset" in attr_map:
            for part in attr_map["srcset"].split(","):
                candidate = part.strip().split(" ", 1)[0]
                if candidate:
                    self.refs.append(candidate)


class AuditReport:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def ok(self, _message: str) -> None:
        self.checks += 1

    def fail(self, message: str) -> None:
        self.checks += 1
        self.failures.append(message)

    @property
    def ok_count(self) -> int:
        return self.checks - len(self.failures)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuditError(f"missing required freeze file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AuditError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AuditError(f"expected object JSON in {path}")
    return data


def check_manifests(report: AuditReport, freeze_dir: Path) -> dict[str, dict]:
    manifests: dict[str, dict] = {}
    if not freeze_dir.is_dir():
        report.fail(f"freeze directory missing: {freeze_dir}")
        return manifests

    for name in REQUIRED_MANIFESTS:
        path = freeze_dir / name
        if not path.is_file():
            try:
                display = path.relative_to(REPO_ROOT)
            except ValueError:
                display = path
            report.fail(f"missing freeze manifest: {display}")
            continue
        try:
            data = load_json(path)
        except AuditError as exc:
            report.fail(str(exc))
            continue
        if "schema_version" not in data:
            report.fail(f"{name} missing schema_version")
            continue
        manifests[name] = data
        report.ok(f"manifest present: {name}")

    legacy = manifests.get("legacy-production-manifest.json")
    if legacy is not None:
        files = legacy.get("files")
        if not isinstance(files, dict) or len(files) == 0:
            report.fail("legacy-production-manifest.json has no files entries")
        else:
            missing_checksum = [
                path
                for path, meta in files.items()
                if not isinstance(meta, dict) or not meta.get("sha256")
            ]
            if missing_checksum:
                report.fail(
                    "legacy-production-manifest.json missing sha256 for: "
                    + ", ".join(sorted(missing_checksum)[:5])
                )
            else:
                report.ok(f"legacy manifest checksums present ({len(files)} files)")

    research = manifests.get("standalone-research-manifest.json")
    if research is not None:
        files = research.get("files")
        entry_pages = research.get("entry_pages")
        if not isinstance(files, dict) or not files:
            report.fail("standalone-research-manifest.json has no files entries")
        elif not isinstance(entry_pages, dict) or not entry_pages:
            report.fail("standalone-research-manifest.json has no entry_pages")
        else:
            unreachable = [
                path
                for path, meta in files.items()
                if not isinstance(meta, dict) or not meta.get("live_reachable", True)
            ]
            if unreachable:
                report.fail(
                    "standalone research manifest contains unreachable paths: "
                    + ", ".join(sorted(unreachable)[:5])
                )
            else:
                report.ok(
                    f"research manifest reachability recorded ({len(files)} paths)"
                )

    baseline = manifests.get("baseline.json")
    if baseline is not None:
        required_keys = ("legacy_source", "netlify_production", "dns", "http_responses")
        missing = [key for key in required_keys if key not in baseline]
        if missing:
            report.fail(f"baseline.json missing keys: {', '.join(missing)}")
        else:
            report.ok("baseline records source, Netlify, DNS, and HTTP data")

    return manifests


def check_required_build_paths(report: AuditReport, site_dir: Path) -> None:
    if not site_dir.is_dir():
        report.fail(f"generated site directory missing: {site_dir}")
        return

    for rel in REQUIRED_BUILD_PATHS:
        path = site_dir / rel
        if path.is_file():
            report.ok(f"required build path present: /{rel}")
        else:
            report.fail(f"required build path missing: /{rel}")


def parse_html_file(path: Path) -> tuple[bool, list[str], str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, [], f"unreadable HTML {path}: {exc}"
    parser = LinkCollector()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:  # html.parser is permissive; keep guard
        return False, [], f"unparseable HTML {path}: {exc}"
    return True, parser.refs, None


def iter_local_targets(page_path: Path, site_dir: Path, refs: Iterable[str]) -> list[Path]:
    targets: list[Path] = []
    for ref in refs:
        ref = ref.strip()
        if not ref or ref.startswith("#") or ref.startswith(SKIP_SCHEMES):
            continue
        parsed = urlparse(ref)
        if parsed.scheme or parsed.netloc:
            continue
        clean = unquote(parsed.path)
        if not clean:
            continue
        if clean.startswith("/"):
            target = site_dir / clean.lstrip("/")
        else:
            target = (page_path.parent / clean).resolve()
            try:
                target.relative_to(site_dir.resolve())
            except ValueError:
                # Outside the site tree; ignore as non-local artifact path.
                continue
        if target.is_dir():
            index = target / "index.html"
            targets.append(index)
        else:
            targets.append(target)
    return targets


def check_html_and_links(report: AuditReport, site_dir: Path) -> None:
    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        report.fail("no HTML files found in generated site")
        return

    for html_path in html_files:
        ok, refs, err = parse_html_file(html_path)
        rel = html_path.relative_to(site_dir).as_posix()
        if not ok:
            report.fail(err or f"unparseable HTML: /{rel}")
            continue
        report.ok(f"parseable HTML: /{rel}")
        for target in iter_local_targets(html_path, site_dir, refs):
            try:
                rel_target = target.resolve().relative_to(site_dir.resolve()).as_posix()
            except ValueError:
                rel_target = target.as_posix()
            if target.exists():
                report.ok(f"local target exists: /{rel} -> /{rel_target}")
            else:
                report.fail(f"broken local link in /{rel}: missing /{rel_target}")


def check_assets_from_css(report: AuditReport, site_dir: Path) -> None:
    for css_path in sorted(site_dir.rglob("*.css")):
        try:
            text = css_path.read_text(encoding="utf-8")
        except OSError as exc:
            report.fail(f"unreadable CSS {css_path}: {exc}")
            continue
        rel = css_path.relative_to(site_dir).as_posix()
        for match in CSS_URL_RE.finditer(text):
            ref = match.group(2).strip()
            if not ref or ref.startswith(SKIP_SCHEMES) or ref.startswith("#"):
                continue
            parsed = urlparse(ref)
            if parsed.scheme or parsed.netloc:
                continue
            clean = unquote(parsed.path)
            if clean.startswith("/"):
                target = site_dir / clean.lstrip("/")
            else:
                target = (css_path.parent / clean).resolve()
            if target.exists():
                report.ok(f"css asset exists: /{rel}")
            else:
                try:
                    rel_target = target.relative_to(site_dir.resolve()).as_posix()
                except ValueError:
                    rel_target = str(target)
                report.fail(f"broken css url in /{rel}: missing /{rel_target}")


def check_xml_files(report: AuditReport, site_dir: Path) -> None:
    for name in ("sitemap.xml", "feed.xml"):
        path = site_dir / name
        if not path.is_file():
            # required-path check already reports absence
            continue
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            report.fail(f"unparseable XML /{name}: {exc}")
        else:
            report.ok(f"parseable XML: /{name}")


def check_preservation_if_present(
    report: AuditReport, site_dir: Path, manifests: dict[str, dict]
) -> None:
    """If migrated preservation paths are already in the site, enforce them."""
    research = manifests.get("standalone-research-manifest.json")
    if not research:
        return

    files = research.get("files") or {}
    entry_pages = research.get("entry_pages") or {}
    present_entries = [
        path
        for path in entry_pages
        if (site_dir / path).is_file() or (site_dir / path.lstrip("/")).is_file()
    ]

    if not present_entries:
        report.ok("no standalone research entry pages present yet")
        return

    for entry in present_entries:
        meta = entry_pages[entry]
        deps = meta.get("dependencies") or []
        required = [entry, *deps]
        for rel in required:
            rel = rel.lstrip("/")
            target = site_dir / rel
            expected = files.get(rel) or files.get("/" + rel) or {}
            if not target.is_file():
                report.fail(f"preservation path missing for present research entry: /{rel}")
                continue
            actual_sha = _sha256(target)
            expected_sha = expected.get("sha256")
            if expected_sha and actual_sha != expected_sha:
                report.fail(
                    f"preservation checksum mismatch for /{rel}: "
                    f"expected {expected_sha}, got {actual_sha}"
                )
            else:
                report.ok(f"preservation path ok: /{rel}")


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_site(site_dir: Path, freeze_dir: Path = FREEZE_DIR) -> AuditReport:
    report = AuditReport()
    manifests = check_manifests(report, freeze_dir)
    check_required_build_paths(report, site_dir)
    if site_dir.is_dir():
        check_html_and_links(report, site_dir)
        check_assets_from_css(report, site_dir)
        check_xml_files(report, site_dir)
        check_preservation_if_present(report, site_dir, manifests)
    return report


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_self_test() -> int:
    """Prove the audit fails on controlled malformed artifacts and passes on a minimal good site."""
    import hashlib

    failures: list[str] = []

    def expect_fail(label: str, site_dir: Path, freeze_dir: Path) -> None:
        report = audit_site(site_dir, freeze_dir=freeze_dir)
        if not report.failures:
            failures.append(f"{label}: expected audit failure, got success")
        else:
            print(f"  self-test ok (failed as expected): {label} -> {report.failures[0]}")

    def expect_pass(label: str, site_dir: Path, freeze_dir: Path) -> None:
        report = audit_site(site_dir, freeze_dir=freeze_dir)
        if report.failures:
            failures.append(f"{label}: expected success, got: {report.failures[0]}")
        else:
            print(f"  self-test ok (passed as expected): {label}")

    def sha_text(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    with tempfile.TemporaryDirectory(prefix="audit-self-test-") as tmp:
        tmp_path = Path(tmp)
        freeze = tmp_path / "freeze"
        freeze.mkdir()

        research_html = "<html><body>research</body></html>"
        research_css = "body{}"

        _write(
            freeze / "baseline.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "legacy_source": {"repository": "example/quarto-blog", "revision": "abc"},
                    "netlify_production": {"site_name": "example"},
                    "dns": {"anatolii.nz": {"A": []}},
                    "http_responses": {"https://example.test/": {"status": 200}},
                }
            ),
        )
        _write(
            freeze / "legacy-production-manifest.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "files": {
                        "index.html": {
                            "path": "/index.html",
                            "sha256": "0" * 64,
                            "bytes": 1,
                        }
                    },
                }
            ),
        )
        _write(
            freeze / "standalone-research-manifest.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "entry_pages": {
                        "research.html": {
                            "path": "/research.html",
                            "sha256": sha_text(research_html),
                            "bytes": len(research_html.encode()),
                            "dependencies": ["research.css"],
                        }
                    },
                    "files": {
                        "research.html": {
                            "path": "/research.html",
                            "sha256": sha_text(research_html),
                            "bytes": len(research_html.encode()),
                            "live_reachable": True,
                        },
                        "research.css": {
                            "path": "/research.css",
                            "sha256": sha_text(research_css),
                            "bytes": len(research_css.encode()),
                            "live_reachable": True,
                        },
                    },
                }
            ),
        )

        good_site = tmp_path / "good_site"
        _write(
            good_site / "index.html",
            "<!doctype html><html lang='en'><head><title>t</title>"
            "<link rel='stylesheet' href='/assets/site.css'></head>"
            "<body><a href='/about/'>About</a></body></html>",
        )
        _write(good_site / "about" / "index.html", "<!doctype html><html><body>About</body></html>")
        _write(good_site / "assets" / "site.css", "body{color:black}")
        _write(
            good_site / "sitemap.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.test/</loc></url></urlset>",
        )
        _write(
            good_site / "feed.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<rss version='2.0'><channel><title>t</title></channel></rss>",
        )
        _write(good_site / "robots.txt", "User-agent: *\nAllow: /\n")
        expect_pass("minimal good site", good_site, freeze)

        missing_sitemap = tmp_path / "missing_sitemap"
        shutil.copytree(good_site, missing_sitemap)
        (missing_sitemap / "sitemap.xml").unlink()
        expect_fail("missing sitemap.xml", missing_sitemap, freeze)

        broken_link = tmp_path / "broken_link"
        shutil.copytree(good_site, broken_link)
        _write(
            broken_link / "index.html",
            "<!doctype html><html><body><a href='/missing-page/'>x</a></body></html>",
        )
        expect_fail("broken local link", broken_link, freeze)

        bad_xml = tmp_path / "bad_xml"
        shutil.copytree(good_site, bad_xml)
        _write(bad_xml / "feed.xml", "<rss><channel>no close")
        expect_fail("malformed feed.xml", bad_xml, freeze)

        incomplete_freeze = tmp_path / "incomplete_freeze"
        shutil.copytree(freeze, incomplete_freeze)
        (incomplete_freeze / "baseline.json").unlink()
        expect_fail("missing baseline manifest", good_site, incomplete_freeze)

        preserved = tmp_path / "preserved"
        shutil.copytree(good_site, preserved)
        _write(preserved / "research.html", research_html)
        expect_fail("research entry without dependency", preserved, freeze)

        bad_research_freeze = tmp_path / "bad_research_freeze"
        shutil.copytree(freeze, bad_research_freeze)
        research = json.loads(
            (bad_research_freeze / "standalone-research-manifest.json").read_text(encoding="utf-8")
        )
        research["files"]["research.css"]["live_reachable"] = False
        _write(bad_research_freeze / "standalone-research-manifest.json", json.dumps(research))
        expect_fail("research manifest unreachable path", good_site, bad_research_freeze)

    if failures:
        print("self-test failures:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("self-test passed: audit fails on controlled malformed artifacts")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site",
        type=Path,
        default=DEFAULT_SITE,
        help="Path to the generated site directory (default: _site)",
    )
    parser.add_argument(
        "--freeze-dir",
        type=Path,
        default=FREEZE_DIR,
        help="Path to freeze manifests (default: docs/migration/freeze)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run controlled malformed-artifact demonstrations and exit",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    site_dir = args.site if args.site.is_absolute() else REPO_ROOT / args.site
    freeze_dir = args.freeze_dir if args.freeze_dir.is_absolute() else REPO_ROOT / args.freeze_dir

    report = audit_site(site_dir, freeze_dir=freeze_dir)
    if report.failures:
        print(f"audit failed with {len(report.failures)} issue(s); {report.ok_count} check(s) passed")
        for failure in report.failures:
            print(f"  ERROR: {failure}")
        return 1

    print(f"audit passed: {report.ok_count} check(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
