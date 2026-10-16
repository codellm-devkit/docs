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
and a `!^_` filter (private members hidden). The SDK writes its docstrings for
Sphinx, so their reST markup (roles, literal blocks, `.. deprecated::`) is
rewritten to Markdown before griffe parses them.
"""

from __future__ import annotations

import argparse
import ast
import functools
import importlib.metadata
import re
import sys
import textwrap
from pathlib import Path

import griffe

# Google style, with a whole Returns section read as one item: the SDK writes
# Returns as prose, and griffe would otherwise split it into one item per line.
DOCSTRING_OPTIONS = {"returns_multiple_items": False}

# Heading levels. Starlight's page TOC lists h2 and h3, so it shows the sections
# and the classes. Methods sit below it; each big class opens with a method index.
SECTION_LEVEL = 2  # "## Analysis": one per PAGES section
CLASS_LEVEL = 3  # "### `PythonAnalysis`"
PART_LEVEL = 4  # "#### Attributes", "#### Methods"
METHOD_LEVEL = 5  # "##### `PythonAnalysis.get_cfg`", anchor #pythonanalysisget_cfg

# A class with at least this many methods gets a linked method index at its top.
INDEX_MIN_METHODS = 5

# A longer signature is wrapped one parameter per line (Black's line length).
SIGNATURE_WIDTH = 88

# Decorators that change how a method is called, shown above its signature.
CALL_DECORATORS = ("staticmethod", "classmethod", "property")

# Docstring admonitions rendered as Starlight asides: kind -> aside type. See Also
# becomes a quoted list; any other "Lead-in:" block is plain prose.
ASIDES = {"note": "note", "warning": "caution", "deprecated": "caution"}

# Doctests in SDK docstrings that fail on the cldk release these pages document, as griffe
# reads them. A page leaves each one out while the docstring still has it word for word, so a
# fixed docstring shows again. Find them with doctest.testmod(<module>).
FAILING_EXAMPLES = {
    # cldk 2.0.0 returns 'class A { }'.
    ">>> src = 'import java.util.List; class A { }'\n"
    ">>> TreesitterSanitizer(src).remove_unused_imports(src)\n"
    "''",
    # cldk 2.0.0 raises IndexError: the method takes a declaration ('void keep()'), not a name.
    ">>> src = 'class A { void keep(){} void drop(){} }'\n"
    ">>> TreesitterSanitizer(src).sanitize_focal_class('keep')\n"
    "'class A { void keep(){}  }'",
}

# --------------------------------------------------------------------------- #
# Page definitions: mirror the old docs/reference/python-api/*.md layout.
# Each page is a title plus sections: (heading, dotted module path) or
# (heading, dotted module path, options). A heading of None renders the module
# with no section heading. The module can be in cldk or in a package that cldk
# re-exports from (codeanalyzer). Options:
#   "members":    the names to render, in this order: classes, functions, class
#                 aliases, type aliases or constants. Default: the module's
#                 __all__, else its public classes, functions and class aliases.
#                 The section then opens with the import of these names from the
#                 module, so give the module that a reader imports them from.
#   "module_doc": False leaves out the module docstring (default True). Use it
#                 where the module docstring is a placeholder, maintainer notes
#                 or a repeat of the class docstring.
#   "init":       True shows how to construct each class: its signature line is
#                 the constructor call, and the constructor's Args follow the
#                 class docstring. Use it for classes that a reader constructs,
#                 not for the analysis facades that the CLDK factories return.
# --------------------------------------------------------------------------- #
PAGES: list[dict] = [
    {
        "file": "core.md",
        "title": "Core",
        "description": "Core CLDK API: the top-level entry point.",
        "sections": [
            (None, "cldk.core"),
            ("Analysis levels", "cldk.analysis",
             {"members": ["AnalysisLevel"], "module_doc": False}),
            ("Backend configuration", "cldk.analysis.commons.backend_config",
             {"members": ["CodeAnalyzerConfig", "PyCodeAnalyzerConfig", "TSCodeAnalyzerConfig",
                          "Neo4jConnectionConfig", "JavaBackend", "PyBackend", "TSBackend",
                          "cache_subdir"],
              "module_doc": False}),
        ],
    },
    {
        "file": "java.md",
        "title": "Java API",
        "description": "Program analysis for Java and related data models.",
        "sections": [
            ("Analysis", "cldk.analysis.java.java_analysis"),
            ("Schema", "cldk.models.java.models"),
            ("Projections", "cldk.models.java.projections", {"module_doc": False}),
            ("Enums", "cldk.models.java.enums"),
        ],
    },
    {
        "file": "python.md",
        "title": "Python API",
        "description": "Program analysis for Python and related data models.",
        "sections": [
            ("Analysis", "cldk.analysis.python.python_analysis"),
            ("Schema", "cldk.models.python"),
            # Field types of the schema models that cldk.models.python does not export.
            ("Schema field types", "codeanalyzer.schema.py_schema",
             {"members": ["PyCallArgument", "PyImportBinding", "PyEntrypointReport",
                          "PyRepositoryInfo"],
              "module_doc": False}),
        ],
    },
    {
        "file": "typescript.md",
        "title": "TypeScript API",
        "description": "Program analysis for TypeScript and related data models.",
        "sections": [
            ("Analysis", "cldk.analysis.typescript.typescript_analysis"),
            ("Schema", "cldk.models.typescript"),
        ],
    },
    {
        "file": "results.md",
        "title": "Results and errors",
        "description": "The result models that the query methods return, the default bounds, and the exceptions.",
        "sections": [
            ("Locating code", "cldk.analysis.commons.results",
             {"members": ["LocateResult", "CallableRef", "TypeRef", "ModuleRef", "BodyRef", "Span",
                          "Diagnostic"],
              "module_doc": False}),
            # PROV_CERTAINTY and prov_rank give the order behind PathHop.prov and FlowPath.weakest.
            ("Slices, paths and taint", "cldk.analysis.commons.results",
             {"members": ["SliceNode", "Slice", "FlowPaths", "FlowPath", "PathHop",
                          "PROV_CERTAINTY", "prov_rank", "TaintResult"],
              "module_doc": False}),
            ("Paged graphs", "cldk.analysis.commons.results",
             {"members": ["EdgePage", "BoundedResult"], "module_doc": False}),
            ("Entrypoint coverage", "cldk.analysis.commons.results",
             {"members": ["EntrypointCoverage"], "module_doc": False}),
            ("Default bounds", "cldk.analysis.commons.bounds",
             {"members": ["DEFAULT_PAGE_SIZE", "DEFAULT_MAX_NODES", "DEFAULT_DEPTH",
                          "DEFAULT_MAX_PATHS"],
              "module_doc": False}),
            ("Exceptions", "cldk.utils.exceptions",
             {"members": ["SelectorNotInGraph", "AmbiguousName", "CodeanalyzerUsageException",
                          "CodeanalyzerExecutionException", "CldkInitializationException",
                          "GraphSchemaMismatch"],
              "module_doc": False}),
        ],
    },
    {
        "file": "treesitter.md",
        "title": "Tree-sitter utilities",
        "description": "Tree-sitter parsers for Java and Python source code, and the Java source sanitizer.",
        "sections": [
            # The packages, not the defining modules: they re-export the classes.
            ("Java parser", "cldk.analysis.commons.treesitter",
             {"members": ["TreesitterJava"], "module_doc": False, "init": True}),
            ("Python parser", "cldk.analysis.commons.treesitter",
             {"members": ["TreesitterPython"], "module_doc": False, "init": True}),
            ("Java sanitizer", "cldk.utils.sanitization.java",
             {"members": ["TreesitterSanitizer"], "module_doc": False, "init": True}),
        ],
    },
    # NOTE: C analysis is intentionally omitted for now; it will return alongside
    # Go and Rust. Re-add a PAGES entry + a sidebar item to restore it.
]


# --------------------------------------------------------------------------- #
# reST -> Markdown, on the raw docstring before griffe parses it.
# --------------------------------------------------------------------------- #

# "text::" followed by an indented block is a reST literal block.
_LITERAL = re.compile(r"(?<=\S)::[ \t]*$")
# The one directive the SDK uses. griffe reads "Deprecated:" as an admonition.
_DEPRECATED = re.compile(r"^([ \t]*)\.\. deprecated::[ \t]*$")
# A Sphinx role, :class:`~cldk.x.Foo` or :meth:`bar`, also with its leading colon
# lost. Sphinx shows a "~" target by its last component and any other in full.
_ROLE = re.compile(
    r"(?<![\w`]):?(?:py:)?(?:class|meth|func|mod|attr|obj|data|exc|ref|term):`(~?)([^`]+)`"
)
_RST_LINK = re.compile(r"`([^`<]+?)\s*<([^`>]+)>`__?")
_DOUBLE_TICKS = re.compile(r"``([^`]+?)``")
_CODE_SPAN = re.compile(r"`[^`]+`")
_FENCE = re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$", re.M | re.S)
# A line opening with "+ " would start a Markdown list.
_PLUS_LINE = re.compile(r"^([ \t]*)\+ ", re.M)
# A prose dash, with the blanks around it and at most one line break either side.
# A "--" inside a word, a flag (--emit) or an arrow (-->) is not a dash.
_DASH = re.compile(
    r"(?P<pre>[ \t]*(?:\n[ \t]*)?)(?:—|–|(?<![\w<-])--(?![\w>-]))(?P<post>(?:[ \t]*\n)?[ \t]*)"
)
# Text between two dashes that keeps them from reading as one parenthetical: a
# paragraph break, the start of a list item, or the end of a sentence or clause.
_NOT_PARENTHETICAL = re.compile(r"\n[ \t]*\n|\n[ \t]*(?:[-*+]|\d+\.)[ \t]|[.?!:;](?=\s)")
# A bold run that opens its line or list item, so a dash after it ends a label.
_BOLD_LABEL = re.compile(r"(?:\A|\n)[ \t]*(?:(?:[-*+]|\d+\.)[ \t]+)?\*\*[^*\n]+\*\*\Z")
# A design-note reference that the reader cannot look up: brackets that hold only the SDK's
# spec ids, such as (E2), (J-15), (leg 1.5, E6-E8) or (the J-1 erratum), or an issue number
# with no repository, such as (#86).
_NOTE_ID = (r"(?:(?:the |spec |decision )?[A-Z]{1,2}-?\d+(?:[-/][A-Z]{1,2}-?\d+)?(?: erratum)?"
            r"|(?:spec )?leg \d+(?:\.\d+)?[a-z]?|Task \d+|cants#\d+ D\d+|#\d+)")
_DESIGN_REF = re.compile(rf"[ \t]+\({_NOTE_ID}(?:,[ \t]*{_NOTE_ID})*\)")
# A section title alone on its line, such as "Examples:" or "See Also:".
_TITLE = re.compile(r"[ \t]*[A-Z][A-Za-z ]*:[ \t]*$")
# The first line of a Raises item: an exception name, or names joined by "/", then ":".
_RAISES_ITEM = re.compile(r"`?[\w.]+`?(?:[ \t]*/[ \t]*`?[\w.]+`?)*[ \t]*:(?:[ \t]|$)")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _fence_literal_blocks(lines: list[str]) -> list[str]:
    """'text::' over an indented block becomes 'text:' and a ```python fence."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        deprecated = _DEPRECATED.match(line)
        if deprecated:
            out.append(f"{deprecated.group(1)}Deprecated:")
            continue
        if not _LITERAL.search(line):
            out.append(line)
            continue
        out.append(_LITERAL.sub(":", line))
        base, start = _indent(line), i
        while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > base):
            i += 1
        first, end = start, i
        while first < end and not lines[first].strip():
            first += 1
        while end > first and not lines[end - 1].strip():
            end -= 1
        if first == end:  # nothing indented follows: the colon alone is enough
            out.extend(lines[start:i])
            continue
        cut = min(_indent(code) for code in lines[first:end] if code.strip())
        pad = " " * base
        out += ["", f"{pad}```python"]
        out += [pad + code[cut:] if code.strip() else "" for code in lines[first:end]]
        out += [f"{pad}```", *lines[end:i]]
    return out


