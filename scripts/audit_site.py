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
    "about/index.html",
    "papers/index.html",
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
    "blog/2020-03-03-tidy-tuesday-nhl/figures/plot-1.png",
    "blog/2020-03-03-tidy-tuesday-nhl/figures/boxplot-1.png",
    "blog/2022-03-05-soilgrids-terra/figures/unnamed-chunk-5-1.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/benchmarks.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/NVCleanstall_escFw822lQ.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/WindowsTerminal_kTF31RPuRA.png",
    "blog/2024-08-06-xgboost-gpu-r/figures/benchmarks-1.png",
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
    "data/!publ_list.html",
    "data/Tsyplenkov-Anatoly_publications.html",
}

PUBLICATION_CHECKSUM_PATHS = (
    "data/!publ_list.md",
    "data/Tsyplenkov-Anatoly_publications.html",
    "data/Tsyplenkov-Anatoly_publications.pdf",
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
            if any(f"/{path}" in loc for loc in locs for path in NON_CANONICAL_HTML):
                report.fail("sitemap includes non-canonical publication formats")
            else:
                report.ok("sitemap excludes non-canonical publication formats")
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
            if any("tufted-blog.pages.dev" in link for link in links):
                report.fail("RSS references demo host")
            else:
                report.ok("RSS host is canonical")

    if llms.is_file():
        text = llms.read_text(encoding="utf-8", errors="replace")
        for needle in (
            f"{CANONICAL_HOST}/about/",
            f"{CANONICAL_HOST}/papers/",
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
    else:
        report.fail("llms.txt missing")


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
        check_preservation_if_present(report, site_dir, manifests)
        check_publication_preservation(report, site_dir, manifests)
        check_tracer_metadata(report, site_dir)
        check_redirects(report, site_dir)
        check_discoverability(report, site_dir)
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
