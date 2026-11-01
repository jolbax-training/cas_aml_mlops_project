#!/usr/bin/env python3
"""Build the offline HTML work log from explicitly selected Markdown sources.

    .venv/bin/python scripts/build_work_log.py            # write report/index.html
    .venv/bin/python scripts/build_work_log.py --check    # validate, write nothing

The builder reads only the files named in docs/work_log.toml. It never imports or
runs agent, evaluator, API, Podman, MLflow, or CI code, and the output needs no
server, network, or JavaScript.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html
import os
import re
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("docs/work_log.toml")
DEFAULT_OUTPUT = Path("report/index.html")

TITLE = "Agent evaluation and MLOps work log"
ARCHITECTURE_TITLE = "Goal architecture: bounded agent, hidden grading, local evidence"
LABELS = {
    "current": "Current",
    "historical": "Historical / superseded context",
    "personal": "Personal, student-authored",
    "reviewed": "Reviewed record",
}
STATUSES = {
    "implemented": "Implemented",
    "planned": "Planned",
    "incomplete": "Incomplete, work in progress",
}
SECTION_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Path components that must never be selected or linked as local references.
FORBIDDEN_PATTERNS = (
    ".git", ".venv", "venv", ".env", ".env.*", ".envrc", "secrets", ".secrets",
    "credentials", "credentials*", "*.pem", "*.key", "*.p12", "*.pfx", "*.log",
    "runs", "run_bundles", "artifacts", "outputs", "mlruns", "mlartifacts",
    "mlflow.db*", "mlflow.sqlite*", "report", ".claude", ".codex", ".idea",
    ".vscode", ".ds_store", "__pycache__", ".pytest_cache", "node_modules",
)
SVG_TAGS = {"svg", "title", "desc", "defs", "marker", "path", "g", "rect", "text", "tspan", "style"}
SVG_NS = "http://www.w3.org/2000/svg"
# ElementTree has no per-call way to serialize namespaced tags with unqualified attributes and no
# prefix (default_namespace rejects them), so the empty prefix is registered once; the builder is
# the only serializer of SVG-namespace XML in this process.
ET.register_namespace("", SVG_NS)


class WorkLogError(Exception):
    """A source, link, or output problem; the message is the diagnostic."""


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    kind: str
    path: PurePosixPath | None = None
    label: str | None = None
    status: str | None = None
    needs: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class Diagram:
    id: str
    title: str
    svg: PurePosixPath
    text: PurePosixPath
    description: str
    label: str


@dataclass(frozen=True)
class Config:
    diagram: PurePosixPath
    explanation: PurePosixPath
    sections: tuple[Section, ...]
    diagrams: tuple[Diagram, ...] = ()


@dataclass
class Doc:
    section_id: str
    rel: str
    path: Path
    sha: str
    tokens: list[Token]
    slugs: dict[str, str]


# --- path safety -------------------------------------------------------------

def forbidden_reason(rel: PurePosixPath) -> str | None:
    for part in rel.parts:
        for pattern in FORBIDDEN_PATTERNS:
            if fnmatch.fnmatchcase(part.lower(), pattern):
                return f"{part!r} matches the forbidden pattern {pattern!r}"
    return None


def resolve_repo_path(root: Path, base: Path, raw: str) -> Path:
    """Resolve a repository-relative reference, refusing unsafe inputs."""
    if not raw or "\0" in raw or "\\" in raw:
        raise WorkLogError("empty or malformed path")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise WorkLogError("absolute paths are not allowed")
    joined = Path(os.path.normpath(base / raw))
    try:
        rel = joined.relative_to(root)
    except ValueError:
        raise WorkLogError("path escapes the repository") from None
    reason = forbidden_reason(PurePosixPath(rel.as_posix()))
    if reason:
        raise WorkLogError(f"private or generated location: {reason}")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise WorkLogError(f"symlinks are not allowed ({part!r})")
    if not joined.exists():
        raise WorkLogError("file does not exist")
    return joined


# --- source list --------------------------------------------------------------

def _check_keys(table: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise WorkLogError(f"{where}: unknown key(s) {', '.join(unknown)}")


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkLogError(f"{where}: {key!r} must be a non-empty string")
    return value


def load_config(root: Path, config_path: Path) -> Config:
    try:
        with open(config_path, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise WorkLogError(f"cannot read source list {config_path}: {error}") from None
    _check_keys(data, {"architecture", "section", "diagram"}, "source list")
    arch = data.get("architecture")
    if not isinstance(arch, dict):
        raise WorkLogError("source list: [architecture] table is required")
    _check_keys(arch, {"diagram", "explanation"}, "[architecture]")
    raw_sections = data.get("section")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise WorkLogError("source list: at least one [[section]] is required")

    sections: list[Section] = []
    seen: set[str] = set()
    for index, table in enumerate(raw_sections, start=1):
        where = f"[[section]] #{index}"
        _check_keys(table, {"id", "title", "kind", "path", "label", "status", "needs", "description"}, where)
        section_id = _require_str(table, "id", where)
        where = f"section {section_id!r}"
        if not SECTION_ID.match(section_id) or section_id in {"architecture", "sections", "provenance"}:
            raise WorkLogError(f"{where}: id must be a lowercase hyphenated anchor and not reserved")
        if section_id in seen:
            raise WorkLogError(f"{where}: duplicate id")
        seen.add(section_id)
        title = _require_str(table, "title", where)
        kind = table.get("kind", "document")
        status = table.get("status")
        if status is not None and status not in STATUSES:
            raise WorkLogError(f"{where}: status must be one of {', '.join(STATUSES)}")
        if kind == "document":
            if "needs" in table or "description" in table:
                raise WorkLogError(f"{where}: needs/description belong to pending sections")
            label = _require_str(table, "label", where)
            if label not in LABELS:
                raise WorkLogError(f"{where}: label must be one of {', '.join(LABELS)}")
            path = _require_str(table, "path", where)
            if not path.endswith(".md"):
                raise WorkLogError(f"{where}: only Markdown sources can be selected")
            sections.append(Section(section_id, title, kind, PurePosixPath(path), label, status))
        elif kind == "pending":
            if "path" in table or "label" in table or status is not None:
                raise WorkLogError(f"{where}: pending sections take no path, label, or status")
            needs = table.get("needs", [])
            if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
                raise WorkLogError(f"{where}: needs must be a list of strings")
            sections.append(Section(section_id, title, kind, needs=tuple(needs),
                                    description=_require_str(table, "description", where)))
        else:
            raise WorkLogError(f"{where}: kind must be 'document' or 'pending'")
    for key, suffix in (("diagram", ".svg"), ("explanation", ".md")):
        if PurePosixPath(_require_str(arch, key, "[architecture]")).suffix.lower() != suffix:
            raise WorkLogError(f"[architecture]: {key!r} must be a {suffix} file")
    diagrams = _load_diagrams(data.get("diagram", []), seen)
    return Config(
        PurePosixPath(_require_str(arch, "diagram", "[architecture]")),
        PurePosixPath(_require_str(arch, "explanation", "[architecture]")),
        tuple(sections),
        diagrams,
    )


def _load_diagrams(raw: object, section_ids: set[str]) -> tuple[Diagram, ...]:
    """Registered draw.io diagrams: [[diagram]] tables, each with an editable SVG and a text twin."""
    if not isinstance(raw, list):
        raise WorkLogError("source list: [[diagram]] must be an array of tables")
    diagrams: list[Diagram] = []
    seen = set(section_ids)
    for index, table in enumerate(raw, start=1):
        where = f"[[diagram]] #{index}"
        if not isinstance(table, dict):
            raise WorkLogError(f"{where}: must be a table")
        _check_keys(table, {"id", "title", "svg", "text", "description", "label"}, where)
        diagram_id = _require_str(table, "id", where)
        where = f"diagram {diagram_id!r}"
        if not SECTION_ID.match(diagram_id) or diagram_id in {"architecture", "sections", "provenance"}:
            raise WorkLogError(f"{where}: id must be a lowercase hyphenated anchor and not reserved")
        if diagram_id in seen:
            raise WorkLogError(f"{where}: duplicate id")
        seen.add(diagram_id)
        label = _require_str(table, "label", where)
        if label not in LABELS:
            raise WorkLogError(f"{where}: label must be one of {', '.join(LABELS)}")
        svg, text = _require_str(table, "svg", where), _require_str(table, "text", where)
        if not svg.endswith(".drawio.svg"):
            raise WorkLogError(f"{where}: 'svg' must be a .drawio.svg file")
        if not text.endswith(".md"):
            raise WorkLogError(f"{where}: 'text' must be a Markdown (.md) file")
        diagrams.append(Diagram(diagram_id, _require_str(table, "title", where), PurePosixPath(svg),
                                PurePosixPath(text), _require_str(table, "description", where), label))
    return tuple(diagrams)


# --- Markdown -----------------------------------------------------------------

def make_parser() -> MarkdownIt:
    parser = MarkdownIt("commonmark", {"html": False}).enable("table").enable("strikethrough")
    # Let the builder classify every destination instead of silently dropping some.
    parser.validateLink = lambda url: True
    return parser


def slugify(text: str) -> str:
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-") or "section"


def inline_text(token: Token) -> str:
    return "".join(c.content for c in token.children or [] if c.type in ("text", "code_inline"))


def heading_slugs(tokens: list[Token]) -> dict[str, str]:
    """Map each heading's unique slug to its text, in document order."""
    slugs: dict[str, str] = {}
    counts: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        text = inline_text(tokens[index + 1])
        base = slugify(text)
        seen = counts.get(base, 0)
        counts[base] = seen + 1
        slugs[base if seen == 0 else f"{base}-{seen}"] = text
    return slugs