def _role(match: re.Match) -> str:
    tilde, target = match.groups()
    return f"`{target.rsplit('.', 1)[-1] if tilde else target}`"


def _line_break(dash: re.Match) -> str:
    """The line break (and the next line's indent) on either side of a dash, or ''."""
    for blank in dash.group("pre", "post"):
        if "\n" in blank:
            return blank[blank.index("\n"):]
    return ""


def _fix_dashes(text: str) -> str:
    """Rewrite prose dashes, which the site bans (the build turns '--' into one).

    '— X —' becomes '(X)', a dash after a bold label that opens its line or list
    item becomes ':', and any other becomes ','. A dash that ends a paragraph
    goes. Code spans are left alone, and each dash keeps its line break, so
    griffe still finds the sections.
    """
    spans: list[str] = []

    def hide(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE_SPAN.sub(hide, text)
    dashes = list(_DASH.finditer(text))
    out: list[str] = []
    pos = i = 0
    while i < len(dashes):
        dash = dashes[i]
        out.append(text[pos:dash.start()])
        nxt = dashes[i + 1] if i + 1 < len(dashes) else None
        between = text[dash.end():nxt.start()] if nxt else ""
        if nxt and not _NOT_PARENTHETICAL.search(between):
            close = _line_break(nxt) or (" " if nxt.group("post") else "")
            out += [(_line_break(dash) or " ") + "(", between, ")" + close]
            pos, i = nxt.end(), i + 2
            continue
        rest = text[dash.end():]
        brk = _line_break(dash)
        if not rest.strip() or rest.startswith("\n"):
            out.append(brk)
        else:
            out.append((":" if _BOLD_LABEL.search(text[:dash.start()]) else ",") + (brk or " "))
        pos, i = dash.end(), i + 1
    out.append(text[pos:])
    return re.sub("\x00(\\d+)\x00", lambda m: spans[int(m.group(1))], "".join(out))


def _prose(text: str) -> str:
    text = _DESIGN_REF.sub("", text)
    text = _RST_LINK.sub(r"[\1](\2)", text)
    text = _ROLE.sub(_role, text)
    text = _DOUBLE_TICKS.sub(r"`\1`", text)
    return _PLUS_LINE.sub(r"\1\\+ ", _fix_dashes(text))


def _open_sections(lines: list[str]) -> list[str]:
    """A blank line above a section title that ends an indented block. griffe reads a title
    with no blank line above it as text, and the SDK writes 'Examples:' right under the items
    of 'Notes:'."""
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and _TITLE.match(line) and out and out[-1].strip() \
                and _indent(out[-1]) > _indent(line):
            out.append("")
        out.append(line)
    return out


def _indent_raises(lines: list[str]) -> list[str]:
    """Indent a Raises continuation line that the SDK writes at the item indent. griffe reads
    such a line as an item of its own, and drops it when it has no 'exception:' part."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        if line.strip() != "Raises:":
            continue
        head, item, in_fence = _indent(line), None, False
        while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > head):
            line = lines[i]
            fence = line.lstrip().startswith("```")
            if line.strip() and not fence and not in_fence:
                if item is None:
                    item = _indent(line)
                elif _indent(line) == item and not _RAISES_ITEM.match(line.strip()):
                    line = " " * item + line  # griffe reads twice the item indent as a continuation
            in_fence ^= fence
            out.append(line)
            i += 1
    return out


def rst_to_markdown(text: str) -> str:
    """The Sphinx markup of an SDK docstring, rewritten as Markdown griffe can parse."""
    text = "\n".join(_fence_literal_blocks(text.split("\n")))
    parts, pos = [], 0
    for fence in _FENCE.finditer(text):
        parts += [_prose(text[pos:fence.start()]), fence.group(0)]
        pos = fence.end()
    parts.append(_prose(text[pos:]))
    return "\n".join(_indent_raises(_open_sections("".join(parts).split("\n"))))


@functools.cache
def sections(obj) -> list:
    """obj's docstring, rewritten to Markdown and parsed as Google style."""
    if not obj.docstring:
        return []
    return griffe.Docstring(
        rst_to_markdown(obj.docstring.value),
        lineno=obj.docstring.lineno,
        parent=obj,
        parser=griffe.Parser.google,
        parser_options=DOCSTRING_OPTIONS,
    ).parsed


def summary(obj) -> str:
    """The first paragraph of obj's docstring, on one line."""
    parsed = sections(obj)
    if not parsed or parsed[0].kind is not griffe.DocstringSectionKind.text:
        return ""
    return " ".join(parsed[0].value.strip().split("\n\n", 1)[0].split())


def first_sentence(text: str) -> str:
    """Text up to the first '. ' + capital letter or digit (bold or not) outside code spans
    and brackets."""
    depth, in_code = 0, False
    for i, char in enumerate(text):
        if char == "`":
            in_code = not in_code
        elif not in_code and char in "([":
            depth += 1
        elif not in_code and char in ")]":
            depth -= 1
        elif not in_code and not depth and text.startswith(". ", i):
            start = text[i + 2:].lstrip("*_")[:1]
            if start.isupper() or start.isdigit():
                return text[:i + 1]
    return text


def comment_doc(obj) -> str:
    """The first sentence of the Sphinx '#:' comment above an attribute. griffe does not
    read these comments, and the SDK writes its design notes after the first sentence."""
    try:
        lines = Path(obj.filepath).read_text(encoding="utf-8").split("\n")
    except (OSError, TypeError):
        return ""
    block: list[str] = []
    i = (obj.lineno or 0) - 2
    while i >= 0 and lines[i].lstrip().startswith("#:"):
        block.insert(0, lines[i].lstrip()[2:].strip())
        i -= 1
    paragraph = " ".join("\n".join(block).strip().split("\n\n", 1)[0].split())
    return first_sentence(rst_to_markdown(paragraph)) if paragraph else ""


# --------------------------------------------------------------------------- #
# Markdown output.
# --------------------------------------------------------------------------- #

_LIST_ITEM = re.compile(r"[ \t]*[-*+] ")


def outdent_lists(text: str) -> str:
    """Move a list indented under its lead-in line back to the lead-in's indent.

    reST reads 'Key features:' over an indented '- item' as a list; Markdown would
    fold the items into the paragraph.
    """
    lines = text.split("\n")
    in_fence = False
    i = 0
    while i < len(lines):
        line, prev = lines[i], lines[i - 1] if i else ""
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if (
            not in_fence
            and _LIST_ITEM.match(line)
            and prev.strip()
            and not _LIST_ITEM.match(prev)
            and _indent(line) > _indent(prev)
        ):
            floor, shift = _indent(line), _indent(line) - _indent(prev)
            while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) >= floor):
                lines[i] = lines[i][shift:]
                i += 1
            continue
        i += 1
    return "\n".join(lines)


