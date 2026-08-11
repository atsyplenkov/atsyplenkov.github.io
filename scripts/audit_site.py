#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///

"""Black-box audit of a clean generated site artifact.

The audit observes only the deployable tree and the frozen migration
manifests. It does not import Typst helpers or build internals.

Point ``--site`` at any directory that looks like the published tree
(local ``_site``, a CI Pages artifact extract, or a downloaded staging
mirror). Canonical host checks always use ``https://anatolii.nz``; the
staging host ``https://atsyplenkov.github.io`` is for live reachability
only and is not substituted into metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_DIR = REPO_ROOT / "scripts" / "fixtures" / "migration-freeze"
DEFAULT_SITE = REPO_ROOT / "_site"

REQUIRED_MANIFESTS = (
    "baseline.json",
    "legacy-production-manifest.json",
    "standalone-research-manifest.json",
)

# Paths every production-equivalent replacement build must emit today.
REQUIRED_BUILD_PATHS = (
    "index.html",
    "about/index.html",
    "papers/index.html",
    "talks/index.html",
    "software/index.html",
    "blog/2020-03-03-tidy-tuesday-nhl/index.html",
    "blog/2022-03-05-soilgrids-terra/index.html",
    "blog/2024-08-06-xgboost-gpu-r/index.html",
    "blog/2024-02-11-anzgg2024/index.html",
    "sitemap.xml",
    "robots.txt",
    "feed.xml",
    "llms.txt",
    "about.html",
    "papers.html",
    "talks.html",
    "software.html",
    "app.html",
    "posts/2020-03-03-tidy-tuesday-nhl/2020-03-03-tidy-tuesday-nhl.html",
    "posts/2022-03-05-soilgrids-terra/2022-03-05-soilgrids-terra.html",
    "posts/2024/xgboost-gpu-r.html",
    "posts/anzgg2024.html",
    "data/posters/anzgg2024_caucasus-poster_tsyplenkov.pdf",
    "posts/anzgg2024_caucasus-poster_tsyplenkov.png",
    "data/Tsyplenkov-Anatoly_CV.pdf",
    "data/!publ_list.html",
    "data/!publ_list.md",
    "data/Tsyplenkov-Anatoly_publications.html",
    "data/Tsyplenkov-Anatoly_publications.pdf",
    "data/photos/profile.webp",
    "data/logos/hydrotranslate.png",
    "data/logos/rewriter.png",
    "data/logos/zepter.png",
    "blog/2020-03-03-tidy-tuesday-nhl/figures/plot-1.png",
    "blog/2020-03-03-tidy-tuesday-nhl/figures/boxplot-1.png",
    "blog/2022-03-05-soilgrids-terra/figures/unnamed-chunk-5-1.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/benchmarks.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/NVCleanstall_escFw822lQ.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/WindowsTerminal_kTF31RPuRA.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/benchmarks-1.png",
    "404.html",
    "data/dem.tiff",
    "data/dem.tiff.aux.xml",
    "data/social-logo.svg",
    "data/photos/profile-square.jpg",
)

CANONICAL_HOST = "https://anatolii.nz"
PERSON_ID = f"{CANONICAL_HOST}/#person"
ALLOWED_SAME_AS = {
    "https://github.com/atsyplenkov",
    "https://orcid.org/0000-0003-4144-8402",
    "https://scholar.google.com/citations?user=IcwW-WAAAAAJ&hl=en",
    "https://www.linkedin.com/in/atsyplenkov/",
}

LEGACY_REDIRECTS = {
    "about.html": "/about/",
    "papers.html": "/papers/",
    "talks.html": "/talks/",
    "software.html": "/software/",
    "app.html": "/software/#apps",
    "posts/2020-03-03-tidy-tuesday-nhl/2020-03-03-tidy-tuesday-nhl.html": (
        "/blog/2020-03-03-tidy-tuesday-nhl/"
    ),
    "posts/2022-03-05-soilgrids-terra/2022-03-05-soilgrids-terra.html": (
        "/blog/2022-03-05-soilgrids-terra/"
    ),
    "posts/2024/xgboost-gpu-r.html": "/blog/2024-08-06-xgboost-gpu-r/",
    "posts/anzgg2024.html": "/blog/2024-02-11-anzgg2024/",
}

NON_CANONICAL_HTML = {
    "404.html",
    "data/!publ_list.html",
    "data/Tsyplenkov-Anatoly_publications.html",
    "gey_2022-overview.html",
    "kuban_overview.html",
    "nil.html",
    "nil-points.html",
}

PUBLICATION_CHECKSUM_PATHS = (
    "data/!publ_list.md",
    "data/Tsyplenkov-Anatoly_publications.html",
    "data/Tsyplenkov-Anatoly_publications.pdf",
)

# Byte-preserved legacy downloads that must remain at published paths.
# Note: data/!publ_list.html is required as a useful publication-list format but is
# a simplified static snapshot (not the Quarto-wrapped freeze bytes).
LEGACY_DOWNLOAD_CHECKSUM_PATHS = (
    "data/!publ_list.md",
    "data/Tsyplenkov-Anatoly_CV.pdf",
    "data/Tsyplenkov-Anatoly_publications.html",
    "data/Tsyplenkov-Anatoly_publications.pdf",
    "data/dem.tiff",
    "data/dem.tiff.aux.xml",
    "data/logos/hydrotranslate.png",
    "data/logos/rewriter.png",
    "data/photos/profile-square.jpg",
    "data/photos/profile.webp",
    "data/posters/anzgg2024_caucasus-poster_tsyplenkov.pdf",
    "data/social-logo.svg",
)

EXPECTED_NAV = (
    ("/", "Home"),
    ("/about/", "About"),
    ("/papers/", "Papers"),
    ("/talks/", "Talks"),
    ("/software/", "Software"),
)

STANDALONE_RESEARCH_ENTRY_PAGES = (
    "gey_2022-overview.html",
    "kuban_overview.html",
    "nil.html",
    "nil-points.html",
)


LOCAL_REF_ATTRS = ("href", "src", "poster", "data")
CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.I)
SKIP_SCHEMES = ("http://", "https://", "//", "mailto:", "data:", "javascript:", "tel:")
META_ATTR_RE = re.compile(
    r"<meta\s+([^>]+)>",
    re.I,
)
ATTR_RE = re.compile(r"""([^\s=]+)\s*=\s*(['"])(.*?)\2""", re.I | re.S)


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


def check_standalone_research_preservation(
    report: AuditReport, site_dir: Path, manifests: dict[str, dict]
) -> None:
    """Require every frozen standalone research path with matching checksums."""
    research = manifests.get("standalone-research-manifest.json")
    if not research:
        return

    files = research.get("files") or {}
    entry_pages = research.get("entry_pages") or {}
    if not isinstance(files, dict) or not files:
        report.fail("standalone research manifest has no files to preserve")
        return
    if not isinstance(entry_pages, dict) or not entry_pages:
        report.fail("standalone research manifest has no entry pages to preserve")
        return

    for rel, meta in sorted(files.items()):
        rel = rel.lstrip("/")
        target = site_dir / rel
        expected_sha = meta.get("sha256") if isinstance(meta, dict) else None
        if not target.is_file():
            report.fail(f"standalone research path missing: /{rel}")
            continue
        if not expected_sha:
            report.fail(f"standalone research manifest missing sha256 for: /{rel}")
            continue
        actual_sha = _sha256(target)
        if actual_sha != expected_sha:
            report.fail(
                f"standalone research checksum mismatch for /{rel}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        else:
            report.ok(f"standalone research path ok: /{rel}")

    for entry, meta in sorted(entry_pages.items()):
        entry_rel = entry.lstrip("/")
        deps = meta.get("dependencies") or [] if isinstance(meta, dict) else []
        for dep in deps:
            dep_rel = str(dep).lstrip("/")
            if not (site_dir / dep_rel).is_file():
                report.fail(
                    f"standalone research dependency missing for /{entry_rel}: /{dep_rel}"
                )
            else:
                report.ok(
                    f"standalone research dependency present for /{entry_rel}: /{dep_rel}"
                )


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_publication_preservation(
    report: AuditReport, site_dir: Path, manifests: dict[str, dict]
) -> None:
    """Verify byte-preserved publication formats against the legacy manifest."""
    legacy = manifests.get("legacy-production-manifest.json")
    if not legacy:
        return

    files = legacy.get("files") or {}
    for rel in PUBLICATION_CHECKSUM_PATHS:
        target = site_dir / rel
        expected = files.get(rel) or {}
        expected_sha = expected.get("sha256")
        if not target.is_file():
            report.fail(f"publication preservation path missing: /{rel}")
        elif not expected_sha:
            report.fail(f"legacy manifest missing publication checksum: /{rel}")
        elif _sha256(target) != expected_sha:
            report.fail(f"publication preservation checksum mismatch: /{rel}")
        else:
            report.ok(f"publication preservation path ok: /{rel}")


def check_legacy_download_preservation(
    report: AuditReport, site_dir: Path, manifests: dict[str, dict]
) -> None:
    """Require frozen legacy downloads at their published paths."""
    legacy = manifests.get("legacy-production-manifest.json")
    if not legacy:
        return

    files = legacy.get("files") or {}
    for rel in LEGACY_DOWNLOAD_CHECKSUM_PATHS:
        target = site_dir / rel
        expected = files.get(rel) or {}
        expected_sha = expected.get("sha256")
        if not target.is_file():
            report.fail(f"legacy download missing: /{rel}")
        elif not expected_sha:
            report.fail(f"legacy manifest missing download checksum: /{rel}")
        elif _sha256(target) != expected_sha:
            report.fail(f"legacy download checksum mismatch: /{rel}")
        else:
            report.ok(f"legacy download path ok: /{rel}")


def check_404_page(report: AuditReport, site_dir: Path) -> None:
    """Custom 404 must help navigation and stay non-canonical."""
    path = site_dir / "404.html"
    if not path.is_file():
        report.fail("custom 404 page missing: /404.html")
        return

    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    report.ok("custom 404 page present: /404.html")

    if "noindex" not in lowered:
        report.fail("404 page missing noindex robots directive")
    else:
        report.ok("404 page is non-indexable")

    if 'rel="canonical"' in lowered:
        report.fail("404 page must not declare a canonical URL")
    else:
        report.ok("404 page has no canonical URL")

    for href, label in EXPECTED_NAV:
        if href not in text or label not in text:
            report.fail(f"404 page missing navigation link {label} -> {href}")
        else:
            report.ok(f"404 page links to {label}")

    if "page not found" not in lowered and "not found" not in lowered:
        report.fail("404 page missing not-found messaging")
    else:
        report.ok("404 page explains the missing resource")


def check_final_site_certification(report: AuditReport, site_dir: Path) -> None:
    """Final integration checks across nav, demo absence, and presentation seams."""
    home_path = site_dir / "index.html"
    if not home_path.is_file():
        report.fail("homepage missing for final certification")
        return

    home = home_path.read_text(encoding="utf-8", errors="replace")

    # Exact primary navigation labels/targets on the homepage.
    nav_hrefs = re.findall(
        r'<nav class="site-nav">(.*?)</nav>', home, flags=re.I | re.S
    )
    nav_blob = nav_hrefs[0] if nav_hrefs else home
    nav_links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', nav_blob)
    expected_links = list(EXPECTED_NAV)
    if nav_links != expected_links:
        report.fail(
            "homepage navigation is not exactly Home/About/Papers/Talks/Software: "
            f"got {nav_links!r}"
        )
    else:
        report.ok("homepage navigation is exactly Home/About/Papers/Talks/Software")

    demo_markers = (
        ("Ciallo", "Ciallo"),
        ("tufted-blog.pages.dev", "tufted-blog.pages.dev"),
        ("/docs/", "/docs/"),
        (">Docs</a>", "Docs nav item"),
        ('href="/cv/"', "/cv/"),
        ('href="/app/"', "/app/"),
    )
    for needle, label in demo_markers:
        if needle in home:
            report.fail(f"homepage still exposes demo/template surface: {label}")
        else:
            report.ok(f"homepage free of demo marker: {label}")

    # Homepage post links must be dated canonical blog URLs only.
    post_links = re.findall(r'href="(/blog/[^"]+)"', home)
    if not post_links:
        report.fail("homepage has no blog post links")
    else:
        bad = [link for link in post_links if not re.fullmatch(r"/blog/\d{4}-\d{2}-\d{2}-[^/]+/", link)]
        if bad:
            report.fail(f"homepage has non-canonical blog links: {bad[:3]}")
        else:
            report.ok("homepage blog links use dated canonical URLs")

    # Presentation smoke checks used by the certification review.
    if 'name="viewport"' not in home:
        report.fail("homepage missing responsive viewport meta")
    else:
        report.ok("homepage includes responsive viewport meta")

    if "theme-toggle" not in home or "/assets/theme-toggle.js" not in home:
        report.fail("homepage missing theme switching controls")
    else:
        report.ok("homepage includes theme switching controls")

    post = site_dir / "blog/2020-03-03-tidy-tuesday-nhl/index.html"
    if post.is_file():
        post_html = post.read_text(encoding="utf-8", errors="replace")
        if "<pre" not in post_html or "<code" not in post_html:
            report.fail("blog post missing code blocks for presentation review")
        else:
            report.ok("blog post includes code blocks")
        if ".png" not in post_html and "<img" not in post_html:
            report.fail("blog post missing figures for presentation review")
        else:
            report.ok("blog post includes figures")

    talks = site_dir / "talks/index.html"
    if talks.is_file():
        talks_html = talks.read_text(encoding="utf-8", errors="replace")
        if "<video" not in talks_html and "youtube.com/embed" not in talks_html:
            report.fail("Talks page missing embedded media for presentation review")
        else:
            report.ok("Talks page includes embedded media")

    about = site_dir / "about/index.html"
    if about.is_file():
        about_html = about.read_text(encoding="utf-8", errors="replace")
        if "/data/Tsyplenkov-Anatoly_CV.pdf" not in about_html:
            report.fail("About page missing CV PDF link")
        else:
            report.ok("About page links to CV PDF")

    anzgg = site_dir / "blog/2024-02-11-anzgg2024/index.html"
    if anzgg.is_file():
        anzgg_html = anzgg.read_text(encoding="utf-8", errors="replace")
        if "Harmel" not in anzgg_html and "reference" not in anzgg_html.lower():
            report.fail("ANZGG post missing citations for presentation review")
        else:
            report.ok("ANZGG post includes citations")


def _parse_attrs(attr_text: str) -> dict[str, str]:
    return {m.group(1).lower(): m.group(3) for m in ATTR_RE.finditer(attr_text)}


def extract_page_signals(html_text: str) -> dict:
    """Pull metadata and JSON-LD signals from a generated HTML document."""
    title_match = re.search(r"<title>(.*?)</title>", html_text, re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""

    metas: dict[str, str] = {}
    for meta in META_ATTR_RE.finditer(html_text):
        attrs = _parse_attrs(meta.group(1))
        key = attrs.get("name") or attrs.get("property")
        if key and "content" in attrs:
            metas[key.lower()] = attrs["content"]

    canonical = None
    for link in re.finditer(r"<link\s+([^>]+)>", html_text, re.I):
        attrs = _parse_attrs(link.group(1))
        if attrs.get("rel", "").lower() == "canonical":
            canonical = attrs.get("href")

    lang_match = re.search(r"<html[^>]*\blang=['\"]([^'\"]+)['\"]", html_text, re.I)
    lang = lang_match.group(1) if lang_match else ""

    json_ld_blocks = []
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.I | re.S,
    ):
        raw = match.group(1).strip()
        try:
            json_ld_blocks.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            json_ld_blocks.append({"__error__": str(exc), "__raw__": raw[:200]})

    return {
        "title": title,
        "metas": metas,
        "canonical": canonical,
        "lang": lang,
        "json_ld": json_ld_blocks,
        "text": html_text,
    }


def _graph_nodes(blocks: list) -> list[dict]:
    nodes: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if "@graph" in block and isinstance(block["@graph"], list):
            nodes.extend(item for item in block["@graph"] if isinstance(item, dict))
        else:
            nodes.append(block)
    return nodes


def _find_type(nodes: list[dict], type_name: str) -> dict | None:
    for node in nodes:
        value = node.get("@type")
        if value == type_name:
            return node
        if isinstance(value, list) and type_name in value:
            return node
    return None


def check_page_contract(
    report: AuditReport,
    *,
    site_dir: Path,
    rel_path: str,
    expected_type: str,
    expected_canonical: str,
) -> None:
    path = site_dir / rel_path
    if not path.is_file():
        report.fail(f"missing page for contract check: /{rel_path}")
        return

    signals = extract_page_signals(path.read_text(encoding="utf-8", errors="replace"))
    if not signals["title"]:
        report.fail(f"missing title: /{rel_path}")
    else:
        report.ok(f"title present: /{rel_path}")

    desc = signals["metas"].get("description")
    if not desc:
        report.fail(f"missing description: /{rel_path}")
    else:
        report.ok(f"description present: /{rel_path}")

    if signals["lang"].lower() != "en":
        report.fail(f"expected lang=en on /{rel_path}, got {signals['lang']!r}")
    else:
        report.ok(f"lang=en: /{rel_path}")

    if signals["canonical"] != expected_canonical:
        report.fail(
            f"canonical mismatch on /{rel_path}: "
            f"expected {expected_canonical}, got {signals['canonical']!r}"
        )
    else:
        report.ok(f"canonical ok: /{rel_path}")

    for key in ("og:title", "og:type", "og:url", "og:description", "og:site_name", "twitter:card"):
        if key not in signals["metas"] or not signals["metas"][key]:
            report.fail(f"missing {key} on /{rel_path}")
        else:
            report.ok(f"{key} present: /{rel_path}")

    og_image = signals["metas"].get("og:image")
    if not og_image or not og_image.startswith("https://"):
        report.fail(f"missing absolute og:image on /{rel_path}")
    else:
        report.ok(f"absolute og:image: /{rel_path}")

    if "og:image:alt" not in signals["metas"] and "twitter:image:alt" not in signals["metas"]:
        report.fail(f"missing social image alt on /{rel_path}")
    else:
        report.ok(f"social image alt present: /{rel_path}")

    if "giscus" in signals["text"].lower():
        report.fail(f"giscus/comment integration present on /{rel_path}")
    else:
        report.ok(f"no giscus on /{rel_path}")

    if any(isinstance(block, dict) and "__error__" in block for block in signals["json_ld"]):
        report.fail(f"invalid JSON-LD on /{rel_path}")
        return
    if not signals["json_ld"]:
        report.fail(f"missing JSON-LD on /{rel_path}")
        return

    nodes = _graph_nodes(signals["json_ld"])
    typed = _find_type(nodes, expected_type)
    if typed is None:
        report.fail(f"JSON-LD missing @{expected_type} on /{rel_path}")
    else:
        report.ok(f"JSON-LD {expected_type} present: /{rel_path}")

    person = _find_type(nodes, "Person")
    if person is None:
        report.fail(f"JSON-LD missing Person on /{rel_path}")
        return

    if person.get("@id") != PERSON_ID:
        report.fail(f"Person @id mismatch on /{rel_path}: {person.get('@id')!r}")
    else:
        report.ok(f"stable Person @id: /{rel_path}")

    same_as = person.get("sameAs") or []
    if not isinstance(same_as, list):
        report.fail(f"Person sameAs is not a list on /{rel_path}")
        return
    same_set = set(same_as)
    if same_set != ALLOWED_SAME_AS:
        report.fail(
            f"Person sameAs mismatch on /{rel_path}: expected {sorted(ALLOWED_SAME_AS)}, got {sorted(same_set)}"
        )
    else:
        report.ok(f"Person sameAs ok: /{rel_path}")

    if expected_type == "BlogPosting":
        for field in ("headline", "datePublished", "author", "publisher"):
            if field not in typed:
                report.fail(f"BlogPosting missing {field} on /{rel_path}")
            else:
                report.ok(f"BlogPosting {field} present: /{rel_path}")
    if expected_type == "ProfilePage" and "mainEntity" not in (typed or {}):
        report.fail(f"ProfilePage missing mainEntity on /{rel_path}")
    elif expected_type == "ProfilePage":
        report.ok(f"ProfilePage mainEntity present: /{rel_path}")


def check_tracer_metadata(report: AuditReport, site_dir: Path) -> None:
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="index.html",
        expected_type="Blog",
        expected_canonical=f"{CANONICAL_HOST}/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="about/index.html",
        expected_type="ProfilePage",
        expected_canonical=f"{CANONICAL_HOST}/about/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="papers/index.html",
        expected_type="WebPage",
        expected_canonical=f"{CANONICAL_HOST}/papers/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="talks/index.html",
        expected_type="WebPage",
        expected_canonical=f"{CANONICAL_HOST}/talks/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="software/index.html",
        expected_type="WebPage",
        expected_canonical=f"{CANONICAL_HOST}/software/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="blog/2020-03-03-tidy-tuesday-nhl/index.html",
        expected_type="BlogPosting",
        expected_canonical=f"{CANONICAL_HOST}/blog/2020-03-03-tidy-tuesday-nhl/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="blog/2022-03-05-soilgrids-terra/index.html",
        expected_type="BlogPosting",
        expected_canonical=f"{CANONICAL_HOST}/blog/2022-03-05-soilgrids-terra/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="blog/2024-08-06-xgboost-gpu-r/index.html",
        expected_type="BlogPosting",
        expected_canonical=f"{CANONICAL_HOST}/blog/2024-08-06-xgboost-gpu-r/",
    )
    check_page_contract(
        report,
        site_dir=site_dir,
        rel_path="blog/2024-02-11-anzgg2024/index.html",
        expected_type="BlogPosting",
        expected_canonical=f"{CANONICAL_HOST}/blog/2024-02-11-anzgg2024/",
    )

    home_path = site_dir / "index.html"
    if home_path.is_file():
        home = home_path.read_text(encoding="utf-8", errors="replace")
        if "Tidy Tuesday NHL" not in home:
            report.fail("homepage blog index missing Tidy Tuesday entry")
        else:
            report.ok("homepage lists Tidy Tuesday post")
        if "Accessing SoilGrids" not in home:
            report.fail("homepage blog index missing SoilGrids entry")
        else:
            report.ok("homepage lists SoilGrids post")
        if "Accelerating XGBoost with GPU in R" not in home:
            report.fail("homepage blog index missing XGBoost entry")
        else:
            report.ok("homepage lists XGBoost post")
        if "Supplementary material to poster presentation @ ANZGG 2024" not in home:
            report.fail("homepage blog index missing ANZGG 2024 entry")
        else:
            report.ok("homepage lists ANZGG 2024 post")
        soil_index = home.find("Accessing SoilGrids")
        tidy_index = home.find("Tidy Tuesday NHL")
        xgboost_index = home.find("Accelerating XGBoost with GPU in R")
        anzgg_index = home.find("Supplementary material to poster presentation @ ANZGG 2024")
        if (
            anzgg_index == -1
            or xgboost_index == -1
            or soil_index == -1
            or tidy_index == -1
            or not xgboost_index < anzgg_index < soil_index < tidy_index
        ):
            report.fail("homepage blog entries are not reverse chronological")
        else:
            report.ok("homepage blog entries are reverse chronological")
        # Demo identity markers only — upstream MIT attribution may still name the template repo.
        if "Ciallo" in home or "tufted-blog.pages.dev" in home:
            report.fail("homepage still contains template demo identity")
        else:
            report.ok("homepage identity is personalized")

    about_path = site_dir / "about/index.html"
    if about_path.is_file():
        about = about_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "Manaaki Whenua Landcare Research",
            "/data/Tsyplenkov-Anatoly_CV.pdf",
            "orcid.org/0000-0003-4144-8402",
            "CC BY-SA 4.0",
        ):
            if needle not in about:
                report.fail(f"about page missing expected content: {needle}")
            else:
                report.ok(f"about page contains {needle}")

    papers_path = site_dir / "papers/index.html"
    if papers_path.is_file():
        papers = papers_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "selected peer-reviewed publications",
            "Google Scholar",
            "ORCID",
            "WoS",
            "stats as of 07 November 2024",
            "54 scientific papers",
            "254 citations",
            "h-index: 9",
            "Flash Floods on the Northern Coast of the Black Sea",
            "Ecological Revitalization Master Plan of Lipetsk City",
            "Assessment of Basin Component of Suspended Sediment Yield",
            "/data/Tsyplenkov-Anatoly_publications.pdf",
            "/data/!publ_list.md",
            "/data/!publ_list.html",
            "/data/Tsyplenkov-Anatoly_publications.html",
        ):
            if needle not in papers:
                report.fail(f"Papers page missing expected content: {needle}")
            else:
                report.ok(f"Papers page contains {needle}")

        if "migration in progress" in papers.lower():
            report.fail("Papers page still describes the migration as incomplete")
        else:
            report.ok("Papers page is presented as a completed static snapshot")

    talks_path = site_dir / "talks/index.html"
    if talks_path.is_file():
        talks = talks_path.read_text(encoding="utf-8", errors="replace")
        expected_description = (
            "Invited talks and workshops by Anatoly Tsyplenkov on landslide "
            "connectivity, sediment delivery, and soil erosion modeling in R."
        )
        signals = extract_page_signals(talks)
        if signals["metas"].get("description") != expected_description:
            report.fail("Talks page description is not the reviewed concise description")
        else:
            report.ok("Talks page has the reviewed concise description")

        nodes = _graph_nodes(signals["json_ld"])
        webpage = _find_type(nodes, "WebPage")
        if webpage is None or webpage.get("description") != expected_description:
            report.fail("Talks JSON-LD description disagrees with page metadata")
        else:
            report.ok("Talks JSON-LD description matches page metadata")

        for needle in (
            "IAG Webinar Oceania 2024",
            "5 March 2024",
            "http://www.geomorph.org/international-geomorphology-week-2024/",
            "Data-driven insights on shallow landslide connectivity and sediment delivery to streams",
            "https://storage.yandexcloud.net/iag-talk/iag2024_talk_x264.mp4",
            "MEGAPOLIS 2022",
            "6 December 2022",
            "https://megapolis2022.netlify.app/",
            "Soil erosion modeling in R",
            "https://www.youtube.com/embed/B2ian7Gmodc",
            "https://www.youtube.com/watch?v=B2ian7Gmodc",
            "<video ",
            "<source ",
            "controls=\"controls\"",
            "<iframe ",
            "loading=\"lazy\"",
            "talk-media",
            "talk-media-fallback",
            "allowfullscreen",
        ):
            if needle not in talks:
                report.fail(f"Talks page missing expected content: {needle}")
            else:
                report.ok(f"Talks page contains {needle}")

        talks_css_path = site_dir / "assets/custom.css"
        if not talks_css_path.is_file():
            report.fail("Talks responsive media CSS missing: assets/custom.css")
        else:
            talks_css = talks_css_path.read_text(encoding="utf-8", errors="replace")
            for needle in (".talk-media", "max-width: 100%", "aspect-ratio"):
                if needle not in talks_css:
                    report.fail(f"Talks responsive media CSS missing: {needle}")
                else:
                    report.ok(f"Talks responsive media CSS contains {needle}")

    post_path = site_dir / "blog/2020-03-03-tidy-tuesday-nhl/index.html"
    if post_path.is_file():
        post = post_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "top_250",
            "figures/plot-1.png",
            "figures/boxplot-1.png",
            "tidytuesday",
            "2020-03-03",
        ):
            if needle not in post:
                report.fail(f"Tidy Tuesday post missing expected content: {needle}")
            else:
                report.ok(f"Tidy Tuesday post contains {needle}")

    soil_path = site_dir / "blog/2022-03-05-soilgrids-terra/index.html"
    if soil_path.is_file():
        soil = soil_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "Accessing SoilGrids via",
            "Boundary layer",
            "Download urls",
            "soilgrids_download",
            "files.isric.org/soilgrids",
            "figures/unnamed-chunk-5-1.png",
            "soil erosion",
            "2022-03-05",
        ):
            if needle not in soil:
                report.fail(f"SoilGrids post missing expected content: {needle}")
            else:
                report.ok(f"SoilGrids post contains {needle}")

    xgboost_path = site_dir / "blog/2024-08-06-xgboost-gpu-r/index.html"
    if xgboost_path.is_file():
        xgboost = xgboost_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "Accelerating XGBoost with GPU in R",
            "TL;DR",
            "What is XGBoost?",
            "Installation instructions",
            "Testing GPU support",
            "BONUS: Kaggle",
            "xgboost_url",
            "xgb.DMatrix",
            "gpu_accelerated.R",
            "≈6x speed increase",
            "xgboost.readthedocs.io",
            "kaggle.com/code/anatoliitsyplenkov/gpu-accelerated-xgboost-in-r",
            "figures/benchmarks.png",
            "figures/NVCleanstall_escFw822lQ.png",
            "figures/WindowsTerminal_kTF31RPuRA.png",
            "figures/benchmarks-1.png",
            "2024-08-06",
            "gpu",
            "xgboost",
        ):
            if needle not in xgboost:
                report.fail(f"XGBoost post missing expected content: {needle}")
            else:
                report.ok(f"XGBoost post contains {needle}")

    anzgg_path = site_dir / "blog/2024-02-11-anzgg2024/index.html"
    if anzgg_path.is_file():
        anzgg = anzgg_path.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "Supplementary material to poster presentation @ ANZGG 2024",
            "Insights into spatial and temporal changes in suspended sediment yield in the Caucasus Mountains during the Anthropocene",
            "Hello World!",
            "BTW",
            "Download Poster",
            "/data/posters/anzgg2024_caucasus-poster_tsyplenkov.pdf",
            "/posts/anzgg2024_caucasus-poster_tsyplenkov.png",
            "caucasus-sediment-yield",
            "caucasus-sediment-yield2021",
            "sediment-caucasus-anthropocene",
            "Harmel",
            "Steegen",
            "Vanmaercke",
            "Williams",
            "10.1002/hyp.14403",
            "10.3390/w13223173",
            "10.5194/piahs-381-87-2019",
            "2024-02-11",
            "academia",
        ):
            if needle not in anzgg:
                report.fail(f"ANZGG post missing expected content: {needle}")
            else:
                report.ok(f"ANZGG post contains {needle}")