def read_doc(root: Path, parser: MarkdownIt, section_id: str, rel: PurePosixPath) -> Doc:
    try:
        path = resolve_repo_path(root, root, rel.as_posix())
        data = path.read_bytes()
        text = data.decode("utf-8")
    except WorkLogError as error:
        raise WorkLogError(f"{rel}: {error}") from None
    except (OSError, UnicodeDecodeError) as error:
        raise WorkLogError(f"{rel}: cannot read as UTF-8 text ({error})") from None
    if not path.is_file():
        raise WorkLogError(f"{rel}: not a regular file")
    tokens = parser.parse(text)
    return Doc(section_id, rel.as_posix(), path, hashlib.sha256(data).hexdigest()[:12],
               tokens, heading_slugs(tokens))


class LinkContext:
    def __init__(self, root: Path, output_dir: Path, docs: list[Doc], parser: MarkdownIt):
        self.root, self.output_dir, self.parser = root, output_dir, parser
        self.by_path = {doc.path: doc for doc in docs}
        self.errors: list[str] = []
        self._slug_cache: dict[Path, dict[str, str]] = {}

    def slugs_of(self, path: Path) -> dict[str, str]:
        if path not in self._slug_cache:
            tokens = self.parser.parse(path.read_text(encoding="utf-8", errors="replace"))
            self._slug_cache[path] = heading_slugs(tokens)
        return self._slug_cache[path]