def _cell(text) -> str:
    """Text for a markdown table cell: one line, pipes escaped."""
    return " ".join(str(text or "").split()).replace("|", "\\|")


# Name -> link to its entry, for the page being rendered: "#anchor" for an entry
# on that page, else "/reference/python-api/<page>/#anchor". build_body() fills it.
LINKS: dict[str, str] = {}

_NAME = re.compile(r"[A-Za-z_]\w*")


def type_link(annotation) -> str | None:
    """The link to the entry of the first name in annotation that has one."""
    return next((LINKS[name] for name in _NAME.findall(str(annotation)) if name in LINKS), None)


def _code(text, href: str | None = None) -> str:
    """Inline code, linked when href is given."""
    return f"[`{text}`]({href})" if href else f"`{text}`"


def _type_cell(annotation) -> str:
    return _code(_cell(annotation), type_link(annotation)) if annotation else ""


def _list_item(annotation, description: str) -> list[str]:
    """A list item whose continuation lines (nested lists, code) stay inside it. An annotation
    that joins names with ' / ' links each name to its own entry."""
    names = str(annotation).split(" / ") if annotation else []
    head = " / ".join(_code(name, type_link(name)) for name in names) + ": " if names else ""
    first, _, rest = description.partition("\n")
    # griffe strips the first line only; the rest keeps the docstring's hanging indent
    rest = outdent_lists(textwrap.dedent(rest)).split("\n") if rest else []
    return [f"- {head}{first}", *(f"  {line}" if line.strip() else "" for line in rest)]


