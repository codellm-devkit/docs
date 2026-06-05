#!/usr/bin/env python3
"""Generate Starlight API-reference markdown for the CLDK Python SDK.

This replaces the mkdocstrings (`::: cldk.core`) directives that the old
mkdocs site used. It statically introspects the *release-tagged* `cldk`
package with `griffe` (the same library mkdocstrings is built on) and emits
plain Starlight markdown pages under
`src/content/docs/reference/python-api/`.

Run it from the environment where `cldk` is importable so that re-exported
schema models (which live in the external `codeanalyzer` packages) resolve:

    pip install "cldk==<tag>"      # or: pip install -e ../python-sdk
    python scripts/gen_api_docs.py

Mirrors the old mkdocstrings options: google docstrings, source member order,
and a `!^_` filter (private members hidden).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import griffe

# Sphinx/RST cross-reference roles like :class:`~cldk.x.Foo` or :meth:`bar`
# that appear in the source docstrings. Starlight markdown won't resolve them,
# so collapse them to the bare symbol name (`Foo`, `bar`).
_RST_ROLE = re.compile(r":(?:class|meth|func|mod|attr|obj|data|exc|ref|term):`~?([^`]+)`")


def clean_rst(text: str) -> str:
    if not text:
        return text
    return _RST_ROLE.sub(lambda m: f"`{m.group(1).rsplit('.', 1)[-1]}`", text)


# Em-dashes are banned from the rendered docs; normalize any that slip in from
# upstream docstrings to a colon (for "**Label** — desc" definitions) or a comma.
_LABEL_DASH = re.compile(r"\*\*([^*\n]+)\*\*([^\n—]*?) — ")


def strip_emdashes(text: str) -> str:
    if not text:
        return text
    text = _LABEL_DASH.sub(r"**\1**\2: ", text)
    text = text.replace(" — ", ", ")
    text = text.replace("—", ", ")
    return text

# --------------------------------------------------------------------------- #
# Page definitions: mirror the old docs/reference/python-api/*.md layout.
# Each page is a title plus one or more (section heading, dotted module path).
# A section heading of None means the module is rendered with no extra heading.
# --------------------------------------------------------------------------- #
PAGES: list[dict] = [
    {
        "file": "core.md",
        "title": "Core",
        "description": "Core CLDK API: the top-level entry point.",
        "sections": [(None, "cldk.core")],
    },
    {
        "file": "java.md",
        "title": "Java API",
        "description": "Program analysis for Java and related data models.",
        "sections": [
            ("Analysis", "cldk.analysis.java.java_analysis"),
            ("Schema", "cldk.models.java.models"),
        ],
    },
    {
        "file": "python.md",
        "title": "Python API",
        "description": "Program analysis for Python and related data models.",
        "sections": [
            ("Analysis", "cldk.analysis.python.python_analysis"),
            ("Schema", "cldk.models.python"),
        ],
    },
    # NOTE: C analysis is intentionally omitted for now; it will return alongside
    # Go, TypeScript, and Rust. Re-add a PAGES entry + a sidebar item to restore it.
]


def is_public(name: str) -> bool:
    """Mirror the mkdocstrings `filters: ["!^_"]` option."""
    return not name.startswith("_")


def resolve(obj):
    """Resolve a griffe alias to its final target, tolerating failures."""
    if obj.is_alias:
        try:
            return obj.final_target
        except Exception:
            return None
    return obj


def fmt_annotation(annotation) -> str:
    if annotation is None:
        return ""
    return str(annotation)


def fmt_parameters(func) -> str:
    """Reconstruct a readable parameter list from a griffe function."""
    parts: list[str] = []
    for param in func.parameters:
        if param.name in ("self", "cls"):
            continue
        kind = getattr(param.kind, "value", str(param.kind))
        prefix = ""
        if kind == "variadic positional":
            prefix = "*"
        elif kind == "variadic keyword":
            prefix = "**"
        piece = f"{prefix}{param.name}"
        ann = fmt_annotation(param.annotation)
        if ann:
            piece += f": {ann}"
        if param.default is not None and prefix == "":
            piece += f" = {param.default}"
        parts.append(piece)
    return ", ".join(parts)


def signature(func) -> str:
    params = fmt_parameters(func)
    sig = f"{func.name}({params})"
    returns = fmt_annotation(func.returns)
    if returns:
        sig += f" -> {returns}"
    return sig


def _esc(text: str) -> str:
    """Escape pipes and collapse newlines for use inside a markdown table cell."""
    return " ".join(clean_rst(text or "").split()).replace("|", "\\|")


def render_docstring(obj, out: list[str], skip_attributes: bool = False) -> None:
    """Render a parsed google-style docstring into readable markdown sections."""
    if not obj.docstring:
        return
    try:
        sections = obj.docstring.parsed
    except Exception:
        sections = None
    if not sections:
        value = obj.docstring.value.strip()
        if value:
            out.append(value)
            out.append("")
        return

    K = griffe.DocstringSectionKind
    for section in sections:
        kind = section.kind
        value = section.value

        if kind == K.text:
            if value and value.strip():
                out.append(clean_rst(value.strip()))
                out.append("")
        elif kind == K.parameters:
            out.append("**Parameters:**")
            out.append("")
            out.append("| Name | Type | Description |")
            out.append("| ---- | ---- | ----------- |")
            for p in value:
                out.append(
                    f"| `{p.name}` | `{_esc(str(p.annotation)) if p.annotation else ''}` "
                    f"| {_esc(p.description)} |"
                )
            out.append("")
        elif kind == K.attributes:
            if skip_attributes:
                continue
            out.append("**Attributes:**")
            out.append("")
            out.append("| Name | Type | Description |")
            out.append("| ---- | ---- | ----------- |")
            for a in value:
                out.append(
                    f"| `{a.name}` | `{_esc(str(a.annotation)) if a.annotation else ''}` "
                    f"| {_esc(a.description)} |"
                )
            out.append("")
        elif kind == K.returns:
            out.append("**Returns:**")
            out.append("")
            for r in value:
                ann = f"`{_esc(str(r.annotation))}`" if r.annotation else ""
                desc = _esc(r.description)
                out.append(f"- {ann}: {desc}" if ann else f"- {desc}")
            out.append("")
        elif kind == K.raises:
            out.append("**Raises:**")
            out.append("")
            for r in value:
                ann = f"`{_esc(str(r.annotation))}`" if r.annotation else ""
                desc = _esc(r.description)
                out.append(f"- {ann}: {desc}" if ann else f"- {desc}")
            out.append("")
        elif kind == K.admonition:
            title = getattr(section, "title", None) or "Note"
            contents = clean_rst(getattr(value, "contents", "") or "")
            out.append(f"> **{title}**")
            for line in contents.strip().splitlines():
                out.append(f"> {line}")
            out.append("")
        elif kind == K.examples:
            out.append("**Examples:**")
            out.append("")
            for ex in value:
                # each example is a (kind, text) tuple
                text = ex[1] if isinstance(ex, (tuple, list)) and len(ex) > 1 else str(ex)
                out.append(text.rstrip())
            out.append("")
        else:
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
                out.append("")


def render_function(func, level: int, qualifier: str, out: list[str]) -> None:
    heading = "#" * level
    label = f"{qualifier}.{func.name}" if qualifier else func.name
    out.append(f"{heading} `{label}`")
    out.append("")
    out.append("```python")
    out.append(signature(func))
    out.append("```")
    out.append("")
    render_docstring(func, out)


def member_attributes(cls):
    return [
        m
        for m in cls.members.values()
        if not m.is_alias
        and m.kind is griffe.Kind.ATTRIBUTE
        and is_public(m.name)
    ]


def render_attributes(cls, level: int, out: list[str]) -> None:
    attrs = member_attributes(cls)
    if not attrs:
        return
    out.append("#" * level + " Attributes")
    out.append("")
    out.append("| Name | Type | Description |")
    out.append("| ---- | ---- | ----------- |")
    for attr in attrs:
        ann = fmt_annotation(attr.annotation).replace("|", "\\|")
        doc = ""
        if attr.docstring and attr.docstring.value.strip():
            doc = attr.docstring.value.strip().splitlines()[0].replace("|", "\\|")
        out.append(f"| `{attr.name}` | `{ann}` | {doc} |")
    out.append("")


def render_class(cls, level: int, out: list[str]) -> None:
    bases = ", ".join(str(b) for b in cls.bases)
    decl = f"class {cls.name}({bases})" if bases else f"class {cls.name}"
    out.append(f"{'#' * level} `{cls.name}`")
    out.append("")
    out.append("```python")
    out.append(decl)
    out.append("```")
    out.append("")
    # Prefer the member-derived attribute table (real field types) when the
    # class exposes attributes; otherwise let the docstring's Attributes
    # section through so hand-documented attributes still appear.
    has_member_attrs = bool(member_attributes(cls))
    render_docstring(cls, out, skip_attributes=has_member_attrs)

    render_attributes(cls, level + 1, out)

    methods = [
        m
        for m in cls.members.values()
        if not m.is_alias
        and m.kind is griffe.Kind.FUNCTION
        and is_public(m.name)
    ]
    if methods:
        out.append("#" * (level + 1) + " Methods")
        out.append("")
        for method in methods:
            render_function(method, level + 2, cls.name, out)


def collect_members(module):
    """Public classes/functions documented by a module, in declaration order.

    Mirrors mkdocstrings: when ``__all__`` is defined, follow it (resolving
    re-exported aliases to their targets); otherwise document only members
    that are actually defined in this module (skip imports/aliases).
    """
    members = []
    exports = getattr(module, "exports", None)

    if exports:
        names = [e if isinstance(e, str) else getattr(e, "name", str(e)) for e in exports]
        for name in names:
            member = module.members.get(name)
            if member is None or not is_public(name):
                continue
            target = resolve(member)
            if target is not None and target.kind in (griffe.Kind.CLASS, griffe.Kind.FUNCTION):
                members.append(target)
        return members

    for name, member in module.members.items():
        if not is_public(name) or member.is_alias:
            continue
        if member.kind in (griffe.Kind.CLASS, griffe.Kind.FUNCTION):
            members.append(member)
    return members


def render_module(module, base_level: int, out: list[str]) -> None:
    render_docstring(module, out)
    members = collect_members(module)
    if not members:
        out.append("_No public symbols are exposed by this module._")
        out.append("")
        return
    for member in members:
        if member.kind is griffe.Kind.CLASS:
            render_class(member, base_level, out)
        else:
            render_function(member, base_level, "", out)


def get_object(root, dotted: str):
    """Descend a dotted path from the loaded root module."""
    parts = dotted.split(".")
    obj = root
    for part in parts[1:]:  # parts[0] == root name ("cldk")
        obj = obj.members[part]
    return resolve(obj) or obj


# Markers delimiting the auto-generated "Zone C" symbol reference. Authored
# content (frontmatter, overview, worked example) lives OUTSIDE these markers
# and is preserved across regeneration.
MARK_START = "<!-- CLDK:API:START -->"
MARK_END = "<!-- CLDK:API:END -->"


# A GitHub badge linking to the python-sdk source, shown atop every API page.
GITHUB_BADGE = (
    "[![Source on GitHub]"
    "(https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)]"
    "(https://github.com/codellm-devkit/python-sdk)"
)


def build_body(root, page: dict) -> str:
    """The generated symbol reference body (no frontmatter)."""
    out: list[str] = [GITHUB_BADGE, ""]
    multi = len(page["sections"]) > 1
    for heading, dotted in page["sections"]:
        module = get_object(root, dotted)
        if heading:
            out.append(f"## {heading}")
            out.append("")
        # When the page has named sections, classes start one level deeper.
        base_level = 3 if multi else 2
        render_module(module, base_level, out)
    return strip_emdashes("\n".join(out).strip())


def build_block(body: str) -> str:
    """Wrap the generated body in injection markers."""
    return (
        f"{MARK_START}\n\n"
        "<!-- AUTO-GENERATED by scripts/gen_api_docs.py, do not edit by hand. -->\n\n"
        f"{body}\n\n{MARK_END}"
    )


def build_full_page(page: dict, block: str) -> str:
    """A complete page (frontmatter + generated block) for first-time output."""
    return (
        "---\n"
        f'title: "{page["title"]}"\n'
        f'description: "{page["description"]}"\n'
        "---\n\n"
        f"{block}\n"
    )


def inject_or_create(dest: Path, page: dict, body: str) -> str:
    """Replace the marked region in an existing authored page, else create it."""
    block = build_block(body)
    if dest.exists():
        text = dest.read_text(encoding="utf-8")
        if MARK_START in text and MARK_END in text:
            head = text.split(MARK_START, 1)[0]
            tail = text.split(MARK_END, 1)[1]
            return f"{head.rstrip()}\n\n{block}\n{tail.rstrip()}\n".replace(
                "\n\n\n", "\n\n"
            )
    return build_full_page(page, block)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "src/content/docs/reference/python-api",
        help="Output directory for generated markdown.",
    )
    parser.add_argument(
        "--search-path",
        type=Path,
        default=None,
        help="Optional path to the cldk source tree (e.g. ../python-sdk). "
        "Defaults to whatever is importable on sys.path.",
    )
    args = parser.parse_args()

    search_paths = [str(args.search_path)] if args.search_path else None
    # Schema modules re-export Pydantic models from the external `codeanalyzer-*`
    # backends. Load those source trees too so the re-export aliases resolve to
    # real definitions. Static analysis only: inspection imports heavy deps
    # (numpy/clang) that can crash, so it stays disabled.
    external_packages = ["codeanalyzer"]
    try:
        loader = griffe.GriffeLoader(
            search_paths=search_paths,
            docstring_parser=griffe.Parser.google,
            allow_inspection=False,
        )
        root = loader.load("cldk")
        for pkg in external_packages:
            try:
                loader.load(pkg)
            except Exception as exc:
                print(f"warning: could not load '{pkg}' for alias resolution: {exc}",
                      file=sys.stderr)
        loader.resolve_aliases(implicit=True, external=False)
    except Exception as exc:  # pragma: no cover
        print(f"error: failed to load 'cldk' with griffe: {exc}", file=sys.stderr)
        print(
            "hint: install the SDK first, e.g. `pip install cldk==<tag>` "
            "or `pip install -e ../python-sdk`.",
            file=sys.stderr,
        )
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        body = build_body(root, page)
        dest = args.out / page["file"]
        text = inject_or_create(dest, page, body)
        mode = "injected into" if dest.exists() and MARK_START in dest.read_text(encoding="utf-8") else "wrote"
        dest.write_text(text, encoding="utf-8")
        print(f"{mode} {dest} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