def classify_link(href: str, doc: Doc, ctx: LinkContext) -> tuple[str, str, bool]:
    """Return (new href, CSS class, is external); raise WorkLogError if unusable."""
    parts = urlsplit(href)
    if parts.scheme:
        scheme = parts.scheme.lower()
        if scheme not in ("http", "https"):
            raise WorkLogError(f"unsafe URL scheme {scheme!r}")
        if parts.username or parts.password:
            raise WorkLogError("URLs with embedded credentials are not allowed")
        if scheme == "http":
            if (parts.hostname or "").lower() not in LOOPBACK_HOSTS:
                raise WorkLogError("plain http is only allowed for loopback hosts")
            return href, "ref local-service", True
        return href, "ref external", True
    if parts.netloc:
        raise WorkLogError("protocol-relative URLs are not allowed")
    fragment = unquote(parts.fragment)
    if not parts.path:
        if not fragment:
            raise WorkLogError("empty link")
        if fragment not in doc.slugs:
            raise WorkLogError(f"no heading #{fragment} in this document")
        return f"#{doc.section_id}--{fragment}", "", False
    target = resolve_repo_path(ctx.root, doc.path.parent, unquote(parts.path))
    included = ctx.by_path.get(target)
    if included:
        if not fragment:
            return f"#{included.section_id}", "", False
        if fragment not in included.slugs:
            raise WorkLogError(f"no heading #{fragment} in {included.rel}")
        return f"#{included.section_id}--{fragment}", "", False
    if fragment and target.suffix.lower() == ".md" and fragment not in ctx.slugs_of(target):
        raise WorkLogError(f"no heading #{fragment} in {target.relative_to(ctx.root).as_posix()}")
    rebased = Path(os.path.relpath(target, ctx.output_dir)).as_posix()
    return rebased + (f"#{fragment}" if fragment else ""), "ref source-file", False


CHECKBOX = re.compile(r"^\[( |x|X)\] ")


def prepare_tokens(doc: Doc, ctx: LinkContext) -> None:
    """Anchor headings, resolve links, neutralise images, and mark checklists."""
    counts: dict[str, int] = {}
    tokens = doc.tokens
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            base = slugify(inline_text(tokens[index + 1]))
            seen = counts.get(base, 0)
            counts[base] = seen + 1
            slug = base if seen == 0 else f"{base}-{seen}"
            token.attrSet("id", f"{doc.section_id}--{slug}")
            # The section heading is h2, so document headings start at h3.
            token.tag = f"h{min(6, int(token.tag[1]) + 2)}"
        elif token.type == "heading_close":
            token.tag = f"h{min(6, int(token.tag[1]) + 2)}"
        elif token.type == "inline":
            prepare_inline(doc, token, ctx)
            if index >= 2 and tokens[index - 2].type == "list_item_open":
                mark_checkbox(token)


def prepare_inline(doc: Doc, token: Token, ctx: LinkContext) -> None:
    for child in token.children or []:
        if child.type == "link_open":
            href = child.attrGet("href") or ""
            try:
                new_href, css, external = classify_link(href, doc, ctx)
            except WorkLogError as error:
                ctx.errors.append(f"{doc.rel}: link {href!r}: {error}")
                continue
            child.attrSet("href", new_href)
            if css:
                child.attrSet("class", css)
            if external:
                child.attrSet("rel", "noopener noreferrer")
        elif child.type == "image":
            child.type, child.tag, child.attrs = "text", "", {}
            child.content = f"[image not loaded: {child.content or 'no description'}]"
            child.children = None


def mark_checkbox(token: Token) -> None:
    first = (token.children or [None])[0]
    match = first is not None and first.type == "text" and CHECKBOX.match(first.content)
    if not match:
        return
    done = match.group(1) != " "
    first.content = first.content[match.end():]
    glyph = Token("html_inline", "", 0)
    glyph.content = (
        '<span class="check" role="img" aria-label="'
        + ("done" if done else "not done") + '">' + ("&#9745;" if done else "&#9744;") + "</span> "
    )
    token.children.insert(0, glyph)