def _see_also(contents: str) -> list[str]:
    """A See Also block as a quoted list, one item per entry."""
    entries: list[str] = []
    for line in contents.split("\n"):
        if not line.strip():
            continue
        if line[0].isspace() and entries:  # a wrapped entry
            entries[-1] += " " + line.strip()
        else:
            entries.append(re.sub(r"^[-*] ", "", line.strip()))
    return ["> **See Also**", ">", *(f"> - {entry}" for entry in entries), ""]


def is_public(name: str) -> bool:
    """Mirror the mkdocstrings `filters: ["!^_"]` option."""
    return not name.startswith("_")


def is_documented(member) -> bool:
    """Public, defined here, and not pydantic's own hooks (model_config, model_post_init)."""
    return not member.is_alias and is_public(member.name) and not member.name.startswith("model_")


def resolve(obj):
    """Resolve a griffe alias to its final target, tolerating failures."""
    if obj.is_alias:
        try:
            return obj.final_target
        except Exception:
            return None
    return obj


# A quoted name: the forward reference in List['PyCallArgument'].
_QUOTED_NAME = re.compile(r"""(['"])[A-Za-z_][\w.]*\1""")


def _unquote(expr) -> str:
    """The annotation as text, with each forward reference unquoted. A Literal keeps its strings."""
    if isinstance(expr, str):
        return expr[1:-1] if _QUOTED_NAME.fullmatch(expr) else expr
    if isinstance(expr, griffe.ExprSubscript) and str(expr.left).rsplit(".", 1)[-1] == "Literal":
        return str(expr)
    # A leaf (a name) yields itself.
    return "".join(str(part) if part is expr else _unquote(part) for part in expr.iterate(flat=False))


