---
title: "Results and errors"
description: "The result models that the query methods return, the default bounds, and the exceptions."
---

The query methods of `JavaAnalysis`, `PythonAnalysis` and `TypeScriptAnalysis` return
the result models on this page. The three languages use the same models. This page
also lists the default bounds and the errors that a call can raise.

The outputs on this page come from cldk 2.0.0 on Flask 3.1.3 and Commons CLI 1.7.0.
One table also shows a result on Zod 4.6.7. To run the samples, clone the two
projects. Then run the samples from the directory that holds the clones.

```bash
git clone --depth 1 --branch 3.1.3 https://github.com/pallets/flask.git
git clone --depth 1 --branch rel/commons-cli-1.7.0 https://github.com/apache/commons-cli.git
```

:::note[Before you run the samples]
- The samples build the analysis at the `system_dependency_graph`
  [analysis level](/reference/python-api/core/#choose-an-analysis-level). The first run
  builds the analysis and writes the cache. The next runs read the cache.
- The first run on each sample project can take several minutes, and it prints nothing
  while it runs.
- The first Python run makes a virtual environment under `flask/.codeanalyzer/python/`
  and installs Flask into it. So it needs network access.
- The Java samples need `pip install "cldk[java]"`, a JDK 11 or later in `JAVA_HOME`,
  and Maven on `PATH`.
- If `CLDK.python()` raises `RuntimeError: Could not find a suitable base Python
  interpreter`, set `SYSTEM_PYTHON` before the run. On macOS and Linux, run
  `export SYSTEM_PYTHON="$(python -c 'import sys; print(sys._base_executable)')"`.
  In Windows PowerShell, run
  `$env:SYSTEM_PYTHON = (python -c "import sys; print(sys._base_executable)")`.
  For `uv run` and `poetry run`, see [Install](/reference/python-api/core/#install).
:::

## Bounded results

Some answers are too large to return in one piece. So `get_cfg`, `get_cdg`, `get_ddg`,
the slice methods, the path methods and `taint` return a bounded result. If a bounded
result holds the whole answer, its `complete` field is `True`.

| Result | Returned by | When `complete` is `True` |
| --- | --- | --- |
| [`EdgePage`](#edgepage) | `get_cfg`, `get_cdg`, `get_ddg` | This page is the last page, and `next_cursor` is `None`. |
| [`Slice`](#slice) | `slice_forward`, `slice_backward`, `backward_cone` | `max_nodes` did not cut the set, and `total` is equal to `len(nodes)`. |
| [`FlowPaths`](#flowpaths) | `paths_between`, `call_paths_between` | `max_paths` did not cut the list. |
| [`TaintResult`](#taintresult) | `taint` | `max_paths` did not cut a list, and `unresolved` is empty. |

A bounded result also acts as its list of items: the edges, the nodes or the paths.
You can loop over it with `for item in result`, count the items with `len(result)`, and
read the first item with `result[0]`. When the result has no items, `bool(result)` is
`False`.

### Read all pages of an edge set

`total` is the size of the whole edge set. One page holds `page_size` edges or fewer. If
`complete` is `False`, pass `next_cursor` back as `cursor=` to get the next page.

```python
from cldk import CLDK
from cldk.analysis import AnalysisLevel

analysis = CLDK.python(
    project_path="flask",
    analysis_level=AnalysisLevel.system_dependency_graph,
)

page = analysis.get_ddg("Flask.make_response", page_size=200)
print(page.total, len(page), page.complete)   # 637 200 False

edges = list(page)
while not page.complete:
    page = analysis.get_ddg(
        "Flask.make_response", page_size=200, cursor=page.next_cursor
    )
    edges.extend(page)
print(len(edges))                             # 637
```

With the default `page_size` of 10000, these 637 edges fit in one page. Pass a cursor
back to the same method, for the same callable. A cursor from a different method or
callable raises `ValueError`.

### Read a slice

A `Slice` is a set of positions. `total` is the size of the whole set, and `nodes` holds
`max_nodes` positions or fewer. This block continues the previous one:

```python
sl = analysis.slice_forward("rv", within="Flask.make_response")
print(sl.total, len(sl), sl.complete)   # 40 40 True
print(sl.root.kind, sl.root.name)       # parameter rv

capped = analysis.slice_forward("rv", within="Flask.make_response", max_nodes=10)
print(capped.total, len(capped), capped.complete)   # 40 10 False
```

`complete` is about `max_nodes` only. A stop at the `depth` limit does not change
`complete`. The slice methods stop after 5 hops by default. To remove the hop limit,
pass `depth=None`.

`root` is the start position of the slice. If a slice has more than one start position,
`root` raises `ValueError`, and you must read `roots`. A `backward_cone` call with two
or more sinks returns such a slice.

### Default values of the bounds

If you do not pass a bound, the methods use these values from
`cldk.analysis.commons.bounds`:

| Constant | Value | Parameter | Methods |
| --- | --- | --- | --- |
| `DEFAULT_PAGE_SIZE` | `10000` | `page_size` | `get_cfg`, `get_cdg`, `get_ddg` |
| `DEFAULT_MAX_NODES` | `10000` | `max_nodes` | `slice_forward`, `slice_backward`, `backward_cone` |
| `DEFAULT_DEPTH` | `5` | `depth` | `slice_forward`, `slice_backward`, `backward_cone` |
| `DEFAULT_MAX_PATHS` | `10` | `max_paths` | `paths_between`, `call_paths_between`, `taint` |

These methods also take `depth`, but they have no hop limit by default (`depth=None`):
`reaches`, `flows_to_call`, `flows_to_argument`, `paths_between`, `call_paths_between`
and `taint`. In `taint`, `max_paths` applies to each pair, not to the whole call.

## Result types

This table lists each result model, the methods that return it, and the fields to read
first. All three languages return these models.

| Model | Returned by | Read first |
| --- | --- | --- |
| [`LocateResult`](#locateresult) | `locate`, and `locate_many` in a list | `callable`, `body`, `source`, `diagnostics` |
| [`CallableRef`](#callableref) | `LocateResult.callable` | `signature`, `name`, `class_signature` |
| [`TypeRef`](#typeref) | `LocateResult.type` | `signature`, `name` |
| [`ModuleRef`](#moduleref) | `LocateResult.module` | `path`, `module_name` |
| [`BodyRef`](#bodyref) | `LocateResult.body` | `kind`, `span` |
| [`Span`](#span) | `LocateResult.span`, `BodyRef.span` | `start` and `end` as `(line, column)` |
| [`Diagnostic`](#diagnostic) | The `diagnostics` lists, and `TaintResult.unresolved` | `code`, `message` |
| [`SliceNode`](#slicenode) | `resolve_callable`, `resolve_value`, and in a list `callers_of`, `callees_of`, `describe` | `callable`, `kind`, `name`, `file`, `line` |
| [`Slice`](#slice) | `slice_forward`, `slice_backward`, `backward_cone` | `nodes`, `total`, `complete`, `root` |
| [`EdgePage`](#edgepage) | `get_cfg`, `get_cdg`, `get_ddg` | `edges`, `total`, `next_cursor`, `complete` |
| [`FlowPaths`](#flowpaths) | `paths_between`, `call_paths_between` | `paths`, `complete` |
| [`FlowPath`](#flowpath) | The items of `FlowPaths` and `TaintResult` | `hops`, `weakest` |
| [`PathHop`](#pathhop) | The items of `FlowPath.hops` | `frm`, `to`, `via`, `var`, `prov` |
| [`TaintResult`](#taintresult) | `taint` | `paths`, `exhausted`, `unresolved`, `complete` |
| [`EntrypointCoverage`](#entrypointcoverage) | `get_entrypoint_coverage` | `frameworks_detected`, `unresolved`, `errors`, `diagnostics` |

The nodes of a slice or a path have no source text (`source` is `None`). To get the
text of the body nodes, for example `statement`, `call` and `branch` nodes, pass the
nodes to `describe`. The [ports](/guides/system-dependence/#the-four-ports-of-a-call)
of a callable or a call have no text, so `describe` leaves their `source` as `None`.
The ports are the `parameter`, `global`, `capture` and `argument` nodes, and the
`return` nodes whose `ref` holds `formal_out` or `actual_out`. Only Python has `global`
and `capture` nodes. The root of the slice sample above is a `parameter` node.

### What the `locate` fields hold

The fields of a `LocateResult` hold different values in each language. This table
shows one `locate` result for each language, at the `system_dependency_graph` analysis
level:

- Python: `locate("src/flask/app.py", 939)` on Flask 3.1.3.
- Java: `locate("src/main/java/org/apache/commons/cli/DefaultParser.java", 548)` on
  Commons CLI 1.7.0.
- TypeScript: `locate("src/v3/helpers/parseUtil.ts", 73)` on Zod 4.6.7, with
  `project_path="zod/packages/zod"`.

| Field | Python | Java | TypeScript |
| --- | --- | --- | --- |
| `callable.signature` | `src.flask.app.Flask.finalize_request` | `handleToken(java.lang.String)` | `src/v3/helpers/parseUtil.addIssueToContext` |
| `callable.class_signature` | `src.flask.app.Flask` | `org.apache.commons.cli.DefaultParser` | `None` |
| `type.signature` | `src.flask.app.Flask` | `org.apache.commons.cli.DefaultParser` | `type` is `None` |
| `module.module_name` | `app` | `org.apache.commons.cli` | `None` |
| `span.start`, `span.end` | `(922, 4)`, `(951, 23)` | `(543, 5)`, `(561, 5)` | `(72, 1)`, `(86, 2)` |
| `body.kind`, `body.span.start` | `call`, `(939, 19)` | `statement`, `(548, 13)` | `call`, `(73, 23)` |

Lines start at 1 in all three languages. Columns start at 0 on Python, and at 1 on
Java and TypeScript. The `Span` and `LocateResult` references below say that columns
start at 0. On Java and TypeScript, this is not correct. With the local backend, use
`span.bytes` to cut the text of a span out of the file. In all three languages,
`data[start:end]` is the text, where `data` holds the bytes of the file.

### Java: make the callable key

On Python and TypeScript, `CallableRef.signature` is the full key that
`get_method_bodies` takes. On Java, `signature` holds only the member signature, and
`class_signature` holds the type. To make the Java key, join the two with a dot:

```python
from cldk import CLDK
from cldk.analysis import AnalysisLevel

analysis = CLDK.java(
    project_path="commons-cli",
    analysis_level=AnalysisLevel.system_dependency_graph,
)

hit = analysis.locate("src/main/java/org/apache/commons/cli/DefaultParser.java", 548)
ref = hit.callable
print(ref.signature)         # handleToken(java.lang.String)
print(ref.class_signature)   # org.apache.commons.cli.DefaultParser

print(len(analysis.get_method_bodies([ref.signature])))   # 0
key = f"{ref.class_signature}.{ref.signature}"
print(len(analysis.get_method_bodies([key])))             # 1
```

With the member signature alone, `get_method_bodies` returns an empty result and shows
no error. The `LocateResult` reference below says that `callable.signature` is the key
for `get_method_bodies`. On Java, this is not correct.

## Read a taint result

`taint()` searches from each source to each sink in one call. For each pair, the result
holds one of three answers.

| You see | It means |
| --- | --- |
| A path in `paths` that joins the pair | The graph holds a flow from the source to the sink. `weakest` tells you how certain the path is. |
| The pair in `exhausted` | The search went to the end of the graph and found no path. |
| The pair in neither list | There is no answer for the pair. You passed `depth`, or `unresolved` names the pair. |

`complete` is one flag for the whole call. If `complete` is `False`, read `unresolved`
to find the cause. If `unresolved` is empty, `max_paths` cut the paths of a pair. Even
when `complete` is `True`, a pair in `exhausted` does not prove that the program has no
flow. The next section tells you why.

This sample tests one source against two sinks:

```python
from cldk import CLDK
from cldk.analysis import AnalysisLevel

analysis = CLDK.java(
    project_path="commons-cli",
    analysis_level=AnalysisLevel.system_dependency_graph,
)

result = analysis.taint(
    sources=[("token", "DefaultParser.handleToken")],
    sinks=[
        ("token", "DefaultParser.handleLongOption"),
        ("width", "HelpFormatter.setWidth"),
    ],
)
print(len(result.paths))     # 1
print(result.exhausted)      # [('token', 'width')]
print(result.complete)       # True
print(result.unresolved)     # []

path = result.paths[0]
print(path.hops[-1].to.callable)
# org.apache.commons.cli.DefaultParser.handleLongOption(java.lang.String)
print(path.weakest.via, path.weakest.prov)   # data ['ssa']
```

The path joins `token` in `handleToken` to `token` in `handleLongOption`. The second
pair is in `exhausted`, because no path in the graph joins `token` to `width`.

### `exhausted` describes the graph, not the program

A pair in `exhausted` tells you that the graph holds no path for it. It does not prove
that the program has no flow. Know these limits:

- If you pass `depth`, `exhausted` is always empty.
- In cldk 2.0.0, no backend adds an `unresolved_dispatch` diagnostic. The only code
  that can be in `unresolved` is `degenerate_pair`. It marks a pair whose source and
  sink are the same position, and CLDK skips that pair. So a flow through a call that
  the analyzer did not resolve can put its pair in `exhausted`, with `complete` set to
  `True`. The `TaintResult` and `Diagnostic` references below name both codes, but only
  `degenerate_pair` occurs.
- On Python, a pair can be in `exhausted` although the program has a flow. For example,
  on line 939 of `src/flask/app.py`, `finalize_request` passes `rv` to `make_response`.
  But
  `taint(sources=[("rv", "Flask.finalize_request")], sinks=[("rv", "Flask.make_response")])`
  puts this pair in `exhausted`, with `complete` set to `True`. The result is the same on
  codeanalyzer-python 1.5.3, which cldk 2.0.0 pins, and on 1.5.4. Version 1.5.4 fixes a
  defect of 1.5.3 that stops some value flow at a call
  ([codeanalyzer-python#220](https://github.com/codellm-devkit/codeanalyzer-python/issues/220)),
  but it does not link this flow. For the flows that 1.5.4 links, and for the install
  steps, see
  [What the pinned Python backend does not link](/guides/system-dependence/#what-the-pinned-python-backend-does-not-link).

For the sanitizers and a longer example, see [Taint analysis](/guides/taint/).

## Errors you can see

CLDK raises six exceptions of its own. Import them from `cldk.utils.exceptions`:

```python
from cldk.utils.exceptions import (
    AmbiguousName,
    CldkInitializationException,
    CodeanalyzerExecutionException,
    CodeanalyzerUsageException,
    GraphSchemaMismatch,
    SelectorNotInGraph,
)
```

| Exception | Base class | When CLDK raises it | What to do |
| --- | --- | --- | --- |
| [`CldkInitializationException`](#cldkinitializationexception) | `Exception` | `project_path` does not exist or is not a directory, or `CLDK.java()` gets no `project_path`. The 1.x call `CLDK(language=...).analysis(source_code=...)` also raises it, because cldk 2.0 has no `source_code` mode. | Pass the path of an existing project directory. For one string of code, use the [tree-sitter utilities](/reference/python-api/treesitter/). |
| [`CodeanalyzerUsageException`](#codeanalyzerusageexception) | `Exception` | A dataflow method, for example `get_cfg`, runs on an analysis below `program_dependency_graph`. On Java, a dataflow method also raises it for an implicit constructor, for example `BasicParser.<init>()`, because it has no body. | Build the analysis again at `system_dependency_graph`, as the message says. On TypeScript, also pass `eager=True` once, or the old analysis level comes back. An implicit constructor has no dataflow, so use a callable that the source declares. |
| [`CodeanalyzerExecutionException`](#codeanalyzerexecutionexception) | `Exception` | The analyzer or a backend fails. [Causes of `CodeanalyzerExecutionException`](#causes-of-codeanalyzerexecutionexception) lists the causes. | Read the message. Then find the cause in that list. |
| [`SelectorNotInGraph`](#selectornotingraph) | `ValueError` | A name, a path, or a value of `paths=`, `module=` or `roots=` matches nothing in the analysis. Below `system_dependency_graph`, Python and TypeScript also raise it for a correct value name. | Copy the name from the analysis, for example from `get_classes()`. If the name is correct, check the [analysis level](#errors-from-a-low-analysis-level). `missing` lists the values that matched nothing. |
| [`AmbiguousName`](#ambiguousname) | `ValueError` | A name matches more than one callable or value. | Use one name from `candidates`. `resolve_callable`, `callers_of` and `callees_of` also take `in_class=` and `in_module=`. `get_cfg`, `get_cdg` and `get_ddg` take only `in_class=`, although the message also names `in_module=`. For a method that takes `within=`, pass a longer `within=`. |
| [`GraphSchemaMismatch`](#graphschemamismatch) | `RuntimeError` | A Neo4j backend connects to a graph that it cannot read. For example, the database is empty, an old analyzer emitted the graph, or `application_name` is wrong. | Make sure that `application_name` is correct. Then emit the graph again with codeanalyzer-python 1.5.0 or later, codeanalyzer-java 3.2.0 or later, or codeanalyzer-typescript 1.5.2 or later. |

`SelectorNotInGraph` and `AmbiguousName` carry the names as data. This sample reads them:

```python
from cldk import CLDK
from cldk.analysis import AnalysisLevel
from cldk.utils.exceptions import AmbiguousName, SelectorNotInGraph

analysis = CLDK.python(
    project_path="flask",
    analysis_level=AnalysisLevel.system_dependency_graph,
)

try:
    analysis.resolve_callable("make_response")
except AmbiguousName as e:
    print(e.candidates)
# ['src.flask.app.Flask.make_response', 'src.flask.helpers.make_response']

try:
    analysis.get_symbol_table(paths=["src/flask/nope.py"])
except SelectorNotInGraph as e:
    print(e.kind, e.missing, e.requested)
# paths ['src/flask/nope.py'] 1
```

### Causes of `CodeanalyzerExecutionException`

| Cause | What to do |
| --- | --- |
| You call `CLDK.java()`, and the `java` extra is not installed. | Run `pip install "cldk[java]"`. |
| You pass a [`Neo4jConnectionConfig`](/reference/python-api/core/#neo4jconnectionconfig), and the `neo4j` driver is not installed. | Run `pip install "cldk[neo4j]"`. |
| The `Neo4jConnectionConfig` has no `application_name`, and you pass no `project_path`. | Pass `application_name`. If you pass `project_path`, `application_name` defaults to the name of the project directory. |
| `<project>/.codeanalyzer` holds a Java cache from cldk 1.5.0. | Pass `eager=True` once, or delete the `.codeanalyzer` directory. The message names `eager_analysis=True`, but `CLDK.java()` has no such keyword. |
| You pass `target_files=` to `CLDK.java()`. codeanalyzer-java 3.3.3 rejects it, and the message shows only the `java` command line. | Leave out `target_files=`. |
| On Java, a value method, for example `slice_forward` or `taint`, runs on a `program_dependency_graph` analysis. | Build the analysis at `system_dependency_graph`. See [Errors from a low analysis level](#errors-from-a-low-analysis-level). |
| You call a Java CRUD method, for example `get_all_crud_operations()`. | cldk 2.0.0 has no replacement for these methods. |

### Errors from a low analysis level

Some errors come from an analysis level that is too low:

- Below `program_dependency_graph`, the dataflow methods, for example `get_cfg` and
  `slice_forward`, raise `CodeanalyzerUsageException`. On Python and TypeScript,
  `resolve_value` and `taint` raise `SelectorNotInGraph` instead.
- At `program_dependency_graph`, on Python and TypeScript, the methods that take a value
  name raise `SelectorNotInGraph`, even for a correct name. An example message is
  `1 of 1 value not in graph: 'rv'`. On Java, `slice_forward`, `flows_to_call`,
  `flows_to_argument`, `paths_between` and `taint` raise
  `CodeanalyzerExecutionException`, and `slice_backward` returns an empty slice. The
  Java message names codeanalyzer-java 3.0.3, but the cause is the analysis level.

For these methods, build the analysis at `system_dependency_graph`.

### Standard Python errors

Some mistakes raise a standard Python error. `SelectorNotInGraph` and `AmbiguousName`
are subclasses of `ValueError`, so an `except ValueError` block also catches them.

| Error | Examples | What to do |
| --- | --- | --- |
| `ValueError` | An unknown `analysis_level` name. `page_size=0` or `depth=0`. A `cursor` from a different method or callable, or a string that is not a cursor. `root` on a slice with more than one root. `CLDK.python()` with no `project_path`. | Use a level name from the message. Pass a bound of 1 or more. Pass the `next_cursor` from the same method and callable. Read `roots` instead of `root`. Pass `project_path`. |
| `TypeError` | A keyword-only option given by position, for example `slice_forward("rv", "Flask.make_response")`. One string for `paths=`, `roots=`, `sources=` or `sinks=`, where the method takes a list. `CLDK.typescript()` with no `project_path`. | Give the option by keyword, for example `within="Flask.make_response"`. Pass a list, for example `paths=["src/flask/app.py"]`. For `sources=` and `sinks=`, pass a list of `(name, within)` pairs. Pass `project_path`. |
| `KeyError` | `get_source()` with a node id that names nothing. On Java, `get_java_compilation_unit()` with a path that the analysis does not hold. | Pass a `node_id` or a callable `ref` from a result. Copy the path from `get_symbol_table()`. |
| `neo4j.exceptions.ServiceUnavailable` | No Neo4j server answers at the `uri` of `Neo4jConnectionConfig`. | Start the Neo4j server, or correct the `uri`. |

## API reference

The reference below comes from the docstrings of cldk 2.0.0.

:::note[About the docstrings below]
Some docstrings below hold design notes for the SDK maintainers, for example labels such
as E5 or D7 and measurements on other applications. You do not need these notes to use
the API. The sections above contain the facts that you need.
:::

<!-- CLDK:API:START -->

<!-- AUTO-GENERATED by scripts/gen_api_docs.py, do not edit by hand. -->

[![Source on GitHub](https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)](https://github.com/codellm-devkit/python-sdk) [![cldk 2.0.0](https://img.shields.io/badge/cldk-2.0.0-3776AB?logo=pypi&logoColor=white)](https://pypi.org/project/cldk/2.0.0/)

_API reference generated from cldk 2.0.0._

## Locating code

```python
from cldk.analysis.commons.results import (
    LocateResult,
    CallableRef,
    TypeRef,
    ModuleRef,
    BodyRef,
    Span,
    Diagnostic,
)
```

### `LocateResult`

```python
class LocateResult(BaseModel)
```

Resolve a `file:line` position to its enclosing callable, source in hand.

The outcomes below must stay distinguishable, an ambiguous empty is a defect (see the module
docstring): a caller must be able to tell "inside a callable" apart from "a real position at
module scope" apart from "the gap between two callables" (also module scope, and never snapped
to the nearest callable) apart from "this file was never analysed".

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `body` | [`BodyRef \| None`](#bodyref) |  | The innermost body node containing the position, as a `BodyRef`, if the graph has one that precise. `None` does not mean "not found", see `callable`/`diagnostics` for that. |
| `node_id` | `str \| None` | `None` | `body`'s identifier for `get_source`, or `None` exactly when `body` is `None` (it is the same value as `body.id`, kept as a field of its own because it is published contract). It is the analyzer's own id for that node (`"<callable can:// id>@<body key>"`), read off the graph where the backend can and composed the emitter's way where it cannot, **an opaque handle, not a string to parse or build**. Treat it as something to pass back, and address a callable by its `callable.signature` instead, the same key `get_method_bodies` uses. |
| `callable` | [`CallableRef \| None`](#callableref) |  | The enclosing callable, or `None` if the position is not inside one (module scope) or the file isn't in the graph at all. |
| `type` | [`TypeRef \| None`](#typeref) |  | The class owning `callable`, or `None` for a module-level function/callable with no owning class. |
| `module` | [`ModuleRef`](#moduleref) |  | The module the position was asked about, always present, even when unresolved. |
| `source` | `str` |  | The slice a caller will ask for next: the enclosing callable's text, or the module's text when there is no enclosing callable. Never `None`, "absence is never null" (see `Diagnostic`); an unrecoverable body is an empty string, not a missing field. Backends differ on one case and say so rather than faking it: the Neo4j backend cannot produce *module* text (`:PyModule` carries no `source` property, only `file_key` / `module_name` / `content_hash` / `last_modified` / `file_size`), so a module-scope result there is `""` plus a `module_source_unavailable` diagnostic. Callable text is available on both. |
| `span` | [`Span`](#span) |  | The span the `source` slice covers. Which of its fields are meaningful depends on the backend, because they carry different data: the local backend returns the analyzer's real span (1-based line, 0-based column, and UTF-8 byte offsets into the module source), while the Neo4j graph projects only `start_line` / `end_line` on `:PyCallable` and `:PyBodyNode`, so over Neo4j the line components are real and the columns and `bytes` are `0` placeholders, never offsets to slice with. |
| `diagnostics` | [`list[Diagnostic]`](#diagnostic) | `[]` | Empty when the position resolved inside a callable; `module_scope` for a real position with no enclosing callable (joined by `module_source_unavailable` when the backend cannot supply the module text); `file_not_in_graph` when the path names no analysed module. |

### `CallableRef`

```python
class CallableRef(BaseModel)
```

A lightweight handle on a callable, enough to call back into `get_method` or
`get_method_bodies` without re-walking the symbol table.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `signature` | `str` |  |  |
| `name` | `str` |  |  |
| `class_signature` | `str \| None` | `None` |  |

### `TypeRef`

```python
class TypeRef(BaseModel)
```

A lightweight handle on a class/type, the `callable`'s owner, when it has one.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `signature` | `str` |  |
| `name` | `str` |  |

### `ModuleRef`

```python
class ModuleRef(BaseModel)
```

A lightweight handle on a module, enough to name it and fetch it again.

Always present on a `LocateResult`, even when the position couldn't be resolved any
further (a `file_not_in_graph` result still echoes the path the caller asked about).

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `path` | `str` |  |  |
| `module_name` | `str \| None` | `None` |  |

### `BodyRef`

```python
class BodyRef(BaseModel)
```

A handle on one node inside a callable's body, the statement, call or branch a position
landed on, in the vocabulary every analyzer shares.

Carries only what both analyzers emit for such a node. The Python-schema `BodyNode` this
replaced on `LocateResult` also carried Python-shaped dataflow detail (`of`,
`parent`, `arguments`, the call-site facets), none of which a TypeScript body node speaks
in the same spelling; a caller that needs it addresses the node by `id` and asks the
language's own accessors.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  | The analyzer's own id for the node (`"<callable can:// id>@<body key>"`), **opaque**. The same value `LocateResult.node_id` carries, and the handle `get_source` takes. Pass it back; do not parse it and do not build one. |
| `kind` | `str` |  | The node's kind in the analyzer's already-English spelling, `statement`, `call`, `branch`, `loop`, `raise`, `handler` and the synthetic `entry` / `exit` bookends (the vocabulary `SliceNode.KINDS` pins). |
| `span` | [`Span \| None`](#span) | `None` | The node's own source region, or `None` when it has none: the synthetic analysis vertices (`@entry` / `@exit` / a formal parameter) are dataflow positions, not regions in the file, and a fabricated zero span would read as "line 0". |
| `callee` | `str \| None` | `None` | On a `call` node, the id of what it resolves to; `None` everywhere else and on a call that never resolved. This is the sanctioned null-to-id slot, not an absence to paper over, measured across real applications, one call site in four resolves nothing. |

### `Span`

```python
class Span(BaseModel)
```

Where something lives in source, in the one spelling this whole surface speaks.

`start` / `end` are `[line, column]` (1-based line, 0-based column) and `bytes` are
UTF-8 offsets into the owning module's source, the shape *both* analyzers already emit
(`codeanalyzer-python`'s `Span`, `codeanalyzer-typescript`'s `TSSpan`). It is declared
here rather than borrowed from one of them because these results are language-neutral, and a
span is the one attribute every language's nodes carry.

`from_attributes` is load-bearing, not decoration: it is what lets a backend hand its own
analyzer's span object straight to a `BodyRef` or a `LocateResult` and have it
validate field by field, so no backend converts by hand and no field goes missing in the
handover. It does **not** make this class interchangeable with either analyzer's, the reverse
direction (this class into a `Py*` model's `span` field) is a `ValidationError`, which is
why `cldk.models.python.Span` stays codeanalyzer-python's own class rather than being
replaced by this one.

Which fields are *meaningful* depends on the backend, and they say so rather than fabricating:
a Neo4j projection carrying only `start_line` / `end_line` rehydrates the columns and
`bytes` as `0` placeholders, never offsets to slice with (see `LocateResult`).

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `start` | `tuple[int, int]` |  |
| `end` | `tuple[int, int]` |  |
| `bytes` | `tuple[int, int]` |  |

### `Diagnostic`

```python
class Diagnostic(BaseModel)
```

A structured, non-`None` explanation for why a query came back empty or uncertain.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `code` | `Literal['no_match', 'ambiguous', 'unknown_callable', 'unknown_param', 'did_you_mean', 'level_too_low', 'module_scope', 'file_not_in_graph', 'module_source_unavailable', 'unresolved_dispatch', 'graph_schema_mismatch', 'entrypoint_report_unavailable', 'degenerate_pair']` |  | The fixed vocabulary of reasons a query can fail to produce a definite answer. |
| `message` | `str` |  | A human-readable explanation, safe to surface directly to an agent or user. |
| `suggestions` | `list[str]` | `[]` | Declared by the leg-1 spec for a `did_you_mean` diagnostic and **never populated**. E8 put typo-tolerant matching out of scope "not in the resolver, not in the error path", so nothing in the SDK constructs a `Diagnostic` with suggestions or with `code="did_you_mean"`; the codes actually emitted are `file_not_in_graph`, `module_scope`, `module_source_unavailable`, `entrypoint_report_unavailable`, and (since `taint()`) `unresolved_dispatch` and `degenerate_pair`. The field and the code stay because both are part of a published model contract (`docs/agent-api-reference.md`) that a caller may already destructure; removing either is a separate, breaking change. |

## Slices, paths and taint

```python
from cldk.analysis.commons.results import (
    SliceNode,
    Slice,
    FlowPaths,
    FlowPath,
    PathHop,
    PROV_CERTAINTY,
    prov_rank,
    TaintResult,
)
```

### `SliceNode`

```python
class SliceNode(BaseModel)
```

One addressed position in a program: what a name resolved to, in the caller's vocabulary.

The unit the addressing layer hands back, and the unit the traversals built on
it will carry. Every field is something a person or an agent already understands, a path, a
line, a dotted callable name, a variable name. Nothing here requires knowing the analyzer's id
grammar, and nothing here carries an ordinal: a parameter is `kind="parameter"` with
`name="invoice_id"`, never `formal_in:1` (E7, "an interface requiring the caller to know
that `self` occupies slot 0 will be got wrong by a model and misread by a person").

`ref` is the one exception, and it is deliberately opaque. The graph addresses nodes by a
`can://` id; the caller must never have to read, parse or assemble one, because that
would mean reimplementing the analyzer's id grammar in the SDK and breaking silently the day it
changes. So the id rides here, in the same vocabulary as
`LocateResult.node_id` (the analyzer's own id, read off the graph, joinable back to the
node it names) and is documented as something to *pass back*, not to read.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `KINDS` | `frozenset[str]` | `frozenset({'parameter', 'global', 'capture', 'argument', 'return', 'statement', 'call', 'branch', 'loop', 'raise', 'handler', 'entry', 'exit', 'callable', 'external'})` | Every value `kind` can take, in the caller's vocabulary. |
| `file` | `str` |  | The module's repo-relative path, the same vocabulary as `locate().module.path`, `PyCallableOverview.path` and the symbol table's keys. |
| `line` | `int` |  | 1-based. For a position with no source region of its own (a parameter is a synthetic dataflow vertex, not a span in the file) this is the enclosing callable's first line, which is where a reader would go looking for it. |
| `callable` | `str` |  | The enclosing callable's dotted signature. Never a `can://` id. |
| `kind` | `str` |  | What kind of position this is, one of `KINDS`. The three that *enter* a callable are `parameter`, `global` (a module global the callable reads, 84% of entering values on a real application, so collapsing them into `parameter` mislabelled most of the domain) and `capture` (a name closed over from an enclosing scope). Around a call site: `argument` (the value bound to a callee's parameter, named for that parameter) and `return` (a value coming back out of a call, or the callable's own result, unnamed). The body kinds pass through in the analyzer's already-English spelling: `statement`, `call`, `branch`, `loop`, `raise`, `handler`, and the synthetic `entry` / `exit` bookends. Finally `callable` (the callable itself, what `resolve_callable` returns) and `external` (a call target that was never analysed, from `callees_of` and the call-graph paths). Fifteen in all, pinned by a live test against the graph's own `:PyBodyNode.kind` vocabulary. |
| `name` | `str \| None` |  | The value's name where it has one (a parameter, a global, an argument), `None` where it does not (a statement). Always the readable identifier as written in the source, never the analyzer's internal spelling of it. |
| `defined_in` | `str \| None` | `None` | For a `global`, the module it is defined in (`"payment"`), the same vocabulary as `ModuleRef.module_name`. `None` for everything else, whose defining scope is the enclosing callable in `callable`. |
| `source` | `str \| None` | `None` | The text, when the backend can produce it; `None` when it cannot. Whether a Neo4j graph carries text below callable granularity is the projection's choice, so it depends on the language: Java's does since codeanalyzer-java 3.2.0 and answers the same text as its local backend, Python's does not and is `None` there for anything finer (see `LocateResult`). |
| `ref` | `str` |  | The analyzer's own id for this node, **opaque**. Pass it back; do not parse it, and do not build one. The one sanctioned use is `get_source`, and that round-trips for a `kind="callable"` ref on either backend. A value's ref does **not**: `parameter` / `global` / `capture` are dataflow vertices with no source span, so neither backend has text to return for one. |

### `Slice`

```python
class Slice(BoundedResult)
```

A set of positions reached by one traversal, with the size of the whole answer alongside.

**A slice is a set**: no duplicates, and the order carries no meaning beyond making the
cap deterministic, it is the node-id order, the one total order both backends can compute
without agreeing on a traversal. A *path* is the sequence, and it is a different accessor
returning a different type; neither is derived from the other, because a cone of 10,000 nodes
contains millions of distinct paths.

**Why this caps where** `EdgePage` **pages.** The sibling per-callable accessors
paginate, on the ruling that a cap discards edges a caller may need. Slices measured on
odoo-slim-19 land the other way, for two reasons:

* **The distribution is bimodal, not long-tailed.** Over 200 random `formal_in` seeds,
  `slice_backward` has median 1 and p95 195,790 (max 196,117); restricted to the 150 seeds
  that actually have callers, the median is 195,786. `slice_forward` over the same seeds is
  median 1, p95 440,270, max 440,662, of 885,218 body nodes in the whole application. A slice
  is either a handful of nodes or a fifth to a half of the program, with almost nothing in
  between, and "page 3 of 20" of the second kind answers no question anyone asked.
* **A slice cursor could not be cheap.** An `EdgePage` cursor is a keyset position in
  an order the database already maintains, so each page costs one bounded query. A slice *is*
  the traversal, so resuming it means re-running the whole closure, the cost is in computing
  the set, not in shipping it.

So the cap stays, and `total` is what keeps it from being the silent bound E5 forbids:
a capped result reports the size of the whole slice, so "here are 10,000 of 195,784" arrives
in one call and the caller learns the question was too broad instead of walking twenty pages
to find out. The way to a *complete* answer is a narrower question, `depth=` bounds the
traversal rather than the response, and what comes back is the whole slice of that question.

**And that is why the traversals bound themselves by default** (five hops,
`DEFAULT_DEPTH`). "Here are 10,000 of 195,784" is honest
but it is still an unprincipled 5% of a closure, and a caller who never passes `depth=` was
getting it every time. Bounded, the same call answers completely: over 120 connected seeds
measured in both directions, no slice at five hops reaches the cap. A slice you are reading is
therefore normally one where `complete` is `True` and `total` is the size of
`nodes`, the incomplete kind is now what you get when you ask for `depth=None`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `nodes` | [`list[SliceNode]`](#slicenode) |  | The positions in the slice, ordered by `SliceNode.ref` and including the seed(s). `source` is `None` on every one of them: a slice answers *where*, and hydrating text a caller has not chosen to read is the cost E4 exists to avoid, pass the ones that matter to `describe()`. |
| `roots` | [`list[SliceNode]`](#slicenode) |  | What the traversal started from, the resolved seed(s), also present in `nodes`. A list because `backward_cone` takes several sinks; see `root` for the singular case. |
| `resolved` | `str` |  | What the caller's name(s) matched, in the caller's vocabulary, so the inference is auditable rather than trusted. |
| `total` | `int` |  | The size of the whole slice, not of `nodes`, the number the caller needs to decide whether to ask a narrower question. |
| `diagnostics` | [`list[Diagnostic]`](#diagnostic) | `[]` | Empty on both Python backends today. Reserved for a backend that cannot answer the question asked, which must say which rather than return a partial answer that looks whole (the `entrypoint_report_unavailable` precedent). |
| `complete` | `bool` |  | Whether `nodes` is the whole slice, `False` exactly when a cap fired. Derived from `total` and `nodes` rather than stored, so the two cannot disagree (the same construction as `EdgePage.complete`) and serialised with the model. |
| `root` | [`SliceNode`](#slicenode) |  | The single seed, for the accessors that take one. |

### `FlowPaths`

```python
class FlowPaths(BoundedResult)
```

The paths a query returned, and whether that was all of them.

A model, not a `list` subclass, the earlier `list` form carried `truncated` as a plain
attribute, so `json.dumps` dropped it and `model_dump` did not exist (verified). It keeps
list behaviour through `BoundedResult` because everything a caller does with paths
(index, iterate, `if paths:`) is what a list does, and making them write `.paths` first
would be friction with no information in it.

`complete` is stored here rather than derived, because it is a flag and not a `total`:
counting *every* shortest path costs a second full traversal to produce a number a caller
cannot act on differently, at `max_paths` witnesses, "there were more" is the entire
actionable content. The extent question (how far a value reaches) is `slice_forward`,
which does report its `total`.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `paths` | [`list[FlowPath]`](#flowpath) | The paths, in `hop_sort_key` order. |
| `complete` | `bool` | `False` when `max_paths` cut the list; `True` when these are all the shortest paths there are (including when there are none). `TaintResult` narrows it (there, truncation is only one of the ways it can be `False`) so on a taint verdict, `False` is not on its own a reason to raise the cap and ask again. |

### `FlowPath`

```python
class FlowPath(BaseModel)
```

**A path is a sequence**, where a `Slice` is a set.

The order of `hops` is the order the value travels, and consecutive hops join up:
`hops[i].to.ref == hops[i + 1].frm.ref`. That is the whole difference from a slice, and it
is why the two are separate accessors returning separate types rather than one derived from
the other, a cone of 10,000 nodes contains millions of distinct paths, so a caller who wants
to *argue* a flow needs the sequence and a caller who wants to *bound* one needs the set.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `hops` | [`list[PathHop]`](#pathhop) | The edges, in order. Never empty: a path with no hops is not a path, and the "does it flow at all" question is `flows_to_call` / `reaches`. |
| `weakest` | [`PathHop`](#pathhop) | The hop that caps how strongly this flow can be stated, the *most approximate* one. |

### `PathHop`

```python
class PathHop(BaseModel)
```

One edge of a flow, in the caller's vocabulary: where it went, and what justified it.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `frm` | [`SliceNode`](#slicenode) |  | The position the hop leaves. |
| `to` | [`SliceNode`](#slicenode) |  | The position it arrives at. |
| `via` | `str` |  | What kind of edge justified it, `data`, `control`, `argument`, `return`, `summary` (the five SDG relationships) or `call` (`call_paths_between`). Never the graph's own `PY_DDG`/`PY_PARAM_IN` spelling. |
| `var` | `str \| None` | `None` | The variable the dependence is on, for a `data` hop; `None` for the rest, which carry no variable on the edge. |
| `prov` | `list[str]` | `[]` | How the hop was established. Empty for everything but a `data` hop, see `prov_rank`. |

### `PROV_CERTAINTY`

```python
PROV_CERTAINTY = ('points-to', 'reaching-defs', 'ssa')
```

How much a data-dependence provenance is worth as evidence, **least certain first**.

### `prov_rank`

```python
prov_rank(prov: list[str]) -> int
```

How certain a hop's provenance is: lower is weaker. See `PROV_CERTAINTY`.

A hop with **no** provenance ranks above every labelled one. `prov` is carried by `PY_DDG`
and by nothing else (verified on the live graph: `PY_CDG`, `PY_PARAM_IN`, `PY_PARAM_OUT`
and `PY_SUMMARY` carry no properties at all), and those four are structural facts
(control dependence, argument binding, return binding) not may-analyses. An unlabelled hop
therefore claims no approximation, and ranking it as the most certain is what stops it from
being reported as the reason a flow is uncertain.

An unrecognised provenance ranks weakest of all: a new label from a future analyzer is
something this SDK has not been taught to trust, and treating it as strong would be the
optimistic half of the guess.

A hop carrying **several** provenances takes the weakest of them. That is the conservative
reading (several labels could as easily mean "any one of these justifies the edge", in which
case the strongest should win) and it is unobservable on real data today, because `prov` is
a singleton on every edge of the live graph. Conservative is the direction to be wrong in:
under-claiming certainty costs a caller a follow-up question, over-claiming it costs them a
wrong conclusion.

### `TaintResult`

```python
class TaintResult(FlowPaths)
```

Which of the requested (source, sink) pairs flow, which were searched to exhaustion, and what
stopped the rest.

A subclass of `FlowPaths` rather than a new shape: the witnesses *are* flow paths, each
already carrying `weakest`, and `complete` still answers "did this call return everything it
found". Three fields are added, and `complete` is narrowed.

**What `complete` says here.** `True` only when nothing was truncated **and**
`unresolved` is empty. It is one flag for the whole batch, so a single skipped or blocked
pair makes it `False` however cleanly the other pairs answered, deliberately, because the
alternative is `True` beside a non-empty ledger, which tells a caller who reads only the flag
that the batch was fully searched when part of it was not. The consequence to know: `False`
does not mean "raise `max_paths` and ask again". Where `paths` was not truncated a bigger cap
returns the same flag, and `unresolved` is what says why.

**What `exhausted` claims.** A pair is listed when all three hold: the call passed
`depth=None`, the search found no path for it, and no `unresolved` diagnostic implicates
it. That is a claim about **the emitted graph plus the ledger, and never about the program**,
which is why the field is named for the search rather than for the conclusion. The step from
"exhausted" to "this alert is a false positive" is the caller's, deliberately: the DDG's
`points-to` edges over-approximate, which is the safe direction for an absence claim, but the
call structure *under*-approximates wherever dispatch is unresolved, so a missing call edge means
a real flow can exist with no path in the graph. Absence of path bounds the program only where the
frontier was fully resolved, and `unresolved` is what enumerates where it was not.

**Why it is stored rather than derived.** It is computable (`all_pairs − pairs_with_paths −
pairs_with_unresolved` when `depth is None`, and `∅` otherwise) and that is the reason not
to: the load-bearing answer must not be a subtraction the caller can get wrong, and a subtraction
with a mode switch in front of it is worse than one without.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `exhausted` | `list[tuple[str, str]]` | The `(source, sink)` pairs searched to exhaustion with a clean ledger, named by the same strings the caller passed, never a `can://` id. Empty whenever `depth` was not `None`. |
| `roots` | [`list[SliceNode]`](#slicenode) | What each selector matched, so a conclusion is auditable rather than asserted. |
| `resolved` | `str` | The human-readable form of `roots`, via `slice_resolved`. |
| `unresolved` | [`list[Diagnostic]`](#diagnostic) | The ledger of everything that stopped a pair short of an answer, whatever stopped it. Two codes reach it: `unresolved_dispatch` for a frontier the walk could not follow, and `degenerate_pair` for a requested pair whose source and sink resolved to the same position, which is skipped rather than searched. Both name the affected pair in `message` prose, the same convention every other diagnostic in this SDK follows (e.g. the Neo4j backend's `module_scope` message). `Diagnostic` has no structured field for a pair today, so this is a human-readable explanation, not something to compute with: the pair→diagnostic association `exhausted` needs is tracked internally by the implementation before each `Diagnostic` is built, never recovered by parsing `message` back out, that would resurrect the derivation this stored field exists to avoid. A caller that needs the association programmatically wants an additive `subject` field on `Diagnostic`, which widens a published model contract (`docs/agent-api-reference.md`) and should be requested rather than assumed here. |

## Paged graphs

```python
from cldk.analysis.commons.results import EdgePage, BoundedResult
```

### `EdgePage`

```python
class EdgePage(BoundedResult, Generic[E])
```

One page of an edge set, plus everything needed to tell what is missing from it.

Per-callable scoping bounds *which* edges an accessor may return; it does not bound *how
many*. Measured on odoo-slim-19, one callable (`Website.configurator_apply`) has 1,386,918
DDG edges, 27% of the whole application's 5,134,655, while 15,520 of the 15,549 callables have
fewer than 10,000. So the accessors that return edges page, and the ruling is **paginate, do
not truncate**: a cap discards edges the caller may need and can only report that it did,
whereas a page bounds the response while leaving every edge reachable.

E5 requires that a bound is never silent. It is satisfied here without a second call:
`total` is the size of the whole answer, `next_cursor` is `None` exactly when this page
is the end of it, and `complete` (the shared `BoundedResult` protocol) says so
directly, so a caller distinguishes "this is everything" from "there is more" from one page,
and, for the D7 case, an empty *page* whose `total` is 0 from a page that merely ran out of
room.

**Why a page model and not a generator of pages.** A cursor is a value: it survives being
serialized into a result, stored, and passed back later by a different process, which is how
this surface is actually driven. A generator is a live object with a position, so it cannot
cross that boundary, and it would also force the caller to consume pages in order when the
common case (99.8% of callables) is one page that needs no loop at all.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `edges` | `list[E]` |  | This page's edges, in the accessor's canonical order (see `ddg_sort_key` and its siblings), the same order on every backend, which is what makes page *n* the same page everywhere. |
| `total` | `int` |  | The size of the whole edge set, not of this page. Reported on every page, so a caller reads the cost before deciding whether to walk the rest. |
| `next_cursor` | `str \| None` | `None` | An opaque handle naming where to resume, pass it back as `cursor=` to get the next page. `None` means this page ends the set. It is not for reading: it encodes the sort key of the last edge on the page, which is an implementation detail of the order, not part of the caller's vocabulary. |
| `complete` | `bool` |  | Whether this page ends the set. Derived from `next_cursor` rather than stored, so the two cannot disagree; serialised, so `model_dump()` carries it. |

### `BoundedResult`

```python
class BoundedResult(BaseModel)
```

The one completeness protocol every bounded result speaks (E5: a bound is never silent).

Three accessor families return a bounded answer in three shapes (a page of edges, a capped
set of positions, a capped list of paths) and each shape keeps the extra fields its bound
needs (`next_cursor` / `total` / `roots` / …). What they must not do is spell "was that
everything?" three ways. So each exposes **`complete: bool`**, and it is a *serialised*
field: `model_dump()` carries it, so a result written to JSON and read back by another
process still says whether it was whole. On `EdgePage` and `Slice` it is a
pydantic computed field derived from the data (`next_cursor is None`; `total ==
len(nodes)`) so it cannot disagree with them; on `FlowPaths` it is stored, because a
path list's truncation is known only to the query that produced it.

**A result whose payload is a list behaves as that list.** `for x in page` yields the edges,
`len(slice)` counts the nodes, `paths[0]` is the first path and `if paths:` is honest,
`False` when empty. Without this, pydantic's default `__iter__` yields `(field, value)`
tuples and `bool()` is always `True`, which was verified to be exactly what a caller
writing `for edge in page:` got. The payload field is named by `_items`, once per
shape, so the three cannot drift.

## Entrypoint coverage

```python
from cldk.analysis.commons.results import EntrypointCoverage
```

### `EntrypointCoverage`

```python
class EntrypointCoverage(BaseModel)
```

Coverage and failure record for `codeanalyzer-python`'s entrypoint-detection pass,
surfaces its `PyEntrypointReport` (`schema/py_schema.py`) so
`get_entrypoints` returning `[]`
stays distinguishable between "the pass ran clean and this project genuinely has none" and
"the pass had gaps". The pass's own docstring says it best: it "under-approximates by design,
so silence is its failure mode", this is what makes a gap visible instead of indistinguishable
from "this project has no entrypoints".

`get_entrypoints()`'s `List[PyCallableOverview]` return is frozen and carries no room for
this signal, so it rides a separate accessor
(`get_entrypoint_coverage`) instead.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `frameworks_detected` | `list[str]` | `[]` | Frameworks the pass recognized in this project (e.g. `"flask"`). |
| `rulesets` | `list[str]` | `[]` | Rule sources consulted (`"shipped"` and/or `"user:<path>"`). |
| `unresolved` | `dict[str, int]` | `{}` | Count of near-misses, keyed by rule/framework, that could not be resolved to a definite entrypoint, non-zero counts are exactly the under-approximation gap. |
| `errors` | `list[str]` | `[]` | Hard failures the detection pass hit while running. |
| `diagnostics` | [`list[Diagnostic]`](#diagnostic) | `[]` | Non-empty when a backend cannot supply this report at all: a Neo4j graph emitted by codeanalyzer-python 1.4.0 does not carry `PyApplication.entrypoint_report` (only the derived `is_entrypoint`/`entrypoint_frameworks` per-node properties; 1.4.1 projects it onto `:PyApplication`), so the Neo4j backend returns `entrypoint_report_unavailable` here instead of fabricating empty-but-clean-looking fields, the same "say so honestly" precedent as `LocateResult`'s `module_source_unavailable`. When `diagnostics` is non-empty, the other fields are not meaningful coverage information (there was none to report), not "no gaps found". |

## Default bounds

```python
from cldk.analysis.commons.bounds import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_MAX_NODES,
    DEFAULT_DEPTH,
    DEFAULT_MAX_PATHS,
)
```

### `DEFAULT_PAGE_SIZE`

```python
DEFAULT_PAGE_SIZE = 10000
```

Edges per page when the caller does not say.

### `DEFAULT_MAX_NODES`

```python
DEFAULT_MAX_NODES = 10000
```

Nodes per slice when the caller does not say.

### `DEFAULT_DEPTH`

```python
DEFAULT_DEPTH = 5
```

Hops from the seed when the caller does not say.

### `DEFAULT_MAX_PATHS`

```python
DEFAULT_MAX_PATHS = 10
```

Paths per query when the caller does not say.

## Exceptions

```python
from cldk.utils.exceptions import (
    SelectorNotInGraph,
    AmbiguousName,
    CodeanalyzerUsageException,
    CodeanalyzerExecutionException,
    CldkInitializationException,
    GraphSchemaMismatch,
)
```

### `SelectorNotInGraph`

```python
class SelectorNotInGraph(ValueError)
```

Raised when a scoping keyword names something the analysed application does not hold.

`get_symbol_table(paths=...)`, `get_classes(module=...)` and `get_call_graph(roots=...)`
all narrow a whole-application enumeration to a caller-supplied selection. A value in that
selection which matches nothing used to contribute nothing, so a typo'd path and a module that
genuinely declares no classes were the *same* empty dict, the ambiguous-empty defect the
query facade exists to remove. Raising makes them different answers.

The message names the values that matched nothing and stops there. It deliberately offers no
near-miss candidates: leg 1.5's E8 puts typo-tolerant matching out of scope "not in the
resolver, not in the error path", because a suggestion is a guess, and a guess presented as a
correction is the confident-wrong-answer failure this design exists to prevent.

Subclasses `ValueError` because that is what these accessors already document raising
for a malformed scoping keyword (an empty selection, a `depth` below 1), an unmatched value
is the same class of caller error, not a new one, and a caller catching `ValueError` around a
scoped call keeps working.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `kind` | `str` | Which keyword named them, `"paths"`, `"module"` or `"roots"`. |
| `missing` | `list[str]` | The values, as the caller wrote them, that matched nothing. |
| `requested` | `int` | How many values the keyword carried in total, so a partial miss is visible as a partial miss. |
| `detail` |  |  |
| `message` |  |  |

### `AmbiguousName`

```python
class AmbiguousName(ValueError)
```

Raised when a name the caller wrote matches more than one thing, listing every match.

The addressing layer lets a caller name a callable or a value the way it
already thinks of it rather than assembling the analyzer's `can://` id. Names are a viable
address (86% of this application's leaf callable names are unique) but the remainder are
framework methods (`__init__` 238, `write` 220, `create` 214), and there picking one is a
confident wrong answer with no signal to the caller. So the resolver never picks: it raises,
and hands back the matches as data.

Like `SelectorNotInGraph`, it offers no near-miss suggestions, every string in
`candidates` genuinely matched the name as written. E8 puts typo-tolerant matching out of
scope "not in the resolver, not in the error path", so there is no scoring, no edit distance,
and nothing here that was not a real match.

`candidates` carries **all** of them, because that is the data a caller may want to filter
programmatically; `message` shows only the first few plus a total, because two hundred
strings in a traceback is not an error message a person can act on. The message also names the
keyword that narrows it, an error that says what to do next costs nothing extra to write.

Subclasses `ValueError` for the same reason `SelectorNotInGraph` does: an
unusable name is a caller error, and a caller already catching `ValueError` around a
resolution keeps working.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `SHOWN` |  | `5` | How many candidates the message shows before falling back to a count. |
| `name` | `str` |  | The name as the caller wrote it. |
| `candidates` | `list[str]` |  | Every match, in a deterministic (sorted) order. |
| `kind` | `str` |  | What was being resolved, `"callable"` or `"value"`. |
| `message` |  |  |  |

### `CodeanalyzerUsageException`

```python
class CodeanalyzerUsageException(Exception)
```

Exception raised for incorrect CodeAnalyzer usage.

This exception is raised when the CodeAnalyzer is used incorrectly,
such as providing invalid argument combinations or unsupported
configurations. Common causes include:
- Unsupported analysis level for the language
- Invalid file paths
- Incompatible option combinations

> **See Also**
>
> - `CldkInitializationException`: Related exception for initialization-time errors.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `message` | `str` | A descriptive error message explaining the usage error and how to correct it. |

### `CodeanalyzerExecutionException`

```python
class CodeanalyzerExecutionException(Exception)
```

Exception raised for errors during CodeAnalyzer execution.

This exception is raised when the CodeAnalyzer backend (JAR or Python)
fails during analysis. Common causes include:
- Backend process crash or timeout
- Invalid project structure
- Memory exhaustion during analysis
- Missing dependencies

> **See Also**
>
> - `JCodeanalyzer`: Java backend.
> - `PyCodeanalyzer`: Python backend.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `message` | `str` | A descriptive error message explaining the execution failure. |

### `CldkInitializationException`

```python
class CldkInitializationException(Exception)
```

Exception raised for errors during CLDK initialization.

This exception is raised when the CLDK core or its components fail to
initialize properly. Common causes include:
- Invalid language specification
- Missing required parameters
- Conflicting configuration options

> **See Also**
>
> - `CLDK`: The main entry point that may raise this exception.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `message` | `str` | A descriptive error message explaining the initialization failure. |

### `GraphSchemaMismatch`

```python
class GraphSchemaMismatch(RuntimeError)
```

Raised when a Neo4j backend's attached graph doesn't speak its expected vocabulary.

A Neo4j-backed analysis facade queries a graph some other process built with a
`codeanalyzer-*` analyzer. If that analyzer's generation predates (or postdates) the
vocabulary the querying backend was written against, every query silently returns zero
rows, indistinguishable from "this codebase genuinely has no callables". This exception
makes that mismatch loud: it names what the backend expected, what it actually found on
the graph, and which relationship types are missing.

Raised by a one-time schema probe run at connection time (every language's Neo4j backend has
one (`PyNeo4jBackend._probe_schema`, `TSNeo4jBackend._probe_schema`)) never by an
individual query. A probe may also raise it with a precomputed `message` when the vocabulary
matches but the graph's `analyzer_version` is below the backend's floor.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `expected` | `set[str]` | The relationship types the backend requires. |
| `found` | `set[str]` | The relationship types actually present on the connected graph. |
| `missing` | `set[str]` | `expected - found`, what the graph is missing. |
| `message` |  |  |

<!-- CLDK:API:END -->