# --- architecture asset -------------------------------------------------------

def validate_svg(text: str) -> str:
    """Accept only the reviewed, script-free local diagram; return it for inlining."""
    if re.search(r"<!(DOCTYPE|ENTITY)", text, re.I):
        raise WorkLogError("diagram: DOCTYPE/ENTITY declarations are not allowed")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise WorkLogError(f"diagram: invalid SVG ({error})") from None
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in SVG_TAGS:
            raise WorkLogError(f"diagram: element <{tag}> is not allowed")
        if tag == "style" and re.search(r"@import|url\(", element.text or "", re.I):
            raise WorkLogError("diagram: stylesheet may not import or load resources")
        for name, value in element.attrib.items():
            name = name.rsplit("}", 1)[-1].lower()
            if name.startswith("on") or name.endswith("href"):
                raise WorkLogError(f"diagram: attribute {name!r} is not allowed")
            if "url(" in value and not re.fullmatch(r"url\(#[A-Za-z0-9_-]+\)", value):
                raise WorkLogError("diagram: only local url(#id) references are allowed")
    if root.tag.rsplit("}", 1)[-1] != "svg" or root.get("role") != "img" or not root.get("aria-labelledby"):
        raise WorkLogError("diagram: root must be an <svg role='img' aria-labelledby=...>")
    titles = {e.get("id") for e in root.iter() if e.tag.rsplit("}", 1)[-1] in ("title", "desc")}
    if not set(root.get("aria-labelledby").split()) <= titles:
        raise WorkLogError("diagram: aria-labelledby must name its <title> and <desc>")
    return re.sub(r"^<\?xml[^>]*\?>\s*", "", text)


# --- draw.io diagrams ----------------------------------------------------------
# `validate_svg` above stays the gate for the reviewed work-log figure. Registered draw.io
# exports go through `sanitize_drawio_svg` instead: it accepts a closed set of elements,
# attributes, and value shapes, fails on anything else, and re-serializes the validated tree.