def fmt_annotation(annotation) -> str:
    if annotation is None:
        return ""
    return _unquote(annotation)


def literal(expr) -> str | None:
    """The repr of a plain literal expression (10_000 gives '10000'), else None."""
    try:
        value = ast.literal_eval(str(expr))
    except Exception:
        return None
    return repr(value) if isinstance(value, (bool, int, float, str, type(None))) else None


def constant_value(default) -> str | None:
    """The literal value behind a default that names a constant (DEFAULT_DEPTH -> '5')."""
    if not isinstance(default, griffe.ExprName):
        return None
    try:
        return literal(resolve(default.resolved).value)
    except Exception:
        return None


def fmt_parameters(func) -> list[str]:
    """The parameters as in a def, with the '/' and '*' markers: a parameter before
    '/' is passed by position only, one after '*' by keyword only."""
    kinds = griffe.ParameterKind
    params = [p for p in func.parameters if p.name not in ("self", "cls")]
    star_needed = not any(p.kind is kinds.var_positional for p in params)
    parts: list[str] = []
    for i, param in enumerate(params):
        if param.kind is kinds.keyword_only and star_needed:
            parts.append("*")
            star_needed = False
        prefix = {kinds.var_positional: "*", kinds.var_keyword: "**"}.get(param.kind, "")
        piece = f"{prefix}{param.name}"
        ann = fmt_annotation(param.annotation)
        if ann:
            piece += f": {ann}"
        if param.default is not None and not prefix:
            value = constant_value(param.default)
            piece += f" = {param.default if value is None else value}"
        parts.append(piece)
        last_positional = i + 1 == len(params) or params[i + 1].kind is not kinds.positional_only
        if param.kind is kinds.positional_only and last_positional:
            parts.append("/")
    return parts


def call_lines(name: str, params: list[str], tail: str = "") -> list[str]:
    """Code lines for name(params) + tail, one parameter per line when it is long."""
    line = f"{name}({', '.join(params)}){tail}"
    if len(line) <= SIGNATURE_WIDTH or not params:
        return [line]
    return [f"{name}(", *(f"    {p}," for p in params), f"){tail}"]


def signature(func) -> list[str]:
    """Code lines: the decorators that change how it is called, then the signature."""
    decorators = [f"@{label}" for label in CALL_DECORATORS if label in func.labels]
    returns = fmt_annotation(func.returns)
    return [*decorators, *call_lines(func.name, fmt_parameters(func), f" -> {returns}" if returns else "")]


def _default_note(param) -> str:
    """'Default: `DEFAULT_DEPTH` (5).' when the signature shows a constant's value and
    the description does not name the constant."""
    default = getattr(param, "default", None)
    value = constant_value(default)
    if value is None or default.name in param.description:
        return ""
    return f"Default: {_code(default.name, LINKS.get(default.name))} ({value})."


def render_docstring(obj, out: list[str], skip_attributes: bool = False, only: tuple = ()) -> None:
    """Render a parsed google-style docstring into readable markdown sections, or only the
    sections of the kinds in `only`."""
    K = griffe.DocstringSectionKind
    for section in sections(obj):
        kind = section.kind
        value = section.value
        if only and kind not in only:
            continue

        if kind == K.text:
            if value and value.strip():
                out.append(outdent_lists(value.strip()))
                out.append("")
        elif kind == K.parameters:
            out.append("**Parameters:**")
            out.append("")
            out.append("| Name | Type | Description |")
            out.append("| ---- | ---- | ----------- |")
            for p in value:
                desc = " ".join(filter(None, [_cell(p.description), _default_note(p)]))
                out.append(f"| `{p.name}` | {_type_cell(p.annotation)} | {desc} |")
            out.append("")
        elif kind == K.attributes:
            if skip_attributes:
                continue
            out.append("**Attributes:**")
            out.append("")
            out.append("| Name | Type | Description |")
            out.append("| ---- | ---- | ----------- |")
            for a in value:
                out.append(f"| `{a.name}` | {_type_cell(a.annotation)} | {_cell(a.description)} |")
            out.append("")
        elif kind in (K.returns, K.raises):
            out.append("**Returns:**" if kind == K.returns else "**Raises:**")
            out.append("")
            for r in value:
                out += _list_item(r.annotation, r.description)
            out.append("")
        elif kind == K.admonition:
            title, contents = section.title, outdent_lists(value.contents.strip())
            if value.kind in ASIDES:
                aside = ASIDES[value.kind]
                label = "" if title.lower() == aside else f"[{title}]"
                out += [f":::{aside}{label}", contents, ":::", ""]
            elif value.kind == "see-also":
                out += _see_also(contents)
            else:  # a "Lead-in:" line over an indented block is prose, not a callout
                out += [f"{title}:", contents, ""]
        elif kind == K.examples:
            # griffe splits the section into prose and doctests ('>>>' lines and their output)
            parts = [(part, text) for part, text in value
                     if text.strip() and text.strip() not in FAILING_EXAMPLES]
            if not parts:
                continue
            out += ["**Examples:**", ""]
            for part, text in parts:
                if part == K.examples:
                    out += ["```python", text.rstrip(), "```", ""]
                else:
                    out += [outdent_lists(text.strip()), ""]
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
    out += signature(func)
    out.append("```")
    out.append("")
    render_docstring(func, out)