def check_redirects(report: AuditReport, site_dir: Path) -> None:
    for rel, target in LEGACY_REDIRECTS.items():
        path = site_dir / rel
        if not path.is_file():
            report.fail(f"missing redirect document: /{rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if 'http-equiv="refresh"' not in lowered:
            report.fail(f"redirect missing meta refresh: /{rel}")
        else:
            report.ok(f"redirect has meta refresh: /{rel}")
        if "noindex" not in lowered:
            report.fail(f"redirect missing noindex: /{rel}")
        else:
            report.ok(f"redirect is noindex: /{rel}")
        if f'href="{target}"' not in text and f"href='{target}'" not in text:
            report.fail(f"redirect missing visible fallback to {target}: /{rel}")
        else:
            report.ok(f"redirect fallback link ok: /{rel}")
        if f'href="{CANONICAL_HOST}{target}"' not in text and f'href="{target}"' not in text:
            # canonical may be absolute
            if f'rel="canonical"' not in lowered:
                report.fail(f"redirect missing canonical: /{rel}")
            else:
                report.ok(f"redirect canonical present: /{rel}")
        else:
            report.ok(f"redirect target referenced: /{rel}")


def check_software_content(report: AuditReport, site_dir: Path) -> None:
    software_path = site_dir / "software/index.html"
    if not software_path.is_file():
        return

    software = software_path.read_text(encoding="utf-8", errors="replace")
    software_text = unescape(software)
    expected_description = (
        "Software projects, web apps, editor extensions, and R packages by Anatoly "
        "Tsyplenkov, including hydrological tools and research software."
    )
    signals = extract_page_signals(software)
    if signals["metas"].get("description") != expected_description:
        report.fail("Software page does not use the reviewed concise description")
    else:
        report.ok("Software page has the reviewed concise description")

    required_content = (
        "Web Apps & VS Code extensions",
        "pastum",
        "VS Code extension for inserting text tables as dataframe objects into the editor",
        "detect-chatgpt",
        "Experimental app for detecting excessive word usage by ChatGPT",
        "bibtex2html",
        "App for converting bibliography references to BibTeX format",
        "hydrotranslate",
        "Russian-English dictionary of hydrological terms",
        "JavaScript",
        "Python",
        "Streamlit",
        "Py-Shiny",
        "R-Shiny",
        "Packages",
        "centerline",
        "Centerline extraction and plotting for closed geometries",
        "tidyhydro",
        "C++ boosted commonly used hydrological metrics for",
        "tidymodels",
        "framework",
        "loadflux",
        "Tools for turbidity and event sediment transport analysis",
        "rusleR",
        "Soil erosion estimation based on the RUSLE model",
        "rp5pik",
        "Access meteorological data from pogodaiklimat.ru",
        "tgme",
        "Send messages to Telegram from R",
        "HBVr",
        "Access HBV model parameters dataset from Beck et al. (2021)",
        "Apps",
        "Below is a list of a",
        "Shiny",
        "atsyplenkov.pp.ru",
        "Hydrotranslate",
        "English-Russian and Russian-English translator of hydrological terms and definitions.",
        "DScn. Sergey Chalov",
        "Dr. Vsevolod Moreydo",
        "Zepter",
        "currency conversion",
        "MIR payment system",
        "up-to-date exchange rates",
        "Rewriter",
        "paraphrasing",
        "Sber model",
        "same meaning",
        "Launch App",
        "Github",
    )
    for needle in required_content:
        if needle not in software_text:
            report.fail(f"Software page missing expected content: {needle}")
        else:
            report.ok(f"Software page contains {needle}")

    project_links = (
        "https://github.com/atsyplenkov/pastum",
        "https://github.com/atsyplenkov/detect-chatgpt",
        "https://github.com/atsyplenkov/bibtex2html",
        "https://github.com/atsyplenkov/hydrotranslate",
        "https://github.com/atsyplenkov/centerline",
        "https://github.com/atsyplenkov/tidyhydro",
        "https://github.com/atsyplenkov/loadflux",
        "https://github.com/atsyplenkov/rusleR",
        "https://github.com/atsyplenkov/rp5pik",
        "https://github.com/atsyplenkov/tgme",
        "https://github.com/atsyplenkov/HBVr",
        "https://hydrotranslate.ru/",
        "https://github.com/atsyplenkov/shiny-server/tree/master/zepter",
        "https://atsyplenkov.pp.ru/shiny/zepter",
        "https://sbercloud.ru/ru/datahub/rugpt3family/demo-rewrite",
        "https://atsyplenkov.pp.ru/shiny/sber",
        "https://github.com/atsyplenkov/shiny-server/tree/master/sber",
    )
    for link in project_links:
        if link not in software_text:
            report.fail(f"Software page missing project link: {link}")
        else:
            report.ok(f"Software page contains project link: {link}")

    version_badges = (
        "img.shields.io/github/r-package/v/atsyplenkov/centerline",
        "img.shields.io/github/r-package/v/atsyplenkov/tidyhydro",
        "img.shields.io/github/r-package/v/atsyplenkov/loadflux",
        "img.shields.io/github/r-package/v/atsyplenkov/rusleR",
        "img.shields.io/github/r-package/v/atsyplenkov/rp5pik",
        "img.shields.io/github/r-package/v/atsyplenkov/tgme",
        "img.shields.io/github/r-package/v/atsyplenkov/HBVr",
    )
    for badge in version_badges:
        if badge not in software_text:
            report.fail(f"Software page missing version badge: {badge}")
        else:
            report.ok(f"Software page contains version badge: {badge}")

    if 'id="apps"' not in software:
        report.fail("Software page Apps section is not addressable as #apps")
    else:
        report.ok("Software page Apps section is addressable as #apps")

    css_path = site_dir / "assets/custom.css"
    if not css_path.is_file():
        report.fail("Software responsive CSS missing: assets/custom.css")
    else:
        css = css_path.read_text(encoding="utf-8", errors="replace")
        for needle in (".software-grid", ".software-card", "grid-template-columns", "@media"):
            if needle not in css:
                report.fail(f"Software responsive CSS missing: {needle}")
            else:
                report.ok(f"Software responsive CSS contains {needle}")


def check_discoverability(report: AuditReport, site_dir: Path) -> None:
    robots = site_dir / "robots.txt"
    if robots.is_file():
        text = robots.read_text(encoding="utf-8", errors="replace")
        if "Disallow: /" in text and "Allow: /" not in text:
            report.fail("robots.txt disallows crawling")
        elif "Allow: /" not in text and "Disallow:" not in text:
            report.ok("robots.txt present")
        else:
            if "Sitemap:" not in text or "anatolii.nz/sitemap.xml" not in text:
                report.fail("robots.txt missing canonical sitemap reference")
            else:
                report.ok("robots.txt allows crawl and references sitemap")
    else:
        report.fail("robots.txt missing")

    sitemap = site_dir / "sitemap.xml"
    feed = site_dir / "feed.xml"
    llms = site_dir / "llms.txt"
    legacy_paths = tuple(LEGACY_REDIRECTS)

    if sitemap.is_file():
        sm = sitemap.read_text(encoding="utf-8", errors="replace")
        try:
            root = ET.fromstring(sm)
        except ET.ParseError as exc:
            report.fail(f"sitemap.xml unparseable: {exc}")
            root = None
        if root is not None:
            locs = [el.text or "" for el in root.iter() if el.tag.endswith("loc")]
            if not any(loc.rstrip("/") == CANONICAL_HOST for loc in locs) and not any(
                loc == f"{CANONICAL_HOST}/" for loc in locs
            ):
                report.fail("sitemap missing homepage canonical URL")
            else:
                report.ok("sitemap includes homepage")
            if not any("/papers/" in loc for loc in locs):
                report.fail("sitemap missing Papers canonical URL")
            else:
                report.ok("sitemap includes Papers page")
            if not any("/talks/" in loc for loc in locs):
                report.fail("sitemap missing Talks canonical URL")
            else:
                report.ok("sitemap includes Talks page")
            if not any("/software/" in loc for loc in locs):
                report.fail("sitemap missing Software canonical URL")
            else:
                report.ok("sitemap includes Software page")
            if any(f"/{path}" in loc for loc in locs for path in NON_CANONICAL_HTML):
                report.fail("sitemap includes non-canonical HTML paths")
            else:
                report.ok("sitemap excludes non-canonical HTML paths")
            if any(
                entry in loc or entry.removesuffix(".html") in loc
                for loc in locs
                for entry in STANDALONE_RESEARCH_ENTRY_PAGES
            ):
                report.fail("sitemap includes standalone research outputs")
            else:
                report.ok("sitemap excludes standalone research outputs")
            if any("404" in loc for loc in locs):
                report.fail("sitemap includes 404 page")
            else:
                report.ok("sitemap excludes 404 page")
            if not any("/blog/2020-03-03-tidy-tuesday-nhl/" in loc for loc in locs):
                report.fail("sitemap missing Tidy Tuesday canonical URL")
            else:
                report.ok("sitemap includes Tidy Tuesday post")
            if not any("/blog/2022-03-05-soilgrids-terra/" in loc for loc in locs):
                report.fail("sitemap missing SoilGrids canonical URL")
            else:
                report.ok("sitemap includes SoilGrids post")
            if not any("/blog/2024-08-06-xgboost-gpu-r/" in loc for loc in locs):
                report.fail("sitemap missing XGBoost canonical URL")
            else:
                report.ok("sitemap includes XGBoost post")
            if not any("/blog/2024-02-11-anzgg2024/" in loc for loc in locs):
                report.fail("sitemap missing ANZGG canonical URL")
            else:
                report.ok("sitemap includes ANZGG post")
            if any(legacy_path in loc for loc in locs for legacy_path in legacy_paths):
                report.fail("sitemap includes redirect/legacy URLs")
            else:
                report.ok("sitemap excludes redirect URLs")
            if any("tufted-blog.pages.dev" in loc for loc in locs):
                report.fail("sitemap references demo host")
            else:
                report.ok("sitemap host is canonical")

    if feed.is_file():
        fx = feed.read_text(encoding="utf-8", errors="replace")
        try:
            root = ET.fromstring(fx)
        except ET.ParseError as exc:
            report.fail(f"feed.xml unparseable: {exc}")
            root = None
        if root is not None:
            links = [el.text or "" for el in root.iter() if el.tag.endswith("link")]
            titles = [el.text or "" for el in root.iter() if el.tag.endswith("title")]
            if not any("Tidy Tuesday NHL" in t for t in titles):
                report.fail("RSS missing Tidy Tuesday item")
            else:
                report.ok("RSS includes Tidy Tuesday item")
            if not any("Accessing SoilGrids via" in t for t in titles):
                report.fail("RSS missing SoilGrids item")
            else:
                report.ok("RSS includes SoilGrids item")
            if any(legacy_path in link for link in links for legacy_path in legacy_paths):
                report.fail("RSS includes redirect/legacy URLs")
            else:
                report.ok("RSS excludes redirect URLs")
            if not any("Accelerating XGBoost with GPU in R" in t for t in titles):
                report.fail("RSS missing XGBoost item")
            else:
                report.ok("RSS includes XGBoost item")
            if not any("Supplementary material to poster presentation @ ANZGG 2024" in t for t in titles):
                report.fail("RSS missing ANZGG item")
            else:
                report.ok("RSS includes ANZGG item")
            if any(
                entry in link or entry.removesuffix(".html") in link
                for link in links
                for entry in STANDALONE_RESEARCH_ENTRY_PAGES
            ):
                report.fail("RSS includes standalone research outputs")
            else:
                report.ok("RSS excludes standalone research outputs")
            if any("tufted-blog.pages.dev" in link for link in links):
                report.fail("RSS references demo host")
            else:
                report.ok("RSS host is canonical")

    if llms.is_file():
        text = llms.read_text(encoding="utf-8", errors="replace")
        for needle in (
            f"{CANONICAL_HOST}/about/",
            f"{CANONICAL_HOST}/papers/",
            f"{CANONICAL_HOST}/talks/",
            f"{CANONICAL_HOST}/software/",
            f"{CANONICAL_HOST}/blog/2020-03-03-tidy-tuesday-nhl/",
            f"{CANONICAL_HOST}/blog/2022-03-05-soilgrids-terra/",
            f"{CANONICAL_HOST}/blog/2024-08-06-xgboost-gpu-r/",
            f"{CANONICAL_HOST}/blog/2024-02-11-anzgg2024/",
            "Anatoly Tsyplenkov",
        ):
            if needle not in text:
                report.fail(f"llms.txt missing {needle}")
            else:
                report.ok(f"llms.txt contains {needle}")
        if any(legacy_path in text for legacy_path in legacy_paths):
            report.fail("llms.txt advertises redirect/legacy URLs")
        else:
            report.ok("llms.txt advertises only canonical URLs")
        if "Talks and media (migration in progress)" in text:
            report.fail("llms.txt still describes Talks as incomplete")
        else:
            report.ok("llms.txt describes Talks as migrated")
        if any(
            entry in text or f"/{entry.removesuffix('.html')}" in text
            for entry in STANDALONE_RESEARCH_ENTRY_PAGES
        ):
            report.fail("llms.txt advertises standalone research outputs")
        else:
            report.ok("llms.txt excludes standalone research outputs")
    else:
        report.fail("llms.txt missing")

    home = site_dir / "index.html"
    if home.is_file():
        home_text = home.read_text(encoding="utf-8", errors="replace")
        if any(
            entry in home_text or f"/{entry.removesuffix('.html')}/" in home_text
            for entry in STANDALONE_RESEARCH_ENTRY_PAGES
        ):
            report.fail("homepage navigation/content links to standalone research outputs")
        else:
            report.ok("homepage excludes standalone research outputs from main site content")


def check_license_notices(report: AuditReport, site_dir: Path) -> None:
    home = site_dir / "index.html"
    if home.is_file():
        text = home.read_text(encoding="utf-8", errors="replace")
        if "CC BY-SA 4.0" not in text:
            report.fail("homepage footer missing CC BY-SA 4.0 content notice")
        else:
            report.ok("homepage includes CC BY-SA content notice")
        if "MIT" not in text and "Tufted" not in text:
            report.fail("homepage footer missing upstream template notice")
        else:
            report.ok("homepage includes template attribution")

    license_file = REPO_ROOT / "LICENSE"
    if license_file.is_file() and "MIT License" in license_file.read_text(encoding="utf-8"):
        report.ok("repository retains MIT license for template code")
    else:
        report.fail("repository MIT license missing")


def audit_site(site_dir: Path, freeze_dir: Path = FREEZE_DIR) -> AuditReport:
    report = AuditReport()
    manifests = check_manifests(report, freeze_dir)
    check_required_build_paths(report, site_dir)
    if site_dir.is_dir():
        check_html_and_links(report, site_dir)
        check_assets_from_css(report, site_dir)
        check_xml_files(report, site_dir)
        check_standalone_research_preservation(report, site_dir, manifests)
        check_publication_preservation(report, site_dir, manifests)
        check_legacy_download_preservation(report, site_dir, manifests)
        check_404_page(report, site_dir)
        check_tracer_metadata(report, site_dir)
        check_software_content(report, site_dir)
        check_redirects(report, site_dir)
        check_discoverability(report, site_dir)
        check_final_site_certification(report, site_dir)
        check_license_notices(report, site_dir)
    return report


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_self_test() -> int:
    """Prove the audit fails on controlled malformed or incomplete artifacts."""
    import hashlib

    failures: list[str] = []

    def expect_fail(label: str, site_dir: Path, freeze_dir: Path) -> None:
        report = audit_site(site_dir, freeze_dir=freeze_dir)
        if not report.failures:
            failures.append(f"{label}: expected audit failure, got success")
        else:
            print(f"  self-test ok (failed as expected): {label} -> {report.failures[0]}")

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

        base_site = tmp_path / "base_site"
        _write(base_site / "index.html", "<!doctype html><html lang='en'><body>hi</body></html>")
        _write(base_site / "robots.txt", "User-agent: *\nAllow: /\n")
        _write(
            base_site / "sitemap.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{CANONICAL_HOST}/</loc></url></urlset>",
        )
        _write(
            base_site / "feed.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<rss version='2.0'><channel><title>t</title>"
            f"<link>{CANONICAL_HOST}/</link></channel></rss>",
        )

        # Incomplete tracer site must fail required-path checks.
        expect_fail("incomplete tracer site", base_site, freeze)

        broken_link = tmp_path / "broken_link"
        shutil.copytree(base_site, broken_link)
        _write(
            broken_link / "index.html",
            "<!doctype html><html><body><a href='/missing-page/'>x</a></body></html>",
        )
        expect_fail("broken local link", broken_link, freeze)

        bad_xml = tmp_path / "bad_xml"
        shutil.copytree(base_site, bad_xml)
        _write(bad_xml / "feed.xml", "<rss><channel>no close")
        expect_fail("malformed feed.xml", bad_xml, freeze)

        incomplete_freeze = tmp_path / "incomplete_freeze"
        shutil.copytree(freeze, incomplete_freeze)
        (incomplete_freeze / "baseline.json").unlink()
        expect_fail("missing baseline manifest", base_site, incomplete_freeze)

        preserved = tmp_path / "preserved"
        shutil.copytree(base_site, preserved)
        _write(preserved / "research.html", research_html)
        expect_fail("research entry without dependency", preserved, freeze)

        # Production-shaped site missing frozen research paths must fail.
        complete_without_research = tmp_path / "complete_without_research"
        shutil.copytree(base_site, complete_without_research)
        for rel in REQUIRED_BUILD_PATHS:
            target = complete_without_research / rel
            if target.exists():
                continue
            if rel.endswith((".png", ".webp", ".pdf", ".jpg", ".jpeg", ".gif", ".woff")):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x")
            else:
                _write(
                    target,
                    "<!doctype html><html lang='en'><head><title>x</title></head>"
                    "<body>x</body></html>",
                )
        expect_fail("complete site missing standalone research", complete_without_research, freeze)

        bad_research_freeze = tmp_path / "bad_research_freeze"
        shutil.copytree(freeze, bad_research_freeze)
        research = json.loads(
            (bad_research_freeze / "standalone-research-manifest.json").read_text(encoding="utf-8")
        )
        research["files"]["research.css"]["live_reachable"] = False
        _write(bad_research_freeze / "standalone-research-manifest.json", json.dumps(research))
        expect_fail("research manifest unreachable path", base_site, bad_research_freeze)

        # Missing JSON-LD / social metadata on an otherwise present homepage.
        no_jsonld = tmp_path / "no_jsonld"
        shutil.copytree(base_site, no_jsonld)
        for rel in REQUIRED_BUILD_PATHS:
            target = no_jsonld / rel
            if not target.exists():
                if rel.endswith(".png") or rel.endswith(".webp") or rel.endswith(".pdf") or rel.endswith(".jpg"):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"x")
                else:
                    _write(target, "<!doctype html><html lang='en'><head><title>x</title></head><body>x</body></html>")
        expect_fail("missing structured metadata", no_jsonld, freeze)

    if failures:
        print("self-test failures:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("self-test passed: audit fails on controlled malformed artifacts")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  uv run scripts/audit_site.py\n"
            "  uv run scripts/audit_site.py --site _site\n"
            "  uv run scripts/audit_site.py --site /tmp/pages-mirror\n"
            "  uv run scripts/audit_site.py --self-test\n"
            "\n"
            "Staging (after root Pages deploy at https://atsyplenkov.github.io):\n"
            "  download or extract a full site tree into a local directory, then\n"
            "  pass that directory as --site. Metadata must still use the\n"
            "  canonical host https://anatolii.nz (not the staging hostname).\n"
        ),
    )
    parser.add_argument(
        "--site",
        type=Path,
        default=DEFAULT_SITE,
        help=(
            "Path to a deployable site tree to audit (default: _site). "
            "Accepts a local build output, a downloaded staging mirror, or an "
            "extracted GitHub Pages artifact."
        ),
    )
    parser.add_argument(
        "--freeze-dir",
        type=Path,
        default=FREEZE_DIR,
        help="Path to freeze manifests (default: scripts/fixtures/migration-freeze)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run controlled malformed-artifact demonstrations and exit",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    site_dir = args.site.expanduser()
    if not site_dir.is_absolute():
        site_dir = REPO_ROOT / site_dir
    site_dir = site_dir.resolve()

    freeze_dir = args.freeze_dir.expanduser()
    if not freeze_dir.is_absolute():
        freeze_dir = REPO_ROOT / freeze_dir
    freeze_dir = freeze_dir.resolve()

    if not site_dir.is_dir():
        print(f"audit failed: site directory does not exist: {site_dir}", file=sys.stderr)
        return 1

    print(f"auditing site tree: {site_dir}", flush=True)
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