DRAWIO_DOCTYPE = ('<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                  '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
DRAWIO_TAGS = {"svg", "g", "rect", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "defs"}
# Removed on purpose and never inlined: the editable payload, draw.io's page styling, and
# bookkeeping. `xmlns:xlink` is a namespace declaration, not an attribute, and is not kept.
DRAWIO_STRIP = {"svg": {"content", "style", "version"}, "g": {"data-cell-id"}}
_NUM = r"-?\d+(?:\.\d+)?"
_PX = rf"{_NUM}(?:px)?"
_SIMPLE_COLOUR = (r"(?:none|transparent|#[0-9a-fA-F]{3,8}"
                  rf"|rgba?\(\s*{_NUM}\s*,\s*{_NUM}\s*,\s*{_NUM}\s*(?:,\s*{_NUM}\s*)?\))")
_COLOUR = (rf"(?:{_SIMPLE_COLOUR}|light-dark\(\s*{_SIMPLE_COLOUR}\s*,\s*{_SIMPLE_COLOUR}\s*\)"
           rf"|var\(--ge-dark-color,\s*{_SIMPLE_COLOUR}\))")
_PRESENTATION = {
    "fill": _COLOUR, "stroke": _COLOUR, "stroke-width": _NUM, "stroke-miterlimit": _NUM,
    "stroke-dasharray": rf"(?:none|{_NUM}(?:[ ,]+{_NUM})*)",
    "stroke-linecap": r"butt|round|square", "stroke-linejoin": r"miter|round|bevel",
    "fill-opacity": _NUM, "stroke-opacity": _NUM, "opacity": _NUM,
    "font-family": r"[A-Za-z0-9 ,\-]+", "font-size": _PX, "font-weight": r"normal|bold|\d{3}",
    "font-style": r"normal|italic", "text-anchor": r"start|middle|end",
    "dominant-baseline": r"[a-z-]+", "pointer-events": r"all|stroke|fill|none|visible[a-z]*",
    "visibility": r"visible|hidden",
}
_NUMLIST = rf"{_NUM}(?:[ ,]+{_NUM})*"
DRAWIO_VALUES = {
    **{name: re.compile(pattern) for name, pattern in _PRESENTATION.items()},
    "transform": re.compile(rf"(?:translate|scale|rotate|matrix)\({_NUMLIST}\)"),
    "x": re.compile(_PX), "y": re.compile(_PX), "dx": re.compile(_PX), "dy": re.compile(_PX),
    "width": re.compile(_PX), "height": re.compile(_PX), "rx": re.compile(_PX), "ry": re.compile(_PX),
    "cx": re.compile(_PX), "cy": re.compile(_PX), "r": re.compile(_PX),
    "x1": re.compile(_PX), "y1": re.compile(_PX), "x2": re.compile(_PX), "y2": re.compile(_PX),
    "viewBox": re.compile(rf"{_NUM}(?: {_NUM}){{3}}"),
    "points": re.compile(_NUMLIST),
    "d": re.compile(r"[MmLlHhVvCcSsQqTtAaZz0-9eE+\-., ]*"),
    "style": None,  # validated declaration by declaration against _PRESENTATION
}
_GEOMETRY = {
    "svg": {"width", "height", "viewBox"}, "g": set(), "defs": set(),
    "rect": {"x", "y", "width", "height", "rx", "ry"}, "ellipse": {"cx", "cy", "rx", "ry"},
    "line": {"x1", "y1", "x2", "y2"}, "polyline": {"points"}, "polygon": {"points"}, "path": {"d"},
    "text": {"x", "y", "dx", "dy"}, "tspan": {"x", "y", "dx", "dy"},
}
_PAINT = set(_PRESENTATION) | {"transform", "style"}
DRAWIO_MAX_DEPTH = 64


def _drawio_style(value: str) -> None:
    for declaration in filter(None, (part.strip() for part in value.split(";"))):
        name, _, setting = declaration.partition(":")
        name, setting = name.strip(), setting.strip()
        pattern = _PRESENTATION.get(name)
        if pattern is None or not re.fullmatch(pattern, setting):
            raise WorkLogError(f"style declaration {declaration!r} is not allowed")


def sanitize_drawio_svg(text: str, diagram_id: str, title: str, description: str) -> str:
    """Rebuild a draw.io SVG export from a closed allowlist; return inline-ready SVG markup.

    Fails (never silently drops) on any element, attribute, or value outside the allowlist.
    The editable `content` payload, root `style`, `data-cell-id`, and `version` are removed.
    One public SVG 1.1 DOCTYPE with no internal subset is accepted; entities are not."""
    if re.search(r"<!ENTITY", text, re.I):
        raise WorkLogError("diagram: ENTITY declarations are not allowed")
    doctypes = re.findall(r"<!DOCTYPE[^>]*>?", text, re.I)
    if len(doctypes) > 1 or (doctypes and doctypes[0] != DRAWIO_DOCTYPE):
        raise WorkLogError("diagram: only the standard public SVG 1.1 DOCTYPE is allowed")
    if doctypes:
        text = text.replace(DRAWIO_DOCTYPE, "", 1)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise WorkLogError(f"diagram: invalid SVG ({error})") from None
    if root.tag != f"{{{SVG_NS}}}svg":
        raise WorkLogError("diagram: root must be an <svg> in the SVG namespace")

    def rebuild(element: ET.Element, is_root: bool, depth: int = 0) -> ET.Element:
        if depth > DRAWIO_MAX_DEPTH:
            raise WorkLogError(f"diagram: elements nested deeper than {DRAWIO_MAX_DEPTH} levels are not allowed")
        if not isinstance(element.tag, str) or not element.tag.startswith(f"{{{SVG_NS}}}"):
            raise WorkLogError("diagram: element outside the SVG namespace is not allowed")
        tag = element.tag[len(SVG_NS) + 2:]
        if tag not in DRAWIO_TAGS:
            raise WorkLogError(f"diagram: element <{tag}> is not allowed")
        if tag == "svg" and not is_root:
            raise WorkLogError("diagram: nested <svg> is not allowed")
        if (element.text or "").strip() and tag not in {"text", "tspan"}:
            raise WorkLogError(f"diagram: text inside <{tag}> is not allowed")
        if tag == "defs" and len(element):
            raise WorkLogError("diagram: <defs> must be empty")
        clean = ET.Element(element.tag)
        allowed = _GEOMETRY[tag] | _PAINT
        for raw, value in element.attrib.items():
            if raw.startswith("{"):
                raise WorkLogError(f"diagram: namespaced attribute {raw!r} is not allowed")
            if raw in DRAWIO_STRIP.get(tag, ()) and (is_root or tag != "svg"):
                continue
            if raw not in allowed:
                raise WorkLogError(f"diagram: attribute {raw!r} on <{tag}> is not allowed")
            if raw == "style":
                _drawio_style(value)
            elif not DRAWIO_VALUES[raw].fullmatch(value):
                raise WorkLogError(f"diagram: value {value!r} of {raw!r} on <{tag}> is not allowed")
            clean.set(raw, value)
        if tag in {"text", "tspan"}:
            clean.text = element.text
        for child in element:
            rebuilt = rebuild(child, False, depth + 1)
            rebuilt.tail = child.tail if (child.tail or "").strip() == "" else None
            if (child.tail or "").strip():
                raise WorkLogError(f"diagram: text between elements inside <{tag}> is not allowed")
            if tag in {"text", "tspan"} and child.tag != f"{{{SVG_NS}}}tspan":
                raise WorkLogError(f"diagram: <{tag}> may only contain <tspan>")
            clean.append(rebuilt)
        return clean

    clean_root = rebuild(root, True)
    title_id, desc_id = f"{diagram_id}-svg-title", f"{diagram_id}-svg-desc"
    clean_root.set("role", "img")
    clean_root.set("aria-labelledby", f"{title_id} {desc_id}")
    for index, (tag, ident, content) in enumerate((("title", title_id, title), ("desc", desc_id, description))):
        node = ET.Element(f"{{{SVG_NS}}}{tag}", {"id": ident})
        node.text = content
        clean_root.insert(index, node)
    markup = ET.tostring(clean_root, encoding="unicode")
    if re.search(r"</?ns\d+:", markup):
        raise WorkLogError("diagram: unexpected namespace prefix in rebuilt SVG")
    return markup


# --- HTML assembly ------------------------------------------------------------

CSS = """
:root { color-scheme: light; --fg: #111827; --muted: #4b5563; --line: #cbd5e1; --accent: #1d4ed8; --bg: #ffffff; --soft: #f1f5f9; }
* { box-sizing: border-box; }
body { margin: 0; color: var(--fg); background: var(--bg); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
header, main { max-width: 62rem; margin: 0 auto; padding: 0 1rem; }
header { padding-top: 1rem; }
h1 { margin: 0 0 .25rem; font-size: 1.6rem; }
h2 { margin-top: 0; font-size: 1.35rem; }
section { margin: 2rem 0; padding-top: 1rem; border-top: 2px solid var(--line); }
a { color: var(--accent); }
a:focus-visible, .scroll:focus-visible, .skip:focus-visible { outline: 3px solid #f59e0b; outline-offset: 2px; }
.skip { position: absolute; left: -999px; top: 0; background: #fff; padding: .5rem 1rem; }
.skip:focus { left: 0; z-index: 10; }
.lede, .meta { color: var(--muted); font-size: .9rem; }
.badge { display: inline-block; border: 1px solid var(--fg); border-radius: .25rem; padding: 0 .4rem; margin-right: .4rem; font-size: .8rem; font-weight: 600; }
.badge.pending { border-style: dashed; background: var(--soft); }
.scroll { overflow-x: auto; border: 1px solid var(--line); }
.scroll svg { display: block; min-width: 56rem; width: 100%; height: auto; }
nav ol { columns: 2 18rem; padding-left: 1.5rem; }
nav li { margin-bottom: .3rem; }
.content table, .provenance table { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; }
th, td { border: 1px solid var(--line); padding: .3rem .5rem; vertical-align: top; text-align: left; }
pre { overflow-x: auto; padding: .75rem; background: var(--soft); border: 1px solid var(--line); }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .9em; }
blockquote { margin-left: 0; padding-left: 1rem; border-left: 4px solid var(--line); color: var(--muted); }
a.external::after { content: " (external reference, not fetched)"; font-size: .8em; color: var(--muted); }
a.local-service::after { content: " (local-service reference, not fetched)"; font-size: .8em; color: var(--muted); }
a.source-file::after { content: " (source file, not embedded)"; font-size: .8em; color: var(--muted); }
:target { background: #fef9c3; }
.pending-box { border: 2px dashed var(--muted); padding: .75rem 1rem; background: var(--soft); }
@media (max-width: 40rem) { h1 { font-size: 1.3rem; } }
"""

CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'"


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def badges(label: str | None, status: str | None) -> str:
    out = []
    if label:
        out.append(f'<span class="badge">{esc(LABELS[label])}</span>')
    if status:
        out.append(f'<span class="badge">{esc(STATUSES[status])}</span>')
    return "".join(out)


def render_doc(parser: MarkdownIt, doc: Doc) -> str:
    return parser.renderer.render(doc.tokens, parser.options, {})


def build_html(root: Path, config: Config, build_time: datetime, output_dir: Path) -> str:
    parser = make_parser()
    try:
        diagram_bytes = resolve_repo_path(root, root, config.diagram.as_posix()).read_bytes()
        diagram = validate_svg(diagram_bytes.decode("utf-8"))
    except WorkLogError as error:
        raise WorkLogError(f"{config.diagram}: {error}") from None
    except (OSError, UnicodeDecodeError) as error:
        raise WorkLogError(f"{config.diagram}: {error}") from None

    docs: list[Doc] = [read_doc(root, parser, "architecture", config.explanation)]
    diagram_views: list[tuple[Diagram, bytes, str, Doc]] = []
    for item in config.diagrams:
        try:
            svg_bytes = resolve_repo_path(root, root, item.svg.as_posix()).read_bytes()
            markup = sanitize_drawio_svg(svg_bytes.decode("utf-8"), item.id, item.title, item.description)
        except (WorkLogError, OSError, UnicodeDecodeError) as error:
            raise WorkLogError(f"{item.svg}: {error}") from None
        twin = read_doc(root, parser, item.id, item.text)
        docs.append(twin)
        diagram_views.append((item, svg_bytes, markup, twin))
    section_docs: dict[str, Doc] = {}
    for section in config.sections:
        if section.kind == "document":
            section_docs[section.id] = read_doc(root, parser, section.id, section.path)
            docs.append(section_docs[section.id])
    paths = [doc.path for doc in docs]
    if len(set(paths)) != len(paths):
        raise WorkLogError("the same file is selected more than once")

    # The explanation links the included documents, so only those may be link targets.
    ctx = LinkContext(root, output_dir, docs, parser)
    for doc in docs:
        prepare_tokens(doc, ctx)
    if ctx.errors:
        raise WorkLogError("unresolved or unsafe references:\n  " + "\n  ".join(ctx.errors))

    stamp = build_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    pending = [s for s in config.sections if s.kind == "pending"]
    nav = []
    body = []
    for item, svg_bytes, markup, twin in diagram_views:
        tag = badges(item.label, None)
        body.append(
            f'<section id="{item.id}" aria-labelledby="{item.id}-title">'
            f'<h2 id="{item.id}-title">{esc(item.title)}</h2>'
            f'<p class="meta">{tag} Editable diagram: <code>{esc(item.svg.as_posix())}</code> '
            f'(sha256 <code>{hashlib.sha256(svg_bytes).hexdigest()[:12]}</code>). '
            f'Text equivalent: <code>{esc(twin.rel)}</code> (sha256 <code>{twin.sha}</code>).</p>'
            f'<div class="scroll" tabindex="0" role="region" aria-label="{esc(item.title)}, scrollable">'
            f'{markup}</div>'
            f'<div class="content">{render_doc(parser, twin)}</div></section>')
        nav.append(f'<li><a href="#{item.id}">{esc(item.title)}</a> {tag}</li>')
    for section in config.sections:
        tag = ""
        if section.kind == "pending":
            tag = '<span class="badge pending">Pending</span>'
            needs = ", ".join(f"<code>{esc(n)}</code>" for n in section.needs) or "a registered reviewed record"
            body.append(
                f'<section id="{section.id}" aria-labelledby="{section.id}-title">'
                f'<h2 id="{section.id}-title">{esc(section.title)}</h2>'
                f'<div class="pending-box"><p class="meta">{tag} No reviewed record is registered yet.</p>'
                f"<p>{esc(section.description)}</p>"
                f"<p>Awaiting reviewed evidence from: {needs}. Nothing is shown here until it exists.</p></div>"
                "</section>")
        else:
            doc = section_docs[section.id]
            tag = badges(section.label, section.status)
            body.append(
                f'<section id="{section.id}" aria-labelledby="{section.id}-title">'
                f'<h2 id="{section.id}-title">{esc(section.title)}</h2>'
                f'<p class="meta">{tag} Source: <code>{esc(doc.rel)}</code> (sha256 <code>{doc.sha}</code>)</p>'
                f'<div class="content">{render_doc(parser, doc)}</div></section>')
        nav.append(f'<li><a href="#{section.id}">{esc(section.title)}</a> {tag}</li>')

    rows = (
        f"<tr><td><code>{esc(config.diagram.as_posix())}</code></td><td>Architecture diagram</td>"
        f"<td>{esc(LABELS['current'])}</td><td><code>{hashlib.sha256(diagram_bytes).hexdigest()[:12]}</code></td></tr>"
        f"<tr><td><code>{esc(docs[0].rel)}</code></td><td>Architecture text equivalent</td>"
        f"<td>{esc(LABELS['current'])}</td><td><code>{docs[0].sha}</code></td></tr>"
    ) + "".join(
        f"<tr><td><code>{esc(item.svg.as_posix())}</code></td><td>{esc(item.title)} (editable diagram)</td>"
        f"<td>{esc(LABELS[item.label])}</td><td><code>{hashlib.sha256(svg_bytes).hexdigest()[:12]}</code></td></tr>"
        f"<tr><td><code>{esc(twin.rel)}</code></td><td>{esc(item.title)} (text equivalent)</td>"
        f"<td>{esc(LABELS[item.label])}</td><td><code>{twin.sha}</code></td></tr>"
        for item, svg_bytes, _markup, twin in diagram_views
    ) + "".join(
        f"<tr><td><code>{esc(doc.rel)}</code></td><td>{esc(section.title)}</td>"
        f"<td>{esc(LABELS[section.label])}</td><td><code>{doc.sha}</code></td></tr>"
        for section in config.sections if section.kind == "document"
        for doc in [section_docs[section.id]]
    )
    pending_rows = "".join(f"<li>{esc(s.title)}</li>" for s in pending)
    architecture_doc = docs[0]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="generator" content="scripts/build_work_log.py">
<meta name="work-log-build-time" content="{stamp}">
<title>{TITLE}</title>
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#sections">Skip to the section list</a>
<header>
<h1>{TITLE}</h1>
<p class="lede">Local snapshot built {stamp} from {len(docs) - 1} selected Markdown sources by <code>scripts/build_work_log.py</code>. It loads no network resource and runs no candidate code.</p>
</header>
<main>
<section id="architecture" aria-labelledby="architecture-title">
<h2 id="architecture-title">{esc(ARCHITECTURE_TITLE)}</h2>
<div class="scroll" tabindex="0" role="region" aria-label="Architecture diagram, scrollable">
{diagram}
</div>
<div class="content">{render_doc(parser, architecture_doc)}</div>
</section>
<nav id="sections" aria-labelledby="sections-title">
<h2 id="sections-title">Sections</h2>
<ol>{''.join(nav)}<li><a href="#provenance">Sources and provenance</a></li></ol>
</nav>
{''.join(body)}
<section id="provenance" class="provenance" aria-labelledby="provenance-title">
<h2 id="provenance-title">Sources and provenance</h2>
<p class="meta">Only the files below were read. Hashes identify the exact content shown.</p>
<table><thead><tr><th>Source</th><th>Section</th><th>Label</th><th>sha256 (first 12)</th></tr></thead><tbody>{rows}</tbody></table>
<p>Pending sections ({len(pending)}): </p><ul>{pending_rows}</ul>
</section>
</main>
</body>
</html>
"""


# --- output validation --------------------------------------------------------

RISKY_ATTRIBUTES = {"src", "srcset", "data", "onload", "onclick", "onerror"}


class _AttributeScan(HTMLParser):
    """Collect attribute names (never values) that could load a resource or run script."""

    def __init__(self) -> None:
        super().__init__()
        self.found: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.found.update(name for name, _ in attrs if name.lower() in RISKY_ATTRIBUTES)

    handle_startendtag = handle_starttag


def _risky_attributes(html_text: str) -> set[str]:
    scan = _AttributeScan()
    scan.feed(html_text)
    scan.close()
    return scan.found


def validate_output(html_text: str) -> None:
    """Structural checks on generated HTML; raise WorkLogError on the first group of problems."""
    problems: list[str] = []
    if not html_text.startswith("<!doctype html>"):
        problems.append("missing doctype")
    if re.search(r"<(script|img|link|iframe|object|embed|form|base)\b", html_text, re.I):
        problems.append("contains a tag that could load or run a resource")
    if _risky_attributes(html_text):
        problems.append("contains a resource or event attribute")
    ids = re.findall(r'\bid="([^"]+)"', html_text)
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"duplicate ids: {', '.join(duplicates)}")
    missing = sorted({h for h in re.findall(r'<a [^>]*href="#([^"]*)"', html_text) if h not in ids})
    if missing:
        problems.append(f"internal links without targets: {', '.join(missing)}")
    arch, nav = html_text.find('<section id="architecture"'), html_text.find('<nav id="sections"')
    first = html_text.find("<section id=", nav + 1) if nav != -1 else -1
    if not (-1 < arch < nav < first):
        problems.append("architecture figure must precede navigation and the first section")
    elif "<svg" not in html_text[arch:nav] or "<title" not in html_text[arch:nav]:
        problems.append("architecture figure or its accessible title is missing")
    if "Content-Security-Policy" not in html_text:
        problems.append("missing content security policy")
    if problems:
        raise WorkLogError("output validation failed: " + "; ".join(problems))


def write_atomic(output: Path, text: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=output.parent, prefix=".index-", suffix=".tmp", delete=False)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        # NamedTemporaryFile is 0600; give the report the mode a normal write would get.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(handle.name, 0o666 & ~umask)
        os.replace(handle.name, output)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


# --- command line -------------------------------------------------------------

def parse_build_time(value: str | None) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), timezone.utc)
    return datetime.now(timezone.utc).replace(microsecond=0)


def run(root: Path, config_path: Path, output: Path, build_time: datetime, check: bool) -> str:
    try:
        output.resolve().relative_to(root.resolve())
    except ValueError:
        raise WorkLogError(
            f"output {output} is outside the repository root; rebased source links would embed local paths"
        ) from None
    config = load_config(root, config_path)
    rendered = build_html(root, config, build_time, output.parent)
    validate_output(rendered)
    sources = sum(1 for s in config.sections if s.kind == "document")
    pending = len(config.sections) - sources
    if not check:
        write_atomic(output, rendered)
        return f"wrote {output} ({sources} sources, {pending} pending sections)"
    message = f"check passed ({sources} sources, {pending} pending sections); no files written"
    if output.exists():
        existing = output.read_text(encoding="utf-8")
        validate_output(existing)
        match = re.search(r'name="work-log-build-time" content="([^"]+)"', existing)
        if match:
            same = build_html(root, config, parse_build_time(match.group(1)), output.parent)
            if same != existing:
                message += f"\nnote: {output} is out of date with its sources; rebuild to refresh it"
    return message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the offline HTML work log.")
    parser.add_argument("--check", action="store_true", help="validate sources and output; write nothing")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this repository)")
    parser.add_argument("--config", type=Path, help=f"source list (default: {DEFAULT_CONFIG})")
    parser.add_argument("--output", type=Path, help=f"output file (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--build-time", help="ISO timestamp to stamp (default: SOURCE_DATE_EPOCH or now)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        message = run(
            root,
            args.config or root / DEFAULT_CONFIG,
            args.output or root / DEFAULT_OUTPUT,
            parse_build_time(args.build_time),
            args.check,
        )
    except (WorkLogError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