def slug(text: str) -> str:
    """The id Astro gives a heading (github-slugger), for ASCII heading text."""
    return re.sub(r"[^\w\- ]", "", text.lower(), flags=re.ASCII).replace(" ", "-")


def render_method_index(cls, methods, out: list[str]) -> None:
    out.append("| Method | Summary |")
    out.append("| ------ | ------- |")
    for method in methods:
        anchor = slug(f"{cls.name}.{method.name}")
        out.append(f"| [`{method.name}`](#{anchor}) | {_cell(first_sentence(summary(method)))} |")
    out.append("")


def docstring_attributes(obj) -> dict:
    """name -> (annotation, description) from obj's docstring `Attributes:` section."""
    found = {}
    for section in sections(obj):
        if section.kind is not griffe.DocstringSectionKind.attributes:
            continue
        for a in section.value:
            names, annotation = [a.name], a.annotation
            # "start_line / end_line: ..." documents both; griffe reads "/ end_line" as a type
            if isinstance(annotation, str) and annotation.startswith("/"):
                names += re.findall(r"\w+", annotation)
                annotation = None
            for name in names:
                found[name] = (annotation, a.description)
    return found


def private_bases(cls) -> list:
    """The underscore classes that cls inherits from with no public class between, nearest first."""
    try:
        mro = cls.mro()
    except ValueError:
        return []
    bases = []
    for base in mro:
        if is_public(base.name):
            break
        bases.append(base)
    return bases


def public_bases(cls) -> list[str]:
    """cls's bases as written, each private base replaced by its own public bases."""
    resolved = {base.name: base for base in cls.resolved_bases}
    names: list[str] = []
    for base in map(str, cls.bases):
        private = not is_public(base.rsplit(".", 1)[-1]) and base in resolved
        names += [n for n in (public_bases(resolved[base]) if private else [base]) if n not in names]
    return names


def attribute_members(cls) -> list:
    """cls's attributes, after the ones it inherits from private bases (a reader cannot look
    those bases up), in the order of the model's fields: the base's first."""
    private = {base.path for base in private_bases(cls)}
    inherited = [resolve(m) for m in cls.inherited_members.values() if m.target.parent.path in private]
    members = [*inherited, *cls.members.values()]
    return [m for m in members if m is not None and m.kind is griffe.Kind.ATTRIBUTE and is_documented(m)]


def field_arguments(value) -> dict | None:
    """The keyword arguments of a pydantic Field(...) or a dataclass field(...) call, with a
    positional default as 'default'. None for any other value."""
    if not isinstance(value, griffe.ExprCall) or str(value.function).rsplit(".", 1)[-1] not in ("Field", "field"):
        return None
    arguments = {arg.name: arg.value for arg in value.arguments if isinstance(arg, griffe.ExprKeyword)}
    positional = [arg for arg in value.arguments if not isinstance(arg, griffe.ExprKeyword)]
    if positional and str(positional[0]) != "...":  # Field(...) is a required field
        arguments.setdefault("default", positional[0])
    return arguments


def default_value(member) -> str:
    """The value set in the class body: a field's default, or an enum member's value. For a
    Field(...) call, its default= or default_factory= argument."""
    if "class-attribute" not in member.labels or member.value is None:
        return ""
    arguments = field_arguments(member.value)
    if arguments is None:
        return str(member.value)
    if "default" in arguments:
        return str(arguments["default"])
    return f"{arguments['default_factory']}()" if "default_factory" in arguments else ""


def json_key(member) -> str:
    """'JSON key: `imports`.' for a Field(alias="imports"): the analyzer's JSON and model_dump()
    use the alias, not the attribute name. Else ''."""
    alias = (field_arguments(member.value) or {}).get("alias")
    try:
        key = ast.literal_eval(str(alias))
    except (ValueError, SyntaxError):
        return ""
    return f"JSON key: `{key}`." if isinstance(key, str) else ""


def attribute_rows(cls) -> list[tuple[str, str, str, str]]:
    """(name, type, default, description) per attribute: the member's own annotation and
    docstring, else the class docstring's `Attributes:` entry of the same name, else its
    '#:' comment."""
    documented: dict = {}
    for owner in [*reversed(private_bases(cls)), cls]:
        documented.update(docstring_attributes(owner))
    members = attribute_members(cls)
    if not members:
        return [(name, fmt_annotation(ann), "", desc) for name, (ann, desc) in documented.items()]
    rows = []
    for member in members:
        doc_annotation, doc_description = documented.pop(member.name, (None, ""))
        annotation = fmt_annotation(member.annotation) or fmt_annotation(doc_annotation)
        description = summary(member) or doc_description or comment_doc(member)
        description = " ".join(filter(None, [description, json_key(member)]))
        rows.append((member.name, annotation, default_value(member), description))
    for name in documented:
        print(f"warning: {cls.path} documents attribute {name!r}, which it does not define",
              file=sys.stderr)
    return rows


def is_enum(cls) -> bool:
    return any(str(base).rsplit(".", 1)[-1] in ("Enum", "IntEnum", "StrEnum") for base in cls.bases)


def inherited_notes(cls) -> list[str]:
    """Per private base that defines some of cls's attributes and has a docstring: the names,
    then the first paragraph of that docstring. A reader cannot look the base up, and the SDK
    explains these attributes there (_Spanned explains `code`)."""
    defined: dict[str, list[str]] = {}  # base path -> attribute names, in table order
    for member in attribute_members(cls):
        if member.parent.path != cls.path:
            defined.setdefault(member.parent.path, []).append(member.name)
    bases = {base.path: base for base in private_bases(cls)}
    out: list[str] = []
    for path, names in defined.items():
        text = summary(bases[path]) if path in bases else ""
        if text:
            out += [f"Inherited from `{bases[path].name}` ({', '.join(f'`{n}`' for n in names)}): {text}", ""]
    return out


def render_attributes(cls, out: list[str]) -> None:
    """The attribute table. An enum shows each member's value; another class adds a
    Default column when a field has one."""
    rows = attribute_rows(cls)
    if not rows:
        return
    enum = is_enum(cls)
    defaults = not enum and any(default for _, _, default, _ in rows)
    head = ["Name", "Value"] if enum else ["Name", "Type", *(["Default"] * defaults)]
    out.append("#" * PART_LEVEL + " Attributes")
    out.append("")
    out += inherited_notes(cls)
    out.append("| " + " | ".join([*head, "Description"]) + " |")
    out.append("| " + " | ".join("-" * len(cell) for cell in [*head, "Description"]) + " |")
    for name, annotation, default, description in rows:
        value = f"`{_cell(default)}`" if default else ""
        cells = [f"`{name}`", value] if enum else [f"`{name}`", _type_cell(annotation), *([value] * defaults)]
        out.append("| " + " | ".join([*cells, _cell(description)]) + " |")
    out.append("")


def render_class(cls, out: list[str], init: bool = False) -> None:
    """A class entry. With init, the code block shows the constructor call (after the class
    line when the class has public bases), and the constructor's Args follow the docstring."""
    bases = ", ".join(public_bases(cls))
    decl = [f"class {cls.name}({bases})"] if bases else ([] if init else [f"class {cls.name}"])
    constructor = resolve(cls.members["__init__"]) if "__init__" in cls.members else None
    if init:
        decl += call_lines(cls.name, fmt_parameters(constructor) if constructor else [])
    out.append(f"{'#' * CLASS_LEVEL} `{cls.name}`")
    out.append("")
    out.append("```python")
    out += decl
    out.append("```")
    out.append("")
    methods = [m for m in cls.members.values() if m.kind is griffe.Kind.FUNCTION and is_documented(m)]
    if len(methods) >= INDEX_MIN_METHODS:
        render_method_index(cls, methods, out)
    # The Attributes table below merges the docstring's `Attributes:` entries.
    render_docstring(cls, out, skip_attributes=True)
    if init and constructor is not None:
        kinds = griffe.DocstringSectionKind
        render_docstring(constructor, out, only=(kinds.parameters, kinds.raises))
    render_attributes(cls, out)
    if methods:
        out.append("#" * PART_LEVEL + " Methods")
        out.append("")
        for method in methods:
            render_function(method, METHOD_LEVEL, cls.name, out)


def alias_target(attr):
    """The class that a module attribute renames (TSCallEdge = TSCallGraphEdge), or None."""
    if attr.kind is not griffe.Kind.ATTRIBUTE or not isinstance(attr.value, griffe.ExprName):
        return None
    try:
        target = resolve(attr.value.resolved)
    except Exception:
        return None
    return target if target is not None and target.kind is griffe.Kind.CLASS else None


def _subscript(expr) -> tuple[str, list]:
    """The name and items of a subscript (Union[A, B] gives 'Union', [A, B]), else '', []."""
    if not isinstance(expr, griffe.ExprSubscript):
        return "", []
    items = expr.slice.elements if isinstance(expr.slice, griffe.ExprTuple) else [expr.slice]
    return str(expr.left), list(items)


def union_members(expr) -> list[str]:
    """The members of Union[A, B], also inside Annotated[...], else []."""
    left, items = _subscript(expr)
    left = left.rsplit(".", 1)[-1]
    if left == "Annotated":
        return union_members(items[0])
    return [str(item) for item in items] if left == "Union" else []


def collect_members(module, allow: list[str] | None = None) -> list[tuple]:
    """(name, object) pairs a module documents, in order.

    With an allowlist, exactly those names. Otherwise mirror mkdocstrings: follow
    ``__all__`` when defined (resolving re-exports to their targets), else document
    the public members defined in this module: classes, functions and the attributes
    that rename a class (``JGraphEdges = JCallGraphEdge``).
    """
    code = (griffe.Kind.CLASS, griffe.Kind.FUNCTION)
    if allow:
        names = allow
    elif module.exports:
        names = [e if isinstance(e, str) else getattr(e, "name", str(e)) for e in module.exports]
    else:
        names = [
            name for name, member in module.members.items()
            if is_public(name) and not member.is_alias
            and (member.kind in code or alias_target(member) is not None)
        ]
    members = []
    for name in names:
        member = module.members.get(name)
        target = resolve(member) if member is not None and is_public(name) else None
        if target is not None and target.kind in (*code, griffe.Kind.ATTRIBUTE):
            members.append((name, target))
        elif allow:
            print(f"warning: {module.path} has no member {name!r} to document", file=sys.stderr)
    return members


def render_module_attribute(name: str, attr, out: list[str]) -> None:
    """A module-level class alias, type alias or constant: its assignment, then what it names."""
    code = [f"{name} = {literal(attr.value) or attr.value}"]
    left, items = _subscript(attr.value)
    if len(code[0]) > SIGNATURE_WIDTH and items:  # one item per line, like a long signature
        code = [f"{name} = {left}[", *(f"    {item}," for item in items), "]"]
    out += [f"{'#' * CLASS_LEVEL} `{name}`", "", "```python", *code, "```", ""]
    target = alias_target(attr)
    targets = [target.name] if target is not None else union_members(attr.value)
    if targets:
        links = [_code(t, LINKS.get(t)) for t in targets]
        listed = links[0] if len(links) == 1 else f"{', '.join(links[:-1])} or {links[-1]}"
        out += [f"{'Alias of' if target is not None else 'One of'} {listed}.", ""]
    description = summary(attr) or comment_doc(attr)
    if description:
        out += [description, ""]


def import_lines(module: str, names: list[str]) -> list[str]:
    """A code block that imports names from module, wrapped like Black when it is long."""
    line = f"from {module} import {', '.join(names)}"
    if len(line) > SIGNATURE_WIDTH:
        return ["```python", f"from {module} import (", *(f"    {name}," for name in names), ")", "```", ""]
    return ["```python", line, "```", ""]


def render_module(module, out: list[str], options: dict) -> None:
    if options.get("module_doc", True):
        render_docstring(module, out)
    members = collect_members(module, options.get("members"))
    if not members:
        out.append("_No public symbols are exposed by this module._")
        out.append("")
        return
    if options.get("members"):  # a curated section: where its names import from
        out += import_lines(module.path, [name for name, _ in members])
    for name, member in members:
        if member.kind is griffe.Kind.CLASS:
            render_class(member, out, options.get("init", False))
        elif member.kind is griffe.Kind.FUNCTION:
            render_function(member, CLASS_LEVEL, "", out)
        else:
            render_module_attribute(name, member, out)


def get_object(root, dotted: str):
    """The object at a dotted path: in cldk, or in another package that the loader loaded."""
    obj = root.modules_collection[dotted]
    return resolve(obj) or obj


# Markers delimiting the auto-generated "Zone C" symbol reference. Authored
# content (frontmatter, overview, worked example) lives OUTSIDE these markers
# and is preserved across regeneration.
MARK_START = "<!-- CLDK:API:START -->"
MARK_END = "<!-- CLDK:API:END -->"
_LEADING_BLANK_LINES = re.compile(r"\A(?:[ \t]*\n)+")


# A GitHub badge linking to the python-sdk source, shown atop every API page.
GITHUB_BADGE = (
    "[![Source on GitHub]"
    "(https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)]"
    "(https://github.com/codellm-devkit/python-sdk)"
)


def cldk_version() -> str:
    """The version of the installed `cldk` these pages were generated from."""
    try:
        return importlib.metadata.version("cldk")
    except importlib.metadata.PackageNotFoundError:
        return ""


def version_badge(version: str) -> str:
    """A shields.io badge stating the python-sdk version, linked to PyPI."""
    if not version:
        return ""
    safe = version.replace("-", "--")
    return (
        f"[![cldk {version}]"
        f"(https://img.shields.io/badge/cldk-{safe}-3776AB?logo=pypi&logoColor=white)]"
        f"(https://pypi.org/project/cldk/{version}/)"
    )


def sections_of(root, page: dict):
    """(heading, module, options) per section of a page."""
    for heading, dotted, *options in page["sections"]:
        yield heading, get_object(root, dotted), options[0] if options else {}


def page_links(root, file: str) -> dict[str, str]:
    """Name -> link for every entry on every page, seen from the page `file`. A name with
    entries on several other pages and none on this one gets no link."""
    entries: dict[str, list[tuple[str, str]]] = {}
    for page in PAGES:
        for _, module, options in sections_of(root, page):
            for name, _ in collect_members(module, options.get("members")):
                entries.setdefault(name, []).append((page["file"], slug(name)))
    links = {}
    for name, found in entries.items():
        here = [anchor for page, anchor in found if page == file]
        if here:
            links[name] = f"#{here[0]}"
        elif len(found) == 1:
            page, anchor = found[0]
            links[name] = f"/reference/python-api/{page.removesuffix('.md')}/#{anchor}"
    return links


def build_body(root, page: dict, version: str = "") -> str:
    """The generated symbol reference body (no frontmatter)."""
    LINKS.clear()
    LINKS.update(page_links(root, page["file"]))
    badge = version_badge(version)
    header = f"{GITHUB_BADGE} {badge}" if badge else GITHUB_BADGE
    out: list[str] = [header, ""]
    if version:
        out += [f"_API reference generated from cldk {version}._", ""]
    for heading, module, options in sections_of(root, page):
        if heading:
            out.append(f"{'#' * SECTION_LEVEL} {heading}")
            out.append("")
        render_module(module, out, options)
    return "\n".join(out).strip()


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
            head = text.split(MARK_START, 1)[0].rstrip()
            tail = _LEADING_BLANK_LINES.sub("", text.split(MARK_END, 1)[1]).rstrip()
            # The authored text stays as written. Only the joins are set, with one newline at
            # the end as build_full_page writes, so a re-run changes nothing.
            return f"{head}\n\n{block}\n" + (f"\n{tail}\n" if tail else "")
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

    version = cldk_version()
    if version:
        print(f"generating from cldk {version}")
    else:
        print("warning: could not determine the cldk version (is it installed?)",
              file=sys.stderr)

    args.out.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        body = build_body(root, page, version)
        dest = args.out / page["file"]
        text = inject_or_create(dest, page, body)
        mode = "injected into" if dest.exists() and MARK_START in dest.read_text(encoding="utf-8") else "wrote"
        dest.write_text(text, encoding="utf-8")
        print(f"{mode} {dest} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
