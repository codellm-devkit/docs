---
title: "TypeScript API"
description: "Program analysis for TypeScript and JavaScript projects, and the data models that it returns."
---

`TypeScriptAnalysis` gives you the symbol table, the call graph, the dataflow
graphs and the entrypoints of a TypeScript or JavaScript project.
`CLDK.typescript(project_path=...)` returns it. Most method names are the same
as on the [Java](/reference/python-api/java/) and
[Python](/reference/python-api/python/) pages.

## How it works

CLDK runs the analyzer [codeanalyzer-typescript](/backends/codeanalyzer-ts/) on
your project directory. The command-line tool of the analyzer is `cants`, and
`pip install cldk` installs it. CLDK reads the `analysis.json` file that `cants`
writes, and answers each query from it.

The analyzer builds its output level by level. Each
[analysis level](#analysis-levels) adds to the level before it:

```mermaid
flowchart LR
    P[TypeScript or JavaScript project] --> A["CLDK.typescript(project_path)"]
    A --> C["cants (codeanalyzer-typescript)"]
    C --> S["Level 1: symbol table"]
    S --> CG["Level 2: call graph (tsc, defuse and import edges)"]
    CG --> D["Level 3: CFG, CDG and DDG"]
    D --> SDG["Level 4: SDG"]
```

CFG, CDG and DDG are the control flow graph, the control dependence graph and
the data dependence graph of each callable. SDG is the system dependence graph,
which links these graphs across calls.

Each call-graph edge records how the analyzer found it, in `provenance`:

- `tsc`: the resolver of the TypeScript compiler found the call target.
- `defuse`: the analyzer followed a function value from its definition to a
  call. The code calls the value, or passes it as a callback to an external or
  unresolved function, for example `keys.map((k) => ...)`. In the second case,
  the edge goes from the enclosing callable to the callback.
- `import`: the target is outside the project, for example
  `(builtin).getTime` or `vitest/config.mergeConfig`.

The analyzer reads `.ts`, `.tsx`, `.mts`, `.cts`, `.js`, `.jsx`, `.mjs` and
`.cjs` files. A `.d.ts` file is a module with `is_declaration_file=True`. There
is no single-file mode: always pass a project directory. A syntax error does
not stop the analysis, and CLDK does not report it. Declarations near the error
can be missing or wrong.

## Before you start

1. Install CLDK. It needs Python 3.11, 3.12, 3.13 or 3.14. It does not
   install on Python 3.15 yet. On Python 3.14, pip compiles `tree-sitter`
   from source, so you need a C compiler.

   ```bash
   pip install cldk
   ```

   You do not need Node.js for the samples on this page. For your own
   project, install Node.js, which includes npm. The analyzer uses npm to
   install the dependencies of the project.

2. Clone the sample project, Zod 4.6.7:

   ```bash
   git clone --depth 1 --branch v4.6.7 https://github.com/colinhacks/zod.git
   ```

3. Run the samples on this page from the directory that contains `zod`.

### What a run does to your project

A local run does these things:

- It writes the cache to `<project>/.codeanalyzer/typescript/`. On Zod at the
  `call_graph` level, the cache is 18 MB. Add `.codeanalyzer/` to
  `.gitignore`, or move the cache with `backend=CodeAnalyzerConfig(cache_dir=...)`.
- If the project has a `package.json` and no `node_modules`, the analyzer
  installs the dependencies, with install scripts turned off. It runs
  `npm install --ignore-scripts`. With a `package-lock.json` file, it runs
  `npm ci` instead. With a pnpm or yarn lockfile and that tool on your PATH,
  it runs `pnpm install` or `yarn install`. The install needs network access
  and creates `node_modules`.
- If `node_modules` exists, the analyzer uses it. With `eager=True`, the
  analyzer installs the dependencies again, with install scripts turned off.
  `npm ci` deletes `node_modules` first, so the files that install scripts
  made are gone. To get them back, run `npm ci` in the project.
- If the install fails, the analysis continues with fewer resolved calls, and
  CLDK shows no message. For example, the install fails without npm on your
  PATH, and on `zod/packages/zod`.
- It skips test files: files named `*.test.*` or `*.spec.*`, and every
  directory named `test`, `tests`, `spec`, `__test__`, `__tests__` or
  `__mocks__`. It also skips every directory named `node_modules`, `dist`,
  `build`, `out`, `coverage`, `vendor`, `.next`, `.turbo` or `.cache`, for
  example `src/build/`. You cannot include these files.

## Analysis levels

Pass `analysis_level` to `CLDK.typescript`. Use an `AnalysisLevel` member or
its name as a string, for example `"call_graph"`. An unknown name raises
`ValueError`. Each level also contains the levels above it in the table.

| Level | `cants` flag | Adds | Methods that need it |
| ----- | ------------ | ---- | -------------------- |
| `symbol_table` (default) | `-a 1` | Modules, types, callables, fields, imports, exports, decorators, call sites, entrypoints and configuration files | All other methods |
| `call_graph` | `-a 2` | Resolved call targets, the call graph, the external targets and the configuration reads | `get_call_graph`, `get_callers`, `get_callees`, `get_class_call_graph`, `get_calling_lines`, `get_external_symbols`, `get_synthesized_callables`, `callers_of`, `callees_of`, `reaches`, `call_paths_between`, `backward_cone`, `get_config_uses`, `get_config_readers`, `get_unresolved_config_reads` |
| `program_dependency_graph` | `-a 3` | Control flow, control dependence and data dependence inside each callable | `get_cfg`, `get_cdg`, `get_ddg` |
| `system_dependency_graph` | `-a 4` | Nodes for parameters, arguments and return values, and dependence across calls | `resolve_value`, `slice_backward`, `slice_forward`, `paths_between`, `flows_to_call`, `flows_to_argument`, `taint` |

If the analysis level is too low for a method, this happens:

- The call-graph methods find no calls and raise no error. For example,
  `callers_of` returns `[]` and `reaches` returns `False`. Read
  `analysis.has_resolution_edges`: it is `False` below `call_graph`.
  `get_call_sites`, `get_callsites_for` and `get_call_targets` still answer,
  but no call target is resolved.
- Below `call_graph`, `get_config_uses`, `get_config_readers` and
  `get_unresolved_config_reads` return `[]` and raise no error. At
  `call_graph`, a read whose key is in a variable, for example
  `process.env[k]` after `const k = "PORT"`, is only in
  `get_unresolved_config_reads`. `program_dependency_graph` resolves it.
- Below `program_dependency_graph`, `get_cfg`, `get_cdg`, `get_ddg`, the
  slices, `paths_between`, `flows_to_call` and `flows_to_argument` raise
  `CodeanalyzerUsageException`. `resolve_value` and `taint` raise
  `SelectorNotInGraph`.
- At `program_dependency_graph`, the value-flow methods raise
  `SelectorNotInGraph` ("value not in graph"), also for a real parameter.

On Zod, the first run takes about 20 seconds. When `CLDK.typescript` reads the
cache, it takes about one second.

:::caution[The cache does not check the level or your changes]
If `<project>/.codeanalyzer/typescript/analysis.json` exists, CLDK reuses it.
It does not compare the analysis level or the source files with the cache.

- If you ask for a higher `analysis_level` on a project that you analyzed
  before, pass `eager=True` once. Without it, you get the old level and no
  warning. The message of `CodeanalyzerUsageException` tells you to build
  again with a higher level. That alone does not work. Add `eager=True`.
- After you change the source code, pass `eager=True` once.
- A run with `target_files` writes over the cache. Pass `eager=True` on the
  next full run.
- `eager=True` also installs the dependencies again. See
  [What a run does to your project](#what-a-run-does-to-your-project).
:::

## Worked example

The outputs come from cldk 2.0.0 and codeanalyzer-typescript 1.6.0 on Zod
4.6.7. Run the three blocks in order, from the same directory.

### Build the analysis

```python
from cldk import CLDK
from cldk.analysis import AnalysisLevel

analysis = CLDK.typescript(
    project_path="zod/packages/zod",
    analysis_level=AnalysisLevel.call_graph,
)

modules = analysis.get_symbol_table()
classes = analysis.get_classes()
print(len(modules), "modules,", len(classes), "classes")
# 135 modules, 53 classes
print(sorted(classes)[:3])
# ['src/v3/ZodError.ZodError', 'src/v3/helpers/parseUtil.ParseStatus', 'src/v3/types.Class']

parse = analysis.get_method("src/v3/types.ZodType", "parse")
print(parse.signature, parse.start_line)
# src/v3/types.ZodType.parse 223
print(analysis.get_method_parameters("src/v3/types.ZodType", "parse"))
# ['data', 'params']
```

### Read the call graph

This block continues the block above.

```python
graph = analysis.get_call_graph()
print(graph.number_of_nodes(), "nodes,", graph.number_of_edges(), "edges")
# 2261 nodes, 4629 edges

target = "src/v3/helpers/parseUtil.addIssueToContext"
print(graph.nodes[target])
# {'id': 'can://zod/typescript/src/v3/helpers/parseUtil.ts/addIssueToContext', 'kind': 'callable'}
caller = sorted(graph.predecessors(target))[0]
print(caller, graph.edges[caller, target])
# src/v3/types.ZodArray._parse {'type': 'CALL_DEP', 'weight': 4, 'provenance': ('tsc',)}

print(len(analysis.callers_of("addIssueToContext")))
# 28
print(analysis.reaches("ZodString._parse", "addIssueToContext"))
# True
```

### Ask a dataflow question

Dataflow needs `system_dependency_graph`. The cache holds the `call_graph`
analysis from the first block, so pass `eager=True`.

```python
from cldk import CLDK
from cldk.analysis import AnalysisLevel

analysis = CLDK.typescript(
    project_path="zod/packages/zod",
    analysis_level=AnalysisLevel.system_dependency_graph,
    eager=True,  # rebuild: the cache holds the call_graph run from above
)

print(analysis.flows_to_call("ctx", "makeIssue", within="addIssueToContext"))
# True

result = analysis.taint(
    sources=[("issueData", "addIssueToContext")],
    sinks=[("params", "makeIssue")],
)
print(len(result.paths), result.complete)
# 1 True
for path in result.paths:
    print(" -> ".join(h.to.name or h.to.kind for h in path.hops))
# argument -> params
```

The parameter `issueData` flows into an argument of the `makeIssue(...)` call,
and that argument reaches the parameter `params`. The argument hop has no name,
so the example prints its `kind`. For more Zod samples, see the
[TypeScript example](/examples/typescript/).

## What to call for what

| Question | Methods | Lowest level |
| -------- | ------- | ------------ |
| What does the project contain? | [`get_symbol_table`](#typescriptanalysisget_symbol_table), [`get_modules`](#typescriptanalysisget_modules), [`get_typescript_module`](#typescriptanalysisget_typescript_module), [`get_typescript_file`](#typescriptanalysisget_typescript_file), [`get_application_view`](#typescriptanalysisget_application_view), [`get_call_graph_json`](#typescriptanalysisget_call_graph_json) | `symbol_table` |
| Which types are there? | [`get_classes`](#typescriptanalysisget_classes), [`get_class`](#typescriptanalysisget_class), [`get_classes_by_criteria`](#typescriptanalysisget_classes_by_criteria), [`get_interfaces`](#typescriptanalysisget_interfaces), [`get_enums`](#typescriptanalysisget_enums), [`get_enum_members`](#typescriptanalysisget_enum_members), [`get_type_aliases`](#typescriptanalysisget_type_aliases) | `symbol_table` |
| How are the types related? | [`get_class_hierarchy`](#typescriptanalysisget_class_hierarchy), [`get_sub_classes`](#typescriptanalysisget_sub_classes), [`get_extended_classes`](#typescriptanalysisget_extended_classes), [`get_implemented_interfaces`](#typescriptanalysisget_implemented_interfaces), [`get_nested_classes`](#typescriptanalysisget_nested_classes) (always `[]`) | `symbol_table` |
| What does a type or a module declare? | [`get_functions`](#typescriptanalysisget_functions), [`get_methods`](#typescriptanalysisget_methods), [`get_methods_in_class`](#typescriptanalysisget_methods_in_class), [`get_method`](#typescriptanalysisget_method), [`get_method_parameters`](#typescriptanalysisget_method_parameters), [`get_constructors`](#typescriptanalysisget_constructors), [`get_fields`](#typescriptanalysisget_fields), [`get_interface_properties`](#typescriptanalysisget_interface_properties), [`get_variables`](#typescriptanalysisget_variables), [`get_imports`](#typescriptanalysisget_imports), [`get_exports`](#typescriptanalysisget_exports) | `symbol_table` |
| Which decorators are used? | [`get_decorators`](#typescriptanalysisget_decorators), [`get_class_decorators`](#typescriptanalysisget_class_decorators), [`get_methods_with_decorators`](#typescriptanalysisget_methods_with_decorators), [`get_classes_with_decorators`](#typescriptanalysisget_classes_with_decorators), [`get_decorated_callables`](#typescriptanalysisget_decorated_callables) | `symbol_table` |
| What are all the callables and their bodies? | [`get_callables_overview`](#typescriptanalysisget_callables_overview), [`get_method_bodies`](#typescriptanalysisget_method_bodies) | `symbol_table` |
| Where is this code, and what is its text? | [`locate`](#typescriptanalysislocate), [`locate_many`](#typescriptanalysislocate_many), [`resolve_callable`](#typescriptanalysisresolve_callable), [`get_source`](#typescriptanalysisget_source), [`describe`](#typescriptanalysisdescribe) | `symbol_table` |
| Which calls does a callable make? | [`get_call_sites`](#typescriptanalysisget_call_sites), [`get_callsites_for`](#typescriptanalysisget_callsites_for), [`get_call_targets`](#typescriptanalysisget_call_targets) | `symbol_table` (call targets resolved from `call_graph`) |
| Who calls what? | [`get_call_graph`](#typescriptanalysisget_call_graph), [`get_callers`](#typescriptanalysisget_callers), [`get_callees`](#typescriptanalysisget_callees), [`get_class_call_graph`](#typescriptanalysisget_class_call_graph), [`get_calling_lines`](#typescriptanalysisget_calling_lines), [`get_external_symbols`](#typescriptanalysisget_external_symbols), [`get_synthesized_callables`](#typescriptanalysisget_synthesized_callables), [`callers_of`](#typescriptanalysiscallers_of), [`callees_of`](#typescriptanalysiscallees_of), [`reaches`](#typescriptanalysisreaches), [`call_paths_between`](#typescriptanalysiscall_paths_between), [`backward_cone`](#typescriptanalysisbackward_cone) | `call_graph` |
| What happens inside a callable? | [`get_cfg`](#typescriptanalysisget_cfg), [`get_cdg`](#typescriptanalysisget_cdg), [`get_ddg`](#typescriptanalysisget_ddg) | `program_dependency_graph` |
| Where does a value go? | [`resolve_value`](#typescriptanalysisresolve_value), [`slice_backward`](#typescriptanalysisslice_backward), [`slice_forward`](#typescriptanalysisslice_forward), [`paths_between`](#typescriptanalysispaths_between), [`flows_to_call`](#typescriptanalysisflows_to_call), [`flows_to_argument`](#typescriptanalysisflows_to_argument), [`taint`](#typescriptanalysistaint) | `system_dependency_graph` |
| What can code outside the project call? | [`get_entrypoints`](#typescriptanalysisget_entrypoints), [`get_entrypoint_classes`](#typescriptanalysisget_entrypoint_classes), [`get_entrypoint_coverage`](#typescriptanalysisget_entrypoint_coverage) | `symbol_table` |
| What do the configuration files say? | [`get_artifacts`](#typescriptanalysisget_artifacts), [`get_dependencies`](#typescriptanalysisget_dependencies), [`get_config_keys`](#typescriptanalysisget_config_keys) | `symbol_table` |
| Which code reads the configuration? | [`get_config_uses`](#typescriptanalysisget_config_uses), [`get_config_readers`](#typescriptanalysisget_config_readers), [`get_unresolved_config_reads`](#typescriptanalysisget_unresolved_config_reads) | `call_graph` |

`get_artifacts`, `get_dependencies`, `get_config_keys`, `get_config_uses` and
`get_unresolved_config_reads` return the models that the Python analysis also
uses: [`PyArtifact`](/reference/python-api/python/#pyartifact),
[`PyDependency`](/reference/python-api/python/#pydependency),
[`PyConfigKey`](/reference/python-api/python/#pyconfigkey),
[`PyConfigUseEdge`](/reference/python-api/python/#pyconfiguseedge) and
[`PyConfigRead`](/reference/python-api/python/#pyconfigread). The Python page
documents them. `get_config_readers` returns
[`TSCallableOverview`](#tscallableoverview) objects.

On TypeScript, `get_call_graph()`, `get_symbol_table()` and `get_classes()`
take no arguments. The Python options `roots=`, `depth=`, `paths=` and
`module=` do not exist here.

### Names and keys

Many methods in the generated reference do not say which names they take. On
Zod, the keys look like this:

| Key | Format | Example |
| --- | ------ | ------- |
| Module key | The file path from `project_path`, with the extension | `"src/v3/types.ts"` |
| Type or function signature | The module key without the extension, a dot and the name | `"src/v3/types.ZodType"`, `"src/v3/ZodError.quotelessJson"` |
| Method signature | The type signature, a dot and the method name | `"src/v3/types.ZodType.parse"` |
| Anonymous callable | `<anon@line:column>` in place of the name | `"src/compile.<anon@18:35>"` |
| External target | The module, a dot and the name | `"(builtin).getTime"`, `"vitest/config.mergeConfig"` |

Some methods take these keys in a special way:

- `get_method`, `get_method_parameters`, `get_callers` and `get_callees` take
  a type signature and the short method name:
  `get_method("src/v3/types.ZodType", "parse")`. If you give the full method
  signature as the second argument, `get_method` returns `None`. For a
  function, give only its signature to `get_callers` or `get_callees`:
  `get_callers("src/v3/helpers/parseUtil.addIssueToContext")`.
- `get_class_call_graph` takes the full method signature as its second
  argument, for example `"src/v3/types.ZodString._parse"`. A short name
  returns `[]`.
- `get_typescript_module` needs the exact module key. `"./src/v3/types.ts"`
  returns `None`.
- `get_classes_by_criteria(inclusions=[...], exclusions=[...])` matches parts
  of the class signature. With no `inclusions`, it returns `{}`.
- Decorator names have no `@`: `get_methods_with_decorators(["Get"])`. The
  name `"@Get"` matches nothing.
- The name-based methods take a short name or the last parts of a signature,
  for example `"addIssueToContext"` or `"ZodString._parse"`. These methods
  include `resolve_callable`, `callers_of`, `reaches`, `get_cfg`, the slices
  and `taint`. A name that matches more than one callable raises
  `AmbiguousName`. A value is a parameter name and its callable:
  `slice_forward("obj", within="quotelessJson")`.
- The nodes of `get_call_graph()` are callable signatures, module keys for
  the top-level code of a module, for example `"vitest.config.ts"`, and
  external targets.
- `get_call_graph_json()` returns all of the analysis as JSON, not only the
  call graph. On Zod at `call_graph`, the text has more than 10 million
  characters. For the call graph, use `get_call_graph()`.

## Entrypoints

`get_entrypoints()` returns the callables that code outside the project can
call. Three kinds of rules find them:

- **Framework rules**, for example for NestJS and commander. If your source
  imports the package of a framework, the analyzer uses the rules of that
  framework. `package.json` does not have to declare the package.
- **Heuristic rules**. They apply to every project and find shapes such as
  `app.get("/users/:id", handler)` and `process.on("SIGINT", handler)`. Only
  these rules find Express routes. Their `confidence` is `"heuristic"`, and
  some of their results are wrong.
- **Manifest rules**: the `bin` and `main` entries of `package.json`.

On Zod, the three entrypoints come from heuristic rules:

```python
from cldk import CLDK

analysis = CLDK.typescript(project_path="zod/packages/zod")

for overview in analysis.get_entrypoints():
    print(overview.signature)
# src/v3/benchmarks/index.<anon@56:22>
# src/v3/types.ZodArray._parse.<anon@2302:38>
# src/v3/types.ZodTuple.items
print(analysis.get_entrypoint_coverage().frameworks_detected)
# []

items = analysis.get_method("src/v3/types.ZodTuple", "items")
for ep in items.entrypoints:
    print(ep.framework, ep.confidence, ep.rule, ep.evidence)
# heuristic heuristic heuristic.http-verb-call Promise.all
```

The first result is a `process.on("SIGINT", ...)` handler in a benchmark
script. The other two are wrong: the heuristic read `Promise.all(...)` as an
HTTP route with the verb `all`.

`get_entrypoints()` returns `TSCallableOverview` objects. They have no
`framework` or `confidence` field. To see why a callable is an entrypoint, read
`entrypoints` on its `TSCallable`, as the example does. A nested callable, for
example the second result, is in `inner_callables` of the callable that
contains it. Before you trust an empty list, call `get_entrypoint_coverage()`.

## Read source text

To read the text of a callable, use `TSCallable.code`,
`get_method_bodies([...])` or `get_source(<callable signature>)`. Do not slice
`TSModule.source` with `span.bytes` yourself. `bytes` are UTF-8 byte offsets,
but `source` is a Python `str`. The slice is wrong after the first non-ASCII
character in the file. On Zod, 80 of the 135 modules contain non-ASCII text.
Span columns count UTF-16 code units, so they also differ from Python string
positions after a character such as an emoji.

On the local backend, `get_source` and `describe` have the same problem for a
statement or a call site. For example, on Zod, `locate("src/v3/types.ts", 669)`
finds the call `timeRegexSource(args)`, but `get_source` of its `node_id`
returns `'meRegexSource(args)}$'`. Read the callable that contains the call
instead: pass `callable.signature` of the `locate` result to `get_source`.

## Choose a backend

The type of the `backend=` object selects the backend. Import the backend
configuration classes from `cldk.analysis.commons.backend_config`. The
[Core page](/reference/python-api/core/#backend-configuration) documents them.

|  | Local (default) | Neo4j |
| --- | --------------- | ----- |
| Select it with | No `backend=`, or `backend=CodeAnalyzerConfig(cache_dir=...)` | `backend=Neo4jConnectionConfig(...)` |
| Install | `pip install cldk` | `pip install "cldk[neo4j]"` and a Neo4j server |
| Who runs the analyzer | CLDK, in the `CLDK.typescript` call | You, once, with `cants --emit neo4j` |
| `project_path` | Required | Optional |
| Analysis level | The `analysis_level` that you pass | Always `system_dependency_graph` |

`TSCodeAnalyzerConfig` also selects the local backend. Its `tsc_only` flag
does nothing. `tsc_only=True` gives a `DeprecationWarning`.

### Use a Neo4j graph

1. Install the Neo4j driver:

   ```bash
   pip install "cldk[neo4j]"
   ```

2. Put the password of your Neo4j server in the `NEO4J_PASSWORD` environment
   variable. Then load the graph of your project into Neo4j. `cants` also
   writes its cache to `my-app/.codeanalyzer/`.

   ```bash
   export NEO4J_PASSWORD="<your password>"
   cants -i my-app --emit neo4j --neo4j-uri bolt://localhost:7687 --app-name my-app
   ```

   The graph always has all four levels. `cants` refuses `-a 2` or higher
   together with `--emit neo4j`.

3. Connect to the graph. Run the code in the same shell as step 2, so that
   `NEO4J_PASSWORD` is set.

   ```python
   import logging
   import os

   from cldk import CLDK
   from cldk.analysis.commons.backend_config import Neo4jConnectionConfig

   logging.getLogger("neo4j").setLevel(logging.ERROR)  # hide driver warnings

   analysis = CLDK.typescript(
       backend=Neo4jConnectionConfig(
           uri="bolt://localhost:7687",
           username="neo4j",
           password=os.environ["NEO4J_PASSWORD"],
           application_name="my-app",
       ),
   )
   print(len(analysis.get_classes()))
   ```

   Without the `logging` line, the neo4j driver prints warnings about
   relationship types that the graph does not have. They do not stop the
   analysis.

`application_name` must be the same as `--app-name`. If you do not give it,
CLDK uses the name of the `project_path` directory. The backend is read-only.
It refuses a graph from codeanalyzer-typescript before 1.5.2 with
`GraphSchemaMismatch`. For a shared graph of many projects, see
[Analysis at scale](/at-scale/).

The graph does not keep all the data. These answers are different from the
local backend:

- `get_imports`: `alias` is `None`, and the line and column fields are `-1`.
- `get_enum_members`: `value` is `None`.
- `comments` and `type_parameters` are empty on types and callables, and
  `body` is empty on callables.
- `locate`: at module scope, `source` is `''`, with a
  `module_source_unavailable` diagnostic. The columns and `bytes` of `span`
  are `0`.
- `get_source` of a statement or a call site raises `NotImplementedError`.
- `param_in` and `param_out` of the application view are empty.

:::caution[Some merged declarations stop the Neo4j backend]
In cldk 2.0.0, the TypeScript Neo4j backend cannot read a graph with some
kinds of declaration merging. In declaration merging, two or more
declarations share one name. These kinds stop the backend:

- An interface with a method has the same name as a function, a `const` or a
  class.
- A namespace with a function has the same name as a class, an enum, a
  function or an interface.
- Two interfaces or two namespaces have the same name, and the second one
  declares a method or a function.

Other kinds can also stop it. `CLDK.typescript` then raises
`ValueError: child id is not minted under its parent`. Zod has such
declarations, so use the local backend for Zod.
:::

## Errors you can see

Import the CLDK exceptions from `cldk.utils.exceptions`.
[Results and errors](/reference/python-api/results/#exceptions) documents
them. `SelectorNotInGraph` and `AmbiguousName` are subclasses of `ValueError`.

| Exception | When it happens | What to do |
| --------- | --------------- | ---------- |
| `CldkInitializationException` | `project_path` does not exist or is not a directory. | Correct the path. A relative path starts at the current directory. |
| `TypeError` | You pass an option by position, for example `CLDK.typescript("zod/packages/zod", "call_graph")` or `slice_backward("obj", "quotelessJson")`. You use an unknown keyword, for example `neo4j_config`. You call `CLDK.typescript()` with no `project_path` and no Neo4j backend. | Pass the options by keyword: `analysis_level="call_graph"`, `within="quotelessJson"`. Pass `project_path`. For a Neo4j graph, pass `backend=Neo4jConnectionConfig(...)`, not `neo4j_config`. |
| `ValueError` | `analysis_level` is not a level name, for example `"callgraph"`. Or a bound is out of range, for example `depth=0` or `page_size=0`. | Use `symbol_table`, `call_graph`, `program_dependency_graph` or `system_dependency_graph`. Give a bound of 1 or more. |
| `pydantic.ValidationError` ("validation errors for TSAnalysis") | The cache comes from cldk 1.x. | Pass `eager=True` once, or delete `<project>/.codeanalyzer`. |
| `CodeanalyzerUsageException` | You call a dataflow method on an analysis below `program_dependency_graph`. | Build the analysis again at a higher level, with `eager=True`. |
| `SelectorNotInGraph` | A name matches nothing. A value-flow method also raises it below `system_dependency_graph`. | Copy the name from the symbol table. For value flow, build at `system_dependency_graph` with `eager=True`. |
| `AmbiguousName` | A name matches more than one callable. For example, `"_parse"` matches 38 callables on Zod. | Give more of the signature, for example `"ZodString._parse"`, or pass `in_class=` or `in_module=`. `candidates` on the exception lists the matches. |
| `KeyError` | `get_source` gets an id that names nothing. | Pass a signature, or an id that CLDK returned. |
| `GraphSchemaMismatch` | Neo4j: no graph has the `application_name`, or the graph is from codeanalyzer-typescript before 1.5.2. In both cases, the message says that the graph is too old. | Check `application_name` first. If it is correct, load the graph again with `cants --emit neo4j`. |
| `CodeanalyzerExecutionException` | Neo4j: the `neo4j` driver is not installed, or you give no `application_name` and no `project_path`. Local: the analyzer fails. The message shows the command as a Python list and the exit status, not the output of the analyzer. | Run `pip install "cldk[neo4j]"`. Pass `application_name`. If the analyzer fails, copy the items of the list from the message, without the brackets, quotes and commas. Run the result in a terminal to see the output of the analyzer. |
| `neo4j.exceptions.ServiceUnavailable` | Neo4j: CLDK cannot connect to the server. | Make sure that the server runs and that `uri` is correct. |
| `neo4j.exceptions.AuthError` | Neo4j: the username or the password is wrong. | Pass the `username` and the `password` of your Neo4j server. |
| `NotImplementedError` | Neo4j: `get_source` of a statement or a call site. | Read the callable that contains it, or use the local backend. |
| `ValueError` ("child id is not minted under its parent") | Neo4j: the graph has a kind of declaration merging that the backend cannot read. See [Use a Neo4j graph](#use-a-neo4j-graph). | Use the local backend. |

## Removed in CLDK 2.0

CLDK 1.x had `get_entry_point_methods()` and
`get_service_entry_point_methods()`. Both raised `NotImplementedError`, and
CLDK 2.0 removes them. Use `get_entrypoints()` and `get_entrypoint_classes()`.

## API reference

<!-- Remove each item when the SDK docstring is fixed. -->
:::caution[Errors in the generated reference]
The reference below comes from the cldk 2.0.0 docstrings. These statements in
it are wrong:

- The `TypeScriptAnalysis` description says that `neo4j_config` selects the
  Neo4j backend. That keyword raises `TypeError`. Pass
  `backend=Neo4jConnectionConfig(...)`.
- The `slice_backward` example reads `s.truncated`. `Slice` has no
  `truncated`, so the line raises `AttributeError`. Read `s.complete`.
- The `taint` example joins `h.to.name`. On an argument hop, `to.name` is
  `None`, so the join raises `TypeError`. Use `h.to.name or h.to.kind`.
- `get_call_graph` lists the node kinds `class`, `interface`, `enum`,
  `type_alias` and `namespace`, and says that a class is the callee of
  `new X()`. The only kinds are `callable`, `module` and `external`, and
  `new X()` points at `X.constructor`.
- `paths_between` and `taint` say that the provenance of every hop is
  `["reaching-defs"]`. Only data hops have it. Control, argument, return and
  summary hops have an empty `prov`.
- `get_synthesized_callables` says that the keys are `<host>:<line:col>`
  signatures. The keys are older ids, for example
  `can://zod/typescript/src/compile.ts@18:35`. The `id` of each value is the
  callable that replaced the old id.
- `TSSpan` says that `bytes` are offsets into the `source` of the module. They
  are UTF-8 byte offsets, so `source[b0:b1]` is wrong after a non-ASCII
  character. Use `code` or `get_source`.
- `get_source` says that you can get the exact text of a statement or a call
  site from `locate`. On the local backend, the text is shifted after a
  non-ASCII character. Read the callable that contains it.
:::

<!-- CLDK:API:START -->

<!-- AUTO-GENERATED by scripts/gen_api_docs.py, do not edit by hand. -->

[![Source on GitHub](https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)](https://github.com/codellm-devkit/python-sdk) [![cldk 2.0.0](https://img.shields.io/badge/cldk-2.0.0-3776AB?logo=pypi&logoColor=white)](https://pypi.org/project/cldk/2.0.0/)

_API reference generated from cldk 2.0.0._

## Analysis

TypeScript analysis facade.

Thin, read-only query layer over the canonical `TSApplication` produced by the
codeanalyzer-typescript backend. Mirrors the method vocabulary of `JavaAnalysis` /
`PythonAnalysis` (there is no shared base class, the facades match by convention) and, like
those, delegates all indexing and query work to its backend (`TSCodeanalyzer`).

### `TypeScriptAnalysis`

```python
class TypeScriptAnalysis
```

| Method | Summary |
| ------ | ------- |
| [`get_application_view`](#typescriptanalysisget_application_view) |  |
| [`get_symbol_table`](#typescriptanalysisget_symbol_table) |  |
| [`get_modules`](#typescriptanalysisget_modules) |  |
| [`get_call_graph`](#typescriptanalysisget_call_graph) | NetworkX DiGraph of the call edges, keyed as every other accessor keys things (module file key, type/callable signature, `"<module>.<name>"` for an external), each node tagged `kind` (`module \| class \| interface \| enum \| type_alias \| namespace \| callable \| external`) and `id`. |
| [`get_external_symbols`](#typescriptanalysisget_external_symbols) | The phantom (external) call targets (imported/required library members and builtins the call graph points at) keyed `"<module>.<name>"` (e.g. `node:fs.readFileSync`, `(builtin).push`) as the call graph keys them, the wire's `can://` id on the value. |
| [`get_synthesized_callables`](#typescriptanalysisget_synthesized_callables) | The synthesized anonymous-callback endpoints the call graph points at, Jelly-resolved callbacks the symbol table never names (keyed by their `<host>:<line:col>` signature). |
| [`get_call_graph_json`](#typescriptanalysisget_call_graph_json) |  |
| [`get_callers`](#typescriptanalysisget_callers) | Callers of a method, with the connecting call-graph edge metadata, `type`, `weight` and `provenance`, the same three keys `get_call_graph` puts on an edge. (There is no `tags`: it was a schema-1.0.0 call-edge field, and schema v2's `TSCallGraphEdge` is `{src, dst, prov, weight}`.) Pass a bare signature as the first argument for module-level functions or external (phantom) targets. |
| [`get_callees`](#typescriptanalysisget_callees) | Callees of a method, with the connecting call-graph edge metadata. |
| [`get_class_call_graph`](#typescriptanalysisget_class_call_graph) | Call-graph edges reachable from a class (or one of its methods). |
| [`get_class_hierarchy`](#typescriptanalysisget_class_hierarchy) | Inheritance/implementation graph: an edge child → base for every base_class. |
| [`get_call_sites`](#typescriptanalysisget_call_sites) | The rich, syntactic call sites *inside* a callable (receiver/argument types, resolved `callee_signature`, source position). |
| [`get_calling_lines`](#typescriptanalysisget_calling_lines) | Sorted source lines anywhere in the project where `target_signature` is invoked. |
| [`get_call_targets`](#typescriptanalysisget_call_targets) | The call targets invoked from a callable, derived from its call sites. |
| [`get_classes`](#typescriptanalysisget_classes) |  |
| [`get_class`](#typescriptanalysisget_class) |  |
| [`get_classes_by_criteria`](#typescriptanalysisget_classes_by_criteria) |  |
| [`get_interfaces`](#typescriptanalysisget_interfaces) |  |
| [`get_enums`](#typescriptanalysisget_enums) |  |
| [`get_enum_members`](#typescriptanalysisget_enum_members) |  |
| [`get_type_aliases`](#typescriptanalysisget_type_aliases) |  |
| [`get_functions`](#typescriptanalysisget_functions) | Top-level (module/namespace) functions. |
| [`get_methods`](#typescriptanalysisget_methods) | All methods grouped by class/interface signature. |
| [`get_methods_in_class`](#typescriptanalysisget_methods_in_class) |  |
| [`get_method`](#typescriptanalysisget_method) |  |
| [`get_method_parameters`](#typescriptanalysisget_method_parameters) |  |
| [`get_constructors`](#typescriptanalysisget_constructors) |  |
| [`get_fields`](#typescriptanalysisget_fields) |  |
| [`get_interface_properties`](#typescriptanalysisget_interface_properties) |  |
| [`get_imports`](#typescriptanalysisget_imports) |  |
| [`get_exports`](#typescriptanalysisget_exports) |  |
| [`get_variables`](#typescriptanalysisget_variables) | Module-level variable declarations per file. |
| [`get_typescript_file`](#typescriptanalysisget_typescript_file) | File path declaring the class/interface/enum/callable with the given signature. |
| [`get_typescript_module`](#typescriptanalysisget_typescript_module) |  |
| [`get_nested_classes`](#typescriptanalysisget_nested_classes) | Always `[]` on schema v2, on both backends, permanently, not for want of data. |
| [`get_sub_classes`](#typescriptanalysisget_sub_classes) |  |
| [`get_extended_classes`](#typescriptanalysisget_extended_classes) | The base types a class extends (base_classes minus the implemented interfaces). |
| [`get_implemented_interfaces`](#typescriptanalysisget_implemented_interfaces) |  |
| [`get_decorators`](#typescriptanalysisget_decorators) | Structured decorators (with arguments) applied to a callable. |
| [`get_class_decorators`](#typescriptanalysisget_class_decorators) | Structured decorators (with arguments) applied to a class. |
| [`get_methods_with_decorators`](#typescriptanalysisget_methods_with_decorators) | Map each requested decorator name to the signatures of callables carrying it. |
| [`get_classes_with_decorators`](#typescriptanalysisget_classes_with_decorators) | Map each requested decorator name to the signatures of classes carrying it. |
| [`get_callables_overview`](#typescriptanalysisget_callables_overview) | Return a lightweight overview of every callable in the project, in one bulk read. |
| [`get_method_bodies`](#typescriptanalysisget_method_bodies) | Return source bodies for the given callable signatures, in one bulk read. |
| [`get_decorated_callables`](#typescriptanalysisget_decorated_callables) | Return overviews of callables decorated with any of the given markers, in one bulk read. |
| [`get_callsites_for`](#typescriptanalysisget_callsites_for) | Return the call sites of the given callables, keyed by signature, in one bulk read. |
| [`locate`](#typescriptanalysislocate) | Resolve a source position to its enclosing callable, with the source in hand. |
| [`locate_many`](#typescriptanalysislocate_many) | Resolve many `(path, line)` positions in one round trip, in input order. |
| [`resolve_callable`](#typescriptanalysisresolve_callable) | Resolve a callable name to the one callable it names, in the caller's vocabulary. |
| [`resolve_value`](#typescriptanalysisresolve_value) | Resolve a value name inside a callable (in TypeScript, a parameter) to the position that carries it. |
| [`get_source`](#typescriptanalysisget_source) | Return the source text named by `node_id`, a callable, or one of its body nodes. |
| [`describe`](#typescriptanalysisdescribe) | Fill in `source` for these positions, in one round trip. |
| [`get_cfg`](#typescriptanalysisget_cfg) | Return one page of the control flow inside one callable, addressed by name. |
| [`get_cdg`](#typescriptanalysisget_cdg) | Return one page of the control *dependence* inside one callable. |
| [`get_ddg`](#typescriptanalysisget_ddg) | Return one page of the data dependence inside one callable. |
| [`slice_backward`](#typescriptanalysisslice_backward) | Return everything the value `src` depends on, reverse reachability over the SDG. |
| [`slice_forward`](#typescriptanalysisslice_forward) | Return everything the value `src` can affect, the same edges read forward. |
| [`reaches`](#typescriptanalysisreaches) | Return whether control can get from one callable to another over the call graph. |
| [`backward_cone`](#typescriptanalysisbackward_cone) | Return every call-graph vertex that can reach any of `sinks`, "what could get here". |
| [`callers_of`](#typescriptanalysiscallers_of) | Return who calls this, one hop back over the call graph, addressed by name. |
| [`callees_of`](#typescriptanalysiscallees_of) | Return what this calls, one hop forward, externals included (`kind="external"`). |
| [`paths_between`](#typescriptanalysispaths_between) | Return how one value reaches another, the *sequences*, where a slice is the set. |
| [`call_paths_between`](#typescriptanalysiscall_paths_between) | Return how one callable reaches another, the evidence-carrying form of `reaches`. |
| [`flows_to_call`](#typescriptanalysisflows_to_call) | Return whether this value reaches **any** argument of a call to `callee`. |
| [`flows_to_argument`](#typescriptanalysisflows_to_argument) | Return whether this value reaches the argument `arg` of a call to `callee`. |
| [`taint`](#typescriptanalysistaint) | Which of these sources reach which of these sinks, and what to make of the ones that do not. |
| [`get_entrypoints`](#typescriptanalysisget_entrypoints) | Return overviews of every callable the analyzer marked as an entrypoint. |
| [`get_entrypoint_classes`](#typescriptanalysisget_entrypoint_classes) | Return overviews of every class the analyzer marked as an entrypoint in its own right. |
| [`get_entrypoint_coverage`](#typescriptanalysisget_entrypoint_coverage) | Return the entrypoint-detection pass's own coverage and failure record. |
| [`get_artifacts`](#typescriptanalysisget_artifacts) | Return every non-code artifact the analyzer indexed, keyed by repo-relative path. |
| [`get_dependencies`](#typescriptanalysisget_dependencies) | Return every declared dependency, optionally filtered. |
| [`get_config_keys`](#typescriptanalysisget_config_keys) | Return every configuration key the analyzer extracted from the artifacts. |
| [`get_config_uses`](#typescriptanalysisget_config_uses) | Return the resolved edges from a code read to the configuration key it names. |
| [`get_unresolved_config_reads`](#typescriptanalysisget_unresolved_config_reads) | Return every detector-matched configuration read that resolved to no declared key. |
| [`get_config_readers`](#typescriptanalysisget_config_readers) | Return overviews of every callable that reads configuration key `key`. |

Analysis facade for TypeScript projects.

Delegates every query to a backend. Two interchangeable backends exist, both exposing the
same method surface:

* `TSCodeanalyzer` (default), walks the in-memory pydantic `TSApplication` / a
  NetworkX call graph built from `analysis.json`;
* `TSNeo4jBackend`, answers the *same* `get_*` queries with Cypher over the graph
  `codeanalyzer-typescript` emits with `--emit neo4j`. Selected by passing
  `neo4j_config`.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `project_dir` |  |  |
| `analysis_level` |  |  |
| `target_files` |  |  |
| `eager_analysis` |  |  |
| `backend_config` | [`TSBackend`](/reference/python-api/core/#tsbackend) |  |
| `backend` | `TSAnalysisBackend` |  |
| `application` | [`TSApplication`](#tsapplication) |  |
| `has_resolution_edges` | `bool` | Whether `get_callsites_for` can resolve call sites on this backend right now. |

#### Methods

##### `TypeScriptAnalysis.get_application_view`

```python
get_application_view() -> TSApplication
```

##### `TypeScriptAnalysis.get_symbol_table`

```python
get_symbol_table() -> Dict[str, TSModule]
```

##### `TypeScriptAnalysis.get_modules`

```python
get_modules() -> List[TSModule]
```

##### `TypeScriptAnalysis.get_call_graph`

```python
get_call_graph() -> nx.DiGraph
```

NetworkX DiGraph of the call edges, keyed as every other accessor keys things (module
file key, type/callable signature, `"<module>.<name>"` for an external), each node
tagged `kind` (`module | class | interface | enum | type_alias | namespace | callable | external`) and `id`. TypeScript's own
endpoints are kept: a module is the caller of its top-level code and a class the callee of
`new X()`; filter on `kind == "callable"` for Python's shape.

##### `TypeScriptAnalysis.get_external_symbols`

```python
get_external_symbols() -> Dict[str, TSExternalSymbol]
```

The phantom (external) call targets (imported/required library members and builtins
the call graph points at) keyed `"<module>.<name>"` (e.g. `node:fs.readFileSync`,
`(builtin).push`) as the call graph keys them, the wire's `can://` id on the value.
Useful for source→sink reachability.

##### `TypeScriptAnalysis.get_synthesized_callables`

```python
get_synthesized_callables() -> Dict[str, TSSynthesizedCallable]
```

The synthesized anonymous-callback endpoints the call graph points at, Jelly-resolved
callbacks the symbol table never names (keyed by their `<host>:<line:col>` signature).
Empty under the `tsc`-only resolver. Materialized so anonymous call edges don't dangle.

##### `TypeScriptAnalysis.get_call_graph_json`

```python
get_call_graph_json() -> str
```

##### `TypeScriptAnalysis.get_callers`

```python
get_callers(
    target_class_name: str,
    target_method_declaration: str | None = None,
) -> Dict
```

Callers of a method, with the connecting call-graph edge metadata, `type`,
`weight` and `provenance`, the same three keys `get_call_graph` puts on an edge.
(There is no `tags`: it was a schema-1.0.0 call-edge field, and schema v2's
`TSCallGraphEdge` is `{src, dst, prov, weight}`.) Pass a bare signature as the first
argument for module-level functions or external (phantom) targets.

##### `TypeScriptAnalysis.get_callees`

```python
get_callees(
    source_class_name: str,
    source_method_declaration: str | None = None,
) -> Dict
```

Callees of a method, with the connecting call-graph edge metadata.

##### `TypeScriptAnalysis.get_class_call_graph`

```python
get_class_call_graph(
    qualified_class_name: str,
    method_signature: str | None = None,
) -> List[Tuple[str, str]]
```

Call-graph edges reachable from a class (or one of its methods).

##### `TypeScriptAnalysis.get_class_hierarchy`

```python
get_class_hierarchy() -> nx.DiGraph
```

Inheritance/implementation graph: an edge child → base for every base_class.

##### `TypeScriptAnalysis.get_call_sites`

```python
get_call_sites(qualified_callable_name: str) -> List[TSCallsite]
```

The rich, syntactic call sites *inside* a callable (receiver/argument types, resolved
`callee_signature`, source position).

##### `TypeScriptAnalysis.get_calling_lines`

```python
get_calling_lines(target_signature: str) -> List[int]
```

Sorted source lines anywhere in the project where `target_signature` is invoked.

##### `TypeScriptAnalysis.get_call_targets`

```python
get_call_targets(source_signature: str) -> Set[str]
```

The call targets invoked from a callable, derived from its call sites.

##### `TypeScriptAnalysis.get_classes`

```python
get_classes() -> Dict[str, TSClass]
```

##### `TypeScriptAnalysis.get_class`

```python
get_class(qualified_class_name: str) -> TSClass | None
```

##### `TypeScriptAnalysis.get_classes_by_criteria`

```python
get_classes_by_criteria(
    inclusions: List[str] | None = None,
    exclusions: List[str] | None = None,
) -> Dict[str, TSClass]
```

##### `TypeScriptAnalysis.get_interfaces`

```python
get_interfaces() -> Dict[str, TSInterface]
```

##### `TypeScriptAnalysis.get_enums`

```python
get_enums() -> Dict[str, TSEnum]
```

##### `TypeScriptAnalysis.get_enum_members`

```python
get_enum_members(qualified_enum_name: str) -> List[TSEnumMember]
```

##### `TypeScriptAnalysis.get_type_aliases`

```python
get_type_aliases() -> Dict[str, TSTypeAlias]
```

##### `TypeScriptAnalysis.get_functions`

```python
get_functions() -> Dict[str, TSCallable]
```

Top-level (module/namespace) functions.

##### `TypeScriptAnalysis.get_methods`

```python
get_methods() -> Dict[str, Dict[str, TSCallable]]
```

All methods grouped by class/interface signature.

##### `TypeScriptAnalysis.get_methods_in_class`

```python
get_methods_in_class(qualified_class_name: str) -> Dict[str, TSCallable]
```

##### `TypeScriptAnalysis.get_method`

```python
get_method(qualified_class_name: str, qualified_method_name: str) -> TSCallable | None
```

##### `TypeScriptAnalysis.get_method_parameters`

```python
get_method_parameters(
    qualified_class_name: str,
    qualified_method_name: str,
) -> List[str]
```

##### `TypeScriptAnalysis.get_constructors`

```python
get_constructors(qualified_class_name: str) -> Dict[str, TSCallable]
```

##### `TypeScriptAnalysis.get_fields`

```python
get_fields(qualified_class_name: str) -> List[TSClassAttribute]
```

##### `TypeScriptAnalysis.get_interface_properties`

```python
get_interface_properties(qualified_interface_name: str) -> List[TSClassAttribute]
```

##### `TypeScriptAnalysis.get_imports`

```python
get_imports() -> Dict[str, List[TSImport]]
```

##### `TypeScriptAnalysis.get_exports`

```python
get_exports() -> Dict[str, List[TSExport]]
```

##### `TypeScriptAnalysis.get_variables`

```python
get_variables() -> Dict[str, List[TSVariableDeclaration]]
```

Module-level variable declarations per file.

##### `TypeScriptAnalysis.get_typescript_file`

```python
get_typescript_file(qualified_name: str) -> str | None
```

File path declaring the class/interface/enum/callable with the given signature.

##### `TypeScriptAnalysis.get_typescript_module`

```python
get_typescript_module(file_path: str) -> TSModule | None
```

##### `TypeScriptAnalysis.get_nested_classes`

```python
get_nested_classes(qualified_class_name: str) -> List[TSClass]
```

Always `[]` on schema v2, on both backends, permanently, not for want of data. A
v2 class node holds only `callables` and `fields`: the tree gives a class no `types`
bucket, so no class can nest a class. A class declared inside a *callable* is the surviving
case and reads as `TSCallable.inner_classes`. Kept because the 1.x surface had it.

##### `TypeScriptAnalysis.get_sub_classes`

```python
get_sub_classes(qualified_class_name: str) -> Dict[str, TSClass]
```

##### `TypeScriptAnalysis.get_extended_classes`

```python
get_extended_classes(qualified_class_name: str) -> List[str]
```

The base types a class extends (base_classes minus the implemented interfaces).

##### `TypeScriptAnalysis.get_implemented_interfaces`

```python
get_implemented_interfaces(qualified_class_name: str) -> List[str]
```

##### `TypeScriptAnalysis.get_decorators`

```python
get_decorators(qualified_callable_name: str) -> List[TSDecorator]
```

Structured decorators (with arguments) applied to a callable.

##### `TypeScriptAnalysis.get_class_decorators`

```python
get_class_decorators(qualified_class_name: str) -> List[TSDecorator]
```

Structured decorators (with arguments) applied to a class.

##### `TypeScriptAnalysis.get_methods_with_decorators`

```python
get_methods_with_decorators(decorators: List[str]) -> Dict[str, List[str]]
```

Map each requested decorator name to the signatures of callables carrying it. TS
decorators are captured structurally, so this is populatable at level 1.

##### `TypeScriptAnalysis.get_classes_with_decorators`

```python
get_classes_with_decorators(decorators: List[str]) -> Dict[str, List[str]]
```

Map each requested decorator name to the signatures of classes carrying it.

##### `TypeScriptAnalysis.get_callables_overview`

```python
get_callables_overview() -> List[TSCallableOverview]
```

Return a lightweight overview of every callable in the project, in one bulk read.

A field-projected alternative to `get_methods` for enumeration: each
`TSCallableOverview` carries the callable's signature,
owning class/interface (if any), native kind, location, and decorators, but not the full
reconstruction (call sites, inner callables, locals). On the Neo4j backend this is a single
Cypher query instead of the per-entity fan-out `get_methods` pays. Body-inspect the
few you need afterwards via `get_method` or `get_method_bodies`.

**Returns:**

- [`List[TSCallableOverview]`](#tscallableoverview): A flat list of `TSCallableOverview`, one per callable
  (class/interface methods, module- and namespace-level functions, and nested/inner
  callables).

> **See Also**
>
> - `get_decorated_callables`: The same projection filtered by decorator.
> - `get_method_bodies`: Bulk source-body fetch for chosen signatures.

:::note
A `get x()`/`set x()` accessor pair shares one `signature`, so this projection
(and the other bulk accessors) can diverge between the local and Neo4j backends on a
paired accessor, see [#300](https://github.com/codellm-devkit/python-sdk/issues/300).
:::

##### `TypeScriptAnalysis.get_method_bodies`

```python
get_method_bodies(signatures: List[str]) -> Dict[str, str]
```

Return source bodies for the given callable signatures, in one bulk read.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `signatures` | `List[str]` | Callable signatures to fetch bodies for (e.g. from `get_callables_overview`). |

**Returns:**

- `Dict[str, str]`: A dict mapping each signature to its source body. Signatures with no matching callable
  are omitted, as are callables whose `code` is `None` (e.g. implicit constructors
  the analyzer synthesizes with no source text), every returned value is a real `str`.

##### `TypeScriptAnalysis.get_decorated_callables`

```python
get_decorated_callables(markers: List[str]) -> List[TSCallableOverview]
```

Return overviews of callables decorated with any of the given markers, in one bulk read.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `markers` | `List[str]` | Decorator names to match (e.g. `["Get", "Controller"]`). |

**Returns:**

- [`List[TSCallableOverview]`](#tscallableoverview): A list of `TSCallableOverview` for every callable
  carrying at least one of `markers` as a decorator.

> **See Also**
>
> - `get_callables_overview`: The unfiltered projection.

##### `TypeScriptAnalysis.get_callsites_for`

```python
get_callsites_for(signatures: List[str]) -> Dict[str, List[TSCallsite]]
```

Return the call sites of the given callables, keyed by signature, in one bulk read.

Avoids the per-callable reconstruction fan-out when you need call sites for a specific
frontier (e.g. dispatch-edge synthesis or external-reader detection).

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `signatures` | `List[str]` | Callable signatures to fetch call sites for. |

**Returns:**

- [`Dict[str, List[TSCallsite]]`](#tscallsite): A dict mapping each existing signature to its list of
  `TSCallsite` (empty if the callable has no call sites).
  Signatures with no matching callable are omitted.

##### `TypeScriptAnalysis.locate`

```python
locate(path: str, line: int) -> LocateResult
```

Resolve a source position to its enclosing callable, with the source in hand.

The single most-needed query for triaging a scanner alert: an alert arrives as
`file:line` and this resolves it to the enclosing callable in one call, rather than
`get_method`, falling back to `get_callers`, falling back to scanning the symbol table
by hand. Four outcomes stay distinguishable, see
`LocateResult`: inside a callable (`callable` set,
plus `body` when a body node is that precise), at real module scope (`module_scope`
diagnostic), in the gap between two callables (also module scope, never snapped to the
nearest callable), or in a file the analysis has no module for (`file_not_in_graph`).

There is no `col` parameter. Column-level disambiguation would have to be honoured by
both backends to mean anything, and the Neo4j graph projects only `start_line` /
`end_line` on `:TSCallable` and `:TSBodyNode`, so a `col` would work in-process and
be silently ignored over Neo4j. Better absent than documented and inert.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `path` | `str` | The file path. Normalised against the backend's module keys, so a `./`-prefixed or absolute path resolves rather than reading back as `file_not_in_graph`. |
| `line` | `int` | The 1-based line number. |

**Returns:**

- [`LocateResult`](/reference/python-api/results/#locateresult): A `LocateResult` carrying the innermost body
  node, the enclosing callable, its owning class/interface, its module, and the source
  slice, never an ambiguous empty.

> **See Also**
>
> - `locate_many`: The bulk form, the point, not an optimisation.

##### `TypeScriptAnalysis.locate_many`

```python
locate_many(positions: Sequence[Tuple[str, int]]) -> List[LocateResult]
```

Resolve many `(path, line)` positions in one round trip, in input order.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `positions` | `Sequence[Tuple[str, int]]` | The `(path, line)` pairs to resolve, e.g. from a scanner's alert list. |

**Returns:**

- [`List[LocateResult]`](/reference/python-api/results/#locateresult): One `LocateResult` per input position, in the
  same order.

> **See Also**
>
> - `locate`: The single-position form.

##### `TypeScriptAnalysis.resolve_callable`

```python
resolve_callable(
    name: str,
    *,
    in_class: str | None = None,
    in_module: str | None = None,
) -> SliceNode
```

Resolve a callable name to the one callable it names, in the caller's vocabulary.

The addressing step every name-taking accessor performs, exposed so a caller can perform it
once and keep the answer:

```python
node = ts.resolve_callable("show", in_class="UserController")
node.callable   # the full dotted signature — what every other accessor keys by
node.file, node.line
```

`name` matches whole or as a dotted suffix; `in_class` is a dotted suffix of the owning
class or interface, `in_module` a module key (`"src/controllers.ts"`) or the dotted form
(`"src.controllers"`). An anonymous callable is addressed by its `<anon@line:col>`
signature, never by its name, cants calls every one of them `"(anonymous)"`. Ambiguity
raises with every candidate; nothing is guessed.

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): More than one callable matched.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): Nothing matched, naming the argument that missed.

##### `TypeScriptAnalysis.resolve_value`

```python
resolve_value(name: str, *, within: str) -> SliceNode
```

Resolve a value name inside a callable (in TypeScript, a parameter) to the position
that carries it.

The same resolution the dataflow accessors perform on their `src`, exposed so a caller can
check what a name means before asking a question of it:

```python
ts.resolve_value("id", within="UserController.show").kind   # "parameter"
```

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): `within` named more than one callable, or `name` more than one value.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): No such callable, or no such value in it.

##### `TypeScriptAnalysis.get_source`

```python
get_source(node_id: str) -> str
```

Return the source text named by `node_id`, a callable, or one of its body nodes.

Generalises `get_method_bodies` below callable granularity: `node_id` is a
callable's signature, a callable's opaque id, or the body-node id
`node_id` hands back, so a statement or
call site `locate` found can be re-fetched precisely.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `node_id` | `str` | A callable signature, or an id from `locate` / `resolve_callable`, passed back as received, not composed. |

**Returns:**

- `str`: The source text, never an ambiguous empty string.

**Raises:**

- `KeyError`: Nothing matches `node_id`, or it has no recoverable source.
- `NotImplementedError`: (Neo4j backend only) `node_id` names a body node, the attached
  graph carries no source text below callable granularity.

##### `TypeScriptAnalysis.describe`

```python
describe(nodes: Sequence[object]) -> List[SliceNode]
```

Fill in `source` for these positions, in one round trip.

Addressing answers *where*; this answers *what*, and it is a second call because source is
the one field with no size ceiling. Takes anything carrying an address (slice nodes, a
`locate()` result) and gives back the same
`SliceNode` shape with `source` filled.

Afterwards, `source=None` means exactly one thing: **this position exists and there is no
text for it.** A ref that names nothing raises instead.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `nodes` | `Sequence[object]` | The positions to hydrate. An empty sequence costs no round trip. |

**Returns:**

- [`List[SliceNode]`](/reference/python-api/results/#slicenode): The same positions, in the same order, with `source` filled where the backend has
  text for them.

**Raises:**

- `KeyError`: A ref names nothing in this application.
- `TypeError`: An element carries no address to look up.

##### `TypeScriptAnalysis.get_cfg`

```python
get_cfg(
    callable: str,
    *,
    in_class: str | None = None,
    page_size: int = 10000,
    cursor: str | None = None,
) -> EdgePage[TSCfgEdge]
```

Return one page of the control flow inside one callable, addressed by name.

The graph the analyzer built, not one re-derived here: a conditional's two successors stay
two edges discriminated by `kind`. Endpoints are the body nodes' own opaque ids, which
`get_source` and `describe` both accept:

```python
page = ts.get_cfg("show", in_class="UserController")
page.total          # the whole graph's size, on every page
page.complete       # False when there is more, with page.next_cursor to fetch it
```

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `callable` | `str` | The callable's name, resolved as by `resolve_callable`. |
| `in_class` | `str \| None` | Disambiguate by owning class or interface. |
| `page_size` | `int` | Most edges to return. Default: [`DEFAULT_PAGE_SIZE`](/reference/python-api/results/#default_page_size) (10000). |
| `cursor` | `str \| None` | `next_cursor` from a previous page; `None` starts at the beginning. |

**Returns:**

- [`EdgePage[TSCfgEdge]`](/reference/python-api/results/#edgepage): An `EdgePage` of
  `TSCfgEdge`.

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): More than one callable matched.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): Nothing matched.
- `ValueError`: `page_size` below 1, or a cursor from another page, callable or accessor.
- [`CodeanalyzerUsageException`](/reference/python-api/results/#codeanalyzerusageexception): (local backend) built below
  `analysis_level="program_dependency_graph"`.

##### `TypeScriptAnalysis.get_cdg`

```python
get_cdg(
    callable: str,
    *,
    in_class: str | None = None,
    page_size: int = 10000,
    cursor: str | None = None,
) -> EdgePage[TSCdgEdge]
```

Return one page of the control *dependence* inside one callable.

`src` is the branching node `dst` is control dependent on. Arguments, paging and
failures are `get_cfg`'s.

##### `TypeScriptAnalysis.get_ddg`

```python
get_ddg(
    callable: str,
    *,
    in_class: str | None = None,
    page_size: int = 10000,
    cursor: str | None = None,
) -> EdgePage[TSDdgEdge]
```

Return one page of the data dependence inside one callable.

Each edge carries the variable it flows and the evidence for it. **TypeScript has a single
provenance tier:** every edge's `prov` is `["reaching-defs"]`, where Python distinguishes
`ssa` / `reaching-defs` / `points-to`. Arguments, paging and failures are
`get_cfg`'s.

##### `TypeScriptAnalysis.slice_backward`

```python
slice_backward(
    src: str,
    *,
    within: str,
    depth: int | None = 5,
    max_nodes: int = 10000,
) -> Slice
```

Return everything the value `src` depends on, reverse reachability over the SDG.

`depth` defaults to a **finite** bound on purpose: a bounded traversal answers a narrower
question *completely*, and `total` says how much was left out. `depth=None` asks for the
whole cone:

```python
s = ts.slice_backward("id", within="UserController.show")
s.total, s.truncated
```

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` | The value's name, in TypeScript, a parameter. |
| `within` | `str` | The callable to look inside. Required: a value name is scoped by its callable. |
| `depth` | `int \| None` | Most hops from the seed; `None` for the whole cone. Default: [`DEFAULT_DEPTH`](/reference/python-api/results/#default_depth) (5). |
| `max_nodes` | `int` | Most nodes in the result; a cap that fires is reported, never silent. Default: [`DEFAULT_MAX_NODES`](/reference/python-api/results/#default_max_nodes) (10000). |

**Returns:**

- [`Slice`](/reference/python-api/results/#slice): A `Slice`, ordered by node id, with `source`
  unhydrated (`describe` fills it in).

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): `within` or `src` matched more than one thing.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): No such callable, or no such value in it.
- `ValueError`: `depth` is not a positive `int`, or `max_nodes` is below 1.

##### `TypeScriptAnalysis.slice_forward`

```python
slice_forward(
    src: str,
    *,
    within: str,
    depth: int | None = 5,
    max_nodes: int = 10000,
) -> Slice
```

Return everything the value `src` can affect, the same edges read forward.

Usually the interesting direction for a parameter: nothing flows *into* one except from its
callers. Arguments, bounds and failures are `slice_backward`'s.

##### `TypeScriptAnalysis.reaches`

```python
reaches(src: str, dst: str, *, depth: int | None = None) -> bool
```

Return whether control can get from one callable to another over the call graph.

The cheap check before asking for the paths themselves. **`depth` is unbounded by
default**, unlike the slices: a bound on a boolean would collapse "there is no path" and
"there is no path within five hops" into the same `False`.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` | The calling callable's name. |
| `dst` | `str` | The called callable's name. |
| `depth` | `int \| None` | Most call hops, or `None` for any distance. |

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): Either name matched more than one callable.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): Either matched none.
- `ValueError`: `depth` is not a positive `int`.

##### `TypeScriptAnalysis.backward_cone`

```python
backward_cone(
    sinks: Sequence[str],
    *,
    depth: int | None = 5,
    max_nodes: int = 10000,
) -> Slice
```

Return every call-graph vertex that can reach any of `sinks`, "what could get here".

The accessor to reach for when the sink is a dangerous function and the question is which
entry points lead to it. Its nodes are callables **and modules**: cants makes a module the
caller of its own top-level code, so a cone without them would under-report.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `sinks` | `Sequence[str]` | The callables to walk back from; a bare string is refused. |
| `depth` | `int \| None` | Most call hops back; `None` for the whole cone. Default: [`DEFAULT_DEPTH`](/reference/python-api/results/#default_depth) (5). |
| `max_nodes` | `int` | Most nodes in the result. Default: [`DEFAULT_MAX_NODES`](/reference/python-api/results/#default_max_nodes) (10000). |

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): A sink matched more than one callable.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): A sink matched none.
- `TypeError`: `sinks` is a bare string.
- `ValueError`: `sinks` is empty, or a bound is out of range.

##### `TypeScriptAnalysis.callers_of`

```python
callers_of(
    name: str,
    *,
    in_class: str | None = None,
    in_module: str | None = None,
) -> List[SliceNode]
```

Return who calls this, one hop back over the call graph, addressed by name.

The name-based sibling of `get_callers`, returning
`SliceNode` objects rather than raw dicts. A module is
a legitimate caller (`kind="module"`). `[]` is unambiguous: a name matching nothing
raises.

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): More than one callable matched.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): Nothing matched.

##### `TypeScriptAnalysis.callees_of`

```python
callees_of(
    name: str,
    *,
    in_class: str | None = None,
    in_module: str | None = None,
) -> List[SliceNode]
```

Return what this calls, one hop forward, externals included (`kind="external"`).

An external was never analysed, so it has no position: `file=""` and `line=0`, with
`kind` saying why. Its `callable` is the readable `"<module>.<name>"`.

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): More than one callable matched.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): Nothing matched.

##### `TypeScriptAnalysis.paths_between`

```python
paths_between(
    src: str,
    dst: str,
    *,
    src_within: str,
    dst_within: str,
    depth: int | None = None,
    max_paths: int = 10,
) -> FlowPaths
```

Return how one value reaches another, the *sequences*, where a slice is the set.

Each hop says what justified it: the kind of edge (`data` / `control` / `argument` /
`return` / `summary`), the variable, and the provenance, which in TypeScript is always
`["reaching-defs"]`. Only shortest paths are returned.

**Two scopes, not one**: a value is addressed by a name plus the callable it enters, and a
single scope could never find the cross-callable path this accessor exists for. `depth` is
unbounded by default, for `reaches`'s reason.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` | The value the flow starts at. |
| `dst` | `str` | The value it must reach. |
| `src_within` | `str` | The callable `src` enters. Required. |
| `dst_within` | `str` | The callable `dst` enters. Required. |
| `depth` | `int \| None` | Most hops a path may take; `None` for no bound. |
| `max_paths` | `int` | Most paths to return; `complete` says whether more existed. Default: [`DEFAULT_MAX_PATHS`](/reference/python-api/results/#default_max_paths) (10). |

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): A name matched more than one thing.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): A name matched nothing.
- `ValueError`: A bound is out of range, or the two endpoints are the same position.

##### `TypeScriptAnalysis.call_paths_between`

```python
call_paths_between(
    src: str,
    dst: str,
    *,
    depth: int | None = None,
    max_paths: int = 10,
) -> FlowPaths
```

Return how one callable reaches another, the evidence-carrying form of `reaches`.

Every hop is `via="call"` with no variable and no provenance: a call is a syntactic fact,
and saying so is better than inventing a provenance for it. `depth` is unbounded by
default.

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): Either name matched more than one callable.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): Either matched nothing.
- `ValueError`: A bound is out of range, or `src` and `dst` name the same callable.

##### `TypeScriptAnalysis.flows_to_call`

```python
flows_to_call(src: str, callee: str, *, within: str, depth: int | None = None) -> bool
```

Return whether this value reaches **any** argument of a call to `callee`.

A dataflow claim, not a control one: a value that merely runs before a call site and feeds
none of its arguments is not counted. `depth` is unbounded by default, a bare `False`
carries no signal that a bound fired.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` | The value, named as a caller would. |
| `callee` | `str` | The called callable. |
| `within` | `str` | The callable `src` enters. Required; it scopes `src` only. |
| `depth` | `int \| None` | Most hops; `None` for no bound. |

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): A name matched more than one thing.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): A name matched nothing.
- `ValueError`: `depth` is not a positive `int`.

##### `TypeScriptAnalysis.flows_to_argument`

```python
flows_to_argument(
    src: str,
    callee: str,
    arg: str,
    *,
    within: str,
    depth: int | None = None,
) -> bool
```

Return whether this value reaches the argument `arg` of a call to `callee`.

The narrower question: a tainted value routinely reaches a function without reaching the
parameter that matters. `arg` is resolved **by name**, never by position.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` | The value the flow starts at. |
| `callee` | `str` | The called callable. |
| `arg` | `str` | The callee's parameter, by name. |
| `within` | `str` | The callable `src` enters. Required; `arg` is scoped by `callee`. |
| `depth` | `int \| None` | Most hops; `None` for no bound. |

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): A name matched more than one thing.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): A name matched nothing, including `arg` naming no parameter of
  `callee`, which is a caller error and not a `False`.
- `ValueError`: `depth` is not a positive `int`.

##### `TypeScriptAnalysis.taint`

```python
taint(
    sources: Sequence[Tuple[str, str]],
    sinks: Sequence[Tuple[str, str]],
    sanitizers: Sequence[Tuple[str, str] | str] = (),
    *,
    depth: int | None = None,
    max_paths: int = 10,
) -> TaintResult
```

Which of these sources reach which of these sinks, and what to make of the ones that do not.

m sources against n sinks in one traversal, where `paths_between` proves one flow:

```python
r = ts.taint(
    sources=[("userInput", "SearchBar.onChange")],
    sinks=[("html", "ResultList.render")],
    sanitizers=["SearchBar.sanitizeQuery", ("validated", "SearchBar.onChange")],
)
for path in r.paths:
    print(" -> ".join(h.to.name for h in path.hops))
for src, sink in r.exhausted:
    print(src, "does not reach", sink)
```

**`exhausted` is the reason to call this and the only output that can do harm.** A pair is
listed there when it was searched to exhaustion and nothing was found (the refutation
`paths_between`'s `[]` cannot give) and only when all three hold: no witness, no
diagnostic in `unresolved` implicating it, and **`depth` was `None`**. An explicit
`depth` empties `exhausted` by rule, because a bound turns a real long flow into an empty
result and a wrong refutation closes a live alert.

**`complete` is the batch's flag, not the pair's.** While it is `False`, no absence claim
stands on any pair in the result: one blocked pair voids the whole batch's `exhausted`.

**Sources, sinks and sanitizers are the caller's to supply**: no framework catalogue ships
here. A bare `str` cuts a *callable* on the path: a transforming sanitizer, named as the
wrapper *in this application* that calls `encodeURIComponent`, because the bare shape is
resolved with `resolve_callable`. A `(name, within)` pair cuts a *variable* inside
that callable, which is the only thing that severs a *validating* guard, since a guard never
sits on the data path. Both cuts are applied inside the search, so the result is the shortest
**unsanitized** route.

Every hop's provenance is `reaching-defs`, as on `paths_between`, so a TypeScript
witness is argued from its hops rather than from a provenance comparison between two of them.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `sources` | `Sequence[Tuple[str, str]]` | The values taint enters at, each `(name, within)`. |
| `sinks` | `Sequence[Tuple[str, str]]` | The values it must not reach, addressed the same way. |
| `sanitizers` | `Sequence[Tuple[str, str] \| str]` | Bare names cut callables; `(name, within)` pairs cut variables. |
| `depth` | `int \| None` | Most hops; `None` (the default) for no bound, and `exhausted` is empty whenever it is set. |
| `max_paths` | `int` | Most witnesses **per pair**, not per call. Default: [`DEFAULT_MAX_PATHS`](/reference/python-api/results/#default_max_paths) (10). |

**Raises:**

- [`AmbiguousName`](/reference/python-api/results/#ambiguousname): A name, or a sanitizer's `within`, matched more than one thing.
- [`SelectorNotInGraph`](/reference/python-api/results/#selectornotingraph): A name matched nothing, or a sanitizer's shape disagrees with what it
  resolves to.
- `TypeError`: `sources` or `sinks` is a bare string, which would unpack into a pair.
- `ValueError`: A bound is out of range, `sources` or `sinks` is empty, or a sanitizer
  names a blank variable.

##### `TypeScriptAnalysis.get_entrypoints`

```python
get_entrypoints() -> List[TSCallableOverview]
```

Return overviews of every callable the analyzer marked as an entrypoint.

A CLI command, a route handler, whatever ruleset the entrypoint pass matched. This is
where an agent starts a taint question: the callables reachable from outside.

**Returns:**

- [`List[TSCallableOverview]`](#tscallableoverview): One overview per marked callable. Empty means the pass found no entrypoint
  *callables*, a real fact about the project, not "cannot tell".

> **See Also**
>
> - `get_entrypoint_classes`: The class-level sibling this walk never sees.
> - `get_entrypoint_coverage`: Whether the detection pass itself had gaps.

##### `TypeScriptAnalysis.get_entrypoint_classes`

```python
get_entrypoint_classes() -> List[TSClassOverview]
```

Return overviews of every class the analyzer marked as an entrypoint in its own right.

`get_entrypoints` walks callables only, so a class the rulesets matched with no
individually-marked method is invisible to it.

**Returns:**

- [`List[TSClassOverview]`](#tsclassoverview): One overview per marked class. Empty means no class carries the mark.

> **See Also**
>
> - `get_entrypoints`: The callable-level projection.

##### `TypeScriptAnalysis.get_entrypoint_coverage`

```python
get_entrypoint_coverage() -> EntrypointCoverage
```

Return the entrypoint-detection pass's own coverage and failure record.

Entrypoint detection under-approximates by design, so silence is its failure mode:
`get_entrypoints` returning `[]` cannot say whether the pass ran clean or gave up.
This is what distinguishes them, the frameworks it recognized, the rulesets it consulted,
the near-misses it could not resolve, and the errors it hit.

**Returns:**

- [`EntrypointCoverage`](/reference/python-api/results/#entrypointcoverage): The coverage record. A non-empty `diagnostics` means the source carries no report at
  all, and the other fields are then not "no gaps found" but "nothing to report from".

> **See Also**
>
> - `get_entrypoints`: The accessor whose empty result this disambiguates.

##### `TypeScriptAnalysis.get_artifacts`

```python
get_artifacts() -> Dict[str, PyArtifact]
```

Return every non-code artifact the analyzer indexed, keyed by repo-relative path.

`package.json`, `tsconfig.json`, a lockfile, a Dockerfile, the files that say what the
project depends on and how it is configured, which the code itself never states.

**Returns:**

- [`Dict[str, PyArtifact]`](/reference/python-api/python/#pyartifact): `{path: artifact}`. Each artifact carries its roles, its text and the config keys it
  defines.

> **See Also**
>
> - `get_dependencies`, `get_config_keys`, `get_config_uses`.

##### `TypeScriptAnalysis.get_dependencies`

```python
get_dependencies(
    *,
    direct_only: bool = False,
    ecosystem: str | None = None,
    declared_in: str | None = None,
) -> List[PyDependency]
```

Return every declared dependency, optionally filtered.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `direct_only` | `bool` | Keep only dependencies the project declares itself, not transitive ones. |
| `ecosystem` | `str \| None` | Keep only one packaging ecosystem. Every TypeScript dependency is `npm`. |
| `declared_in` | `str \| None` | Keep only dependencies declared by one artifact (`PyDependency.declared_in`, e.g. from `get_artifacts`). |

**Returns:**

- [`List[PyDependency]`](/reference/python-api/python/#pydependency): The matching dependencies.

##### `TypeScriptAnalysis.get_config_keys`

```python
get_config_keys() -> Dict[str, PyConfigKey]
```

Return every configuration key the analyzer extracted from the artifacts.

**Returns:**

- [`Dict[str, PyConfigKey]`](/reference/python-api/python/#pyconfigkey): `{id: key}`. Each value carries the key's dotted name, its namespace and its literal
  value as text.

##### `TypeScriptAnalysis.get_config_uses`

```python
get_config_uses(key: str | None = None) -> List[PyConfigUseEdge]
```

Return the resolved edges from a code read to the configuration key it names.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `key` | `str \| None` | Keep only edges naming this key by its dotted name (e.g. `"compilerOptions.strict"`), matched against `get_config_keys`, since the edge itself carries ids. |

**Returns:**

- [`List[PyConfigUseEdge]`](/reference/python-api/python/#pyconfiguseedge): The matching edges.

> **See Also**
>
> - `get_config_readers`: The same edges, resolved to their reading callables.
> - `get_unresolved_config_reads`: The reads this cannot show.

##### `TypeScriptAnalysis.get_unresolved_config_reads`

```python
get_unresolved_config_reads() -> List[PyConfigRead]
```

Return every detector-matched configuration read that resolved to no declared key.

`get_config_uses` can only show reads that landed on a key the analyzer extracted. A
read of a key defined somewhere it does not index resolves to nothing, and an empty
`get_config_uses` for some key cannot then distinguish "nothing reads this" from "a
read exists and never resolved". This is that second list.

**Returns:**

- [`List[PyConfigRead]`](/reference/python-api/python/#pyconfigread): The unresolved reads, each naming the call site and the callee it went through.

##### `TypeScriptAnalysis.get_config_readers`

```python
get_config_readers(key: str) -> List[TSCallableOverview]
```

Return overviews of every callable that reads configuration key `key`.

`get_config_uses` hands back opaque body-node ids; this answers the question a caller
actually has, *which code* reads this setting.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `key` | `str` | The key's dotted name, exactly as `get_config_uses` matches it. |

**Returns:**

- [`List[TSCallableOverview]`](#tscallableoverview): One overview per reading callable. Empty means no callable reads this key, see
  `get_unresolved_config_reads` for the read that never resolved to one.

## Schema

TypeScript model package, pydantic mirror of codeanalyzer-typescript `src/schema/schema.ts` (schema v2).

`TSCallEdge`, `TSExternalSymbol`, `TSSynthesizedCallable`, `TSClassAttribute`, `TSEnumMember` and
`TSVariableDeclaration` are 1.x names kept as aliases of their v2 classes.

`TSCallsite` and `TSSymbol` are 1.x *shapes* the v2 wire no longer carries, kept importable for
the same reason: `TSCallsite` is still the return type of the call-site accessors, rebuilt from a
`body` node; `TSSymbol` has no v2 counterpart at all (accessed symbols left the schema) and no
accessor returns one, it is an import alias and nothing more.

### `TSAnalysis`

```python
class TSAnalysis(BaseModel)
```

The envelope `analysis.json` IS.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `schema_version` | `str` |  |  |
| `language` | `str` |  |  |
| `max_level` | `int` |  |  |
| `k_limit` | `Optional[int]` | `None` |  |
| `analyzer` | [`TSAnalyzer`](#tsanalyzer) |  |  |
| `application` | [`TSApplication`](#tsapplication) |  |  |

### `TSAnalyzer`

```python
class TSAnalyzer(BaseModel)
```

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `name` | `str` |  |
| `version` | `str` |  |

### `TSApplication`

```python
class TSApplication(BaseModel)
```

The application root: the containment tree plus the app-scope overlays.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `kind` | `Literal['application']` | `'application'` |  |
| `symbol_table` | [`Dict[str, TSModule]`](#tsmodule) |  |  |
| `call_graph` | [`List[TSCallGraphEdge]`](#tscallgraphedge) | `[]` |  |
| `param_in` | [`List[TSParamEdge]`](#tsparamedge) | `[]` |  |
| `param_out` | [`List[TSParamEdge]`](#tsparamedge) | `[]` |  |
| `artifacts` | [`Dict[str, TSArtifact]`](#tsartifact) | `{}` |  |
| `dependencies` | [`List[TSDependency]`](#tsdependency) | `[]` |  |
| `unresolved_imports` | [`List[TSImportBinding]`](#tsimportbinding) | `[]` |  |
| `config_uses` | [`List[TSConfigUse]`](#tsconfiguse) | `[]` |  |
| `config_reads` | [`List[TSConfigRead]`](#tsconfigread) | `[]` |  |
| `external_symbols` | [`Optional[Dict[str, TSExternalNode]]`](#tsexternalnode) | `None` |  |
| `synthesized_callables` | [`Optional[Dict[str, TSSynthesizedNode]]`](#tssynthesizednode) | `None` |  |
| `entrypoint_report` | [`Optional[TSEntrypointReport]`](#tsentrypointreport) | `None` |  |

### `TSArtifact`

```python
class TSArtifact(BaseModel)
```

A recognized non-code file (config, manifest, CI, container spec).

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `kind` | `Literal['artifact']` | `'artifact'` |  |
| `path` | `str` |  |  |
| `format` | `str` |  |  |
| `roles` | `List[str]` | `[]` |  |
| `size_bytes` | `int` |  |  |
| `sha256` | `str` |  |  |
| `source` | `str` |  |  |
| `extraction` | `str` |  |  |
| `config_keys` | [`List[TSConfigKey]`](#tsconfigkey) | `[]` |  |

### `TSBodyNode`

```python
class TSBodyNode(BaseModel)
```

One entry of a callable's `body{}` map, keyed by local id (`L:C` or `@tag`).

`kind` is open: L1 emits `call`/`config_access`, L3 adds `statement`/`entry`/`exit`,
L4 adds `formal_in`/`formal_out`/`actual_in`/`actual_out`. `callee` is the one
sanctioned `null` on the wire (a `call` node at L1, refined to an id at L2).

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `Optional[str]` | `None` |  |
| `kind` | `str` |  |  |
| `span` | [`Optional[TSSpan]`](#tsspan) | `None` |  |
| `callee` | `Optional[str]` | `None` |  |
| `of` | `Optional[str]` | `None` |  |
| `parent` | `Optional[str]` | `None` |  |
| `method_name` | `Optional[str]` | `None` |  |
| `receiver_expr` | `Optional[str]` | `None` |  |
| `receiver_type` | `Optional[str]` | `None` |  |
| `argument_types` | `List[str]` | `[]` |  |
| `type_arguments` | `List[str]` | `[]` |  |
| `return_type` | `Optional[str]` | `None` |  |
| `is_constructor_call` | `bool` | `False` |  |
| `is_optional_chain` | `bool` | `False` |  |
| `root` | `Optional[str]` | `None` |  |
| `key` | `Optional[str]` | `None` |  |

### `TSCallEdge`

```python
TSCallEdge = TSCallGraphEdge
```

Alias of [`TSCallGraphEdge`](#tscallgraphedge).

### `TSCallGraphEdge`

```python
class TSCallGraphEdge(BaseModel)
```

A wire call-graph edge: `can://` endpoints, open provenance tokens (`tsc`, `defuse`,
`import`, …).

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `src` | `str` |  |  |
| `dst` | `str` |  |  |
| `prov` | `List[str]` | `[]` |  |
| `weight` | `int` | `1` |  |

### `TSCallable`

```python
class TSCallable(BaseModel)
```

A function / method / constructor / accessor / arrow function.

`cfg`/`cdg`/`ddg` are present from L3, `summary` from L4; `None` means the level did
not compute them, `[]` means it did and found none.

#### Attributes

Inherited from `_Spanned` (`span`, `start_line`, `end_line`, `start_column`, `end_column`, `code`): A node with a mandatory span. `start_line`/`end_line`/`start_column`/`end_column` are the 1.x attribute paths, read off `span`; `code` is sliced from the owning module's `source`, which `TSModule` threads in after validation.

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |
| `code` | `Optional[str]` |  | The node's source text, `module.source` between the span's **UTF-8 byte** offsets. `None` until the node has been validated as part of a `TSModule`. |
| `id` | `str` |  |  |
| `kind` | `str` | `'function'` |  |
| `name` | `str` |  |  |
| `signature` | `str` |  |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `decorators` | [`List[TSDecorator]`](#tsdecorator) | `[]` |  |
| `parameters` | [`List[TSCallableParameter]`](#tscallableparameter) | `[]` |  |
| `type_parameters` | [`List[TSTypeParameter]`](#tstypeparameter) | `[]` |  |
| `return_type` | `Optional[str]` | `None` |  |
| `cyclomatic_complexity` | `int` | `0` |  |
| `accessibility` | `Optional[str]` | `None` |  |
| `is_static` | `bool` | `False` |  |
| `is_abstract` | `bool` | `False` |  |
| `is_async` | `bool` | `False` |  |
| `is_generator` | `bool` | `False` |  |
| `is_optional` | `bool` | `False` |  |
| `is_readonly` | `bool` | `False` |  |
| `is_exported` | `bool` | `False` |  |
| `is_ambient` | `bool` | `False` |  |
| `is_implicit` | `bool` | `False` |  |
| `accessor_kind` | `Optional[str]` | `None` |  |
| `overload_signatures` | [`List[TSOverloadSignature]`](#tsoverloadsignature) | `[]` |  |
| `body` | [`Dict[str, TSBodyNode]`](#tsbodynode) | `{}` |  |
| `callables` | [`Dict[str, TSCallable]`](#tscallable) | `{}` |  |
| `types` | [`Dict[str, TSType]`](#tstype) | `{}` |  |
| `cfg` | [`Optional[List[TSCfgEdge]]`](#tscfgedge) | `None` |  |
| `cdg` | [`Optional[List[TSCdgEdge]]`](#tscdgedge) | `None` |  |
| `ddg` | [`Optional[List[TSDdgEdge]]`](#tsddgedge) | `None` |  |
| `summary` | [`Optional[List[TSSummaryEdge]]`](#tssummaryedge) | `None` |  |
| `entrypoints` | [`Optional[List[TSEntrypoint]]`](#tsentrypoint) | `None` |  |
| `is_entrypoint` | `Optional[bool]` | `None` |  |
| `inner_callables` | [`Dict[str, TSCallable]`](#tscallable) |  |  |
| `inner_classes` | [`Dict[str, TSClass]`](#tsclass) |  |  |

### `TSCallableOverview`

```python
class TSCallableOverview(BaseModel)
```

A lightweight projection of one callable, enough to enumerate and filter without the full
`TSCallable` reconstruction (call-sites, inner callables,
locals).

Returned set-at-a-time by `TypescriptAnalysis.get_callables_overview` /
`TypescriptAnalysis.get_decorated_callables`. Body-inspect only the few you need afterwards
via `TypescriptAnalysis.get_method`/`TypescriptAnalysis.get_method_bodies`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `signature` | `str` |  | The callable's unique signature (the key the call graph references). |
| `name` | `str` |  | The callable's short name. |
| `owner_signature` | `Optional[str]` | `None` | Signature of the class/interface that declares this callable, or `None` for a module-level function, arrow, or namespace-owned function. |
| `owner_kind` | `Optional[str]` | `None` | The owner's node kind (a closed two-value set, `"class"` or `"interface"`) or `None` when there is no owner. `owner_kind` is `None` iff `owner_signature` is `None`. Namespace-owned functions (`TSNamespace.functions`) carry no owner pair; their dotted signature already encodes the namespace path. |
| `kind` | `str` |  | The callable's native TS kind, passed through verbatim, one of `function`, `method`, `constructor`, `getter`, `setter`, `arrow`, `function_expression`. Never derived; always `TSCallable.kind` as reported by the analyzer. |
| `path` | `str` |  | Project-relative path of the declaring module. |
| `start_line` | `int` |  | The callable's line span. |
| `end_line` | `int` |  | The callable's line span. |
| `decorators` | `List[str]` | `[]` | The decorator names applied to the callable (`TSDecorator.name` only). Order is not part of the cross-backend contract, the in-memory backend preserves source order, the Neo4j backend aggregates with `collect(DISTINCT ...)`, which does not guarantee order (and also dedupes duplicate names; see #300). |
| `is_exported` | `bool` |  | Whether the callable (or its enclosing declaration) is exported. |
| `is_async` | `bool` |  | Whether the callable is declared `async`. |
| `is_static` | `bool` |  | Whether the callable is a static class member. |
| `accessibility` | `Optional[str]` | `None` | The callable's declared accessibility (`public`/`protected`/`private`), or `None` when unspecified. |

#### Methods

##### `TSCallableOverview.from_callable`

```python
@classmethod
from_callable(
    c: TSCallable,
    owner_signature: Optional[str],
    owner_kind: Optional[str],
    *,
    path: str,
) -> TSCallableOverview
```

Project a `TSCallable` into a
`TSCallableOverview`.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `c` | [`TSCallable`](#tscallable) | The callable to project. |
| `owner_signature` | `Optional[str]` | Signature of the declaring class/interface, or `None` for a module-level function, arrow, or namespace-owned function. |
| `owner_kind` | `Optional[str]` | The owner's node kind (`"class"` or `"interface"`), or `None` when `owner_signature` is `None`. |
| `path` | `str` | The declaring module's symbol-table key (repo-relative path). The v2 callable does not carry it; the caller iterating `symbol_table` does. |

**Returns:**

- [`TSCallableOverview`](#tscallableoverview): The projected overview.

### `TSClassOverview`

```python
class TSClassOverview(BaseModel)
```

A lightweight projection of one class, the class-level counterpart to
`TSCallableOverview`, for classes codeanalyzer-typescript marked as entrypoints in
their own right (`TSClass.is_entrypoint`), independently of any individual method.

Returned by `TypeScriptAnalysis.get_entrypoint_classes`. It mirrors
`PyClassOverview` field for field, because the accessor that
returns it mirrors `PythonAnalysis.get_entrypoint_classes`.

**Classes only, on purpose.** `is_entrypoint` is declared on all five TypeScript type kinds
(`TSClass`/`TSInterface`/`TSEnum`/`TSTypeAlias`/`TSNamespace` all inherit it), but
the Neo4j projection stamps it onto `:TSCallable` and `:TSClass` nodes only, measured on
the 1.3.0 reference graph, where those are the only two labels carrying the property at all.
Widening this accessor past classes would therefore answer differently on the two backends,
which is the one thing the query surface may not do.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `signature` | `str` |  | The class's unique signature. |
| `name` | `str` |  | The class's short name. |
| `path` | `str` |  | Project-relative path of the declaring module. `TSClass` carries no `path` field of its own, this is the owning module's key. |
| `start_line` | `int` |  | The class's line span. |
| `end_line` | `int` |  | The class's line span. |
| `decorators` | `List[str]` | `[]` | The decorator names applied to the class (`TSDecorator.name` only). Order is not part of the cross-backend contract, exactly as on `TSCallableOverview`. |

#### Methods

##### `TSClassOverview.from_class`

```python
@classmethod
from_class(c: TSClass, *, path: str) -> TSClassOverview
```

Project a `TSClass` into a `TSClassOverview`.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `c` | [`TSClass`](#tsclass) | The class to project. |
| `path` | `str` | The declaring module's symbol-table key (repo-relative path). The v2 type does not carry it; the caller iterating `symbol_table` does. |

**Returns:**

- [`TSClassOverview`](#tsclassoverview): The projected overview.

### `TSCallableParameter`

```python
class TSCallableParameter(BaseModel)
```

A function / method parameter.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `Optional[str]` | `None` |  |
| `name` | `str` |  |  |
| `type` | `Optional[str]` | `None` |  |
| `default_value` | `Optional[str]` | `None` |  |
| `is_optional` | `bool` | `False` |  |
| `is_rest` | `bool` | `False` |  |
| `is_readonly` | `bool` | `False` |  |
| `accessibility` | `Optional[str]` | `None` |  |
| `decorators` | [`List[TSDecorator]`](#tsdecorator) | `[]` |  |
| `start_line` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |
| `start_column` | `int` | `-1` |  |
| `end_column` | `int` | `-1` |  |

### `TSCallsite`

```python
class TSCallsite(BaseModel)
```

1.x per-call record. Not on the v2 wire (its view is the `call` node in `body{}`);
kept so callers that construct or type-check against it keep importing.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `method_name` | `str` |  |  |
| `receiver_expr` | `Optional[str]` | `None` |  |
| `receiver_type` | `Optional[str]` | `None` |  |
| `argument_types` | `List[str]` | `[]` |  |
| `type_arguments` | `List[str]` | `[]` |  |
| `return_type` | `Optional[str]` | `None` |  |
| `callee_signature` | `Optional[str]` | `None` |  |
| `is_constructor_call` | `bool` | `False` |  |
| `is_optional_chain` | `bool` | `False` |  |
| `start_line` | `int` | `-1` |  |
| `start_column` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |
| `end_column` | `int` | `-1` |  |

### `TSCdgEdge`

```python
class TSCdgEdge(BaseModel)
```

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` |  |
| `dst` | `str` |  |

### `TSCfgEdge`

```python
class TSCfgEdge(BaseModel)
```

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `src` | `str` |  |
| `dst` | `str` |  |
| `kind` | `str` |  |

### `TSClass`

```python
class TSClass(BaseModel)
```

A class declaration.

#### Attributes

Inherited from `_Spanned` (`span`, `start_line`, `end_line`, `start_column`, `end_column`, `code`): A node with a mandatory span. `start_line`/`end_line`/`start_column`/`end_column` are the 1.x attribute paths, read off `span`; `code` is sliced from the owning module's `source`, which `TSModule` threads in after validation.

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |
| `code` | `Optional[str]` |  | The node's source text, `module.source` between the span's **UTF-8 byte** offsets. `None` until the node has been validated as part of a `TSModule`. |
| `id` | `str` |  |  |
| `name` | `str` |  |  |
| `signature` | `str` |  |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `is_exported` | `bool` | `False` |  |
| `is_ambient` | `bool` | `False` |  |
| `entrypoints` | [`Optional[List[TSEntrypoint]]`](#tsentrypoint) | `None` |  |
| `is_entrypoint` | `Optional[bool]` | `None` |  |
| `kind` | `Literal['class']` | `'class'` |  |
| `callables` | [`Dict[str, TSCallable]`](#tscallable) | `{}` |  |
| `fields` | [`Dict[str, TSField]`](#tsfield) | `{}` |  |
| `decorators` | [`List[TSDecorator]`](#tsdecorator) | `[]` |  |
| `base_classes` | `List[str]` | `[]` |  |
| `implements_types` | `List[str]` | `[]` |  |
| `is_abstract` | `bool` | `False` |  |
| `type_parameters` | [`List[TSTypeParameter]`](#tstypeparameter) | `[]` |  |
| `extends_ids` | `List[str]` | `[]` |  |
| `implements_ids` | `List[str]` | `[]` |  |
| `methods` | [`Dict[str, TSCallable]`](#tscallable) |  |  |
| `attributes` | [`Dict[str, TSField]`](#tsfield) |  |  |

### `TSClassAttribute`

```python
TSClassAttribute = TSField
```

Alias of [`TSField`](#tsfield).

### `TSComment`

```python
class TSComment(BaseModel)
```

A comment or JSDoc block.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `content` | `str` |  |  |
| `is_docstring` | `bool` | `False` |  |
| `start_line` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |
| `start_column` | `int` | `-1` |  |
| `end_column` | `int` | `-1` |  |

### `TSConfigKey`

```python
class TSConfigKey(BaseModel)
```

A configuration key flattened out of a config-bearing artifact.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `key` | `str` |  |  |
| `namespace` | `str` |  |  |
| `value` | `Optional[Union[str, int, float, bool]]` | `None` |  |
| `span` | [`Optional[TSSpan]`](#tsspan) | `None` |  |
| `references` | `List[str]` | `[]` |  |

### `TSConfigRead`

```python
class TSConfigRead(BaseModel)
```

A recognized config read that resolved to no declared key.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `site` | `str` |  |  |
| `callee` | `str` |  |  |
| `key` | `Optional[str]` | `None` |  |
| `reason` | `str` |  |  |
| `prov` | `List[str]` | `[]` |  |

### `TSConfigUse`

```python
class TSConfigUse(BaseModel)
```

A recognized config read (global ordinal `src`) joined to the `TSConfigKey` it names.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `src` | `str` |  |  |
| `dst` | `str` |  |  |
| `prov` | `List[str]` | `[]` |  |

### `TSDdgEdge`

```python
class TSDdgEdge(BaseModel)
```

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `src` | `str` |  |  |
| `dst` | `str` |  |  |
| `var` | `Optional[str]` | `None` |  |
| `prov` | `List[str]` | `[]` |  |

### `TSDecorator`

```python
class TSDecorator(BaseModel)
```

A decorator applied to a class / member / parameter (structured, with arguments).

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `str` |  |  |
| `qualified_name` | `Optional[str]` | `None` | Emitted by 1.2.0 (equal to `name` on every decorator measured) and by **no** 1.3.0 build, so it reads `None` at the pin. |
| `positional_arguments` | `List[str]` | `[]` |  |
| `keyword_arguments` | `Dict[str, str]` | `{}` |  |
| `start_line` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |
| `start_column` | `int` | `-1` |  |
| `end_column` | `int` | `-1` |  |

### `TSDependency`

```python
class TSDependency(BaseModel)
```

One third-party dependency, evidence-tagged via `prov`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `str` |  |  |
| `spec` | `str` | `''` |  |
| `kind` | `str` |  |  |
| `extras` | `List[str]` | `[]` |  |
| `declared_in` | `str` |  |  |
| `direct` | `bool` |  |  |
| `locked_version` | `Optional[str]` | `None` |  |
| `provides_imports` | `List[str]` | `[]` |  |
| `prov` | `List[str]` | `[]` |  |

### `TSEntrypoint`

```python
class TSEntrypoint(BaseModel)
```

One way a callable or class is invoked from outside the application.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `framework` | `str` |  |  |
| `confidence` | `str` | `'certain'` |  |
| `rule` | `str` | `''` |  |
| `ruleset` | `str` | `'shipped'` |  |
| `evidence` | `Optional[str]` | `None` |  |
| `route` | `Optional[str]` | `None` |  |
| `http_methods` | `List[str]` | `[]` |  |
| `via` | `Optional[str]` | `None` |  |

### `TSEntrypointReport`

```python
class TSEntrypointReport(BaseModel)
```

Coverage and failure record for the entrypoint pass.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `frameworks_detected` | `List[str]` | `[]` |  |
| `rulesets` | `List[str]` | `[]` |  |
| `unresolved` | `Dict[str, int]` | `{}` |  |
| `errors` | `List[str]` | `[]` |  |

### `TSEnum`

```python
class TSEnum(BaseModel)
```

An enum declaration; its members are `fields` carrying `value`.

#### Attributes

Inherited from `_Spanned` (`span`, `start_line`, `end_line`, `start_column`, `end_column`, `code`): A node with a mandatory span. `start_line`/`end_line`/`start_column`/`end_column` are the 1.x attribute paths, read off `span`; `code` is sliced from the owning module's `source`, which `TSModule` threads in after validation.

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |
| `code` | `Optional[str]` |  | The node's source text, `module.source` between the span's **UTF-8 byte** offsets. `None` until the node has been validated as part of a `TSModule`. |
| `id` | `str` |  |  |
| `name` | `str` |  |  |
| `signature` | `str` |  |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `is_exported` | `bool` | `False` |  |
| `is_ambient` | `bool` | `False` |  |
| `entrypoints` | [`Optional[List[TSEntrypoint]]`](#tsentrypoint) | `None` |  |
| `is_entrypoint` | `Optional[bool]` | `None` |  |
| `kind` | `Literal['enum']` | `'enum'` |  |
| `fields` | [`Dict[str, TSField]`](#tsfield) | `{}` |  |
| `is_const` | `bool` | `False` |  |
| `members` | [`List[TSField]`](#tsfield) |  |  |

### `TSEnumMember`

```python
TSEnumMember = TSField
```

Alias of [`TSField`](#tsfield).

### `TSExport`

```python
class TSExport(BaseModel)
```

A TypeScript export / re-export binding.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `module` | `Optional[str]` | `None` |  |
| `resolved_module` | `Optional[str]` | `None` | 1.4.0 additive, as on `TSImport`; set on re-exports only (a local `export { x }` names no other module). |
| `name` | `str` |  |  |
| `alias` | `Optional[str]` | `None` |  |
| `is_type_only` | `bool` | `False` |  |
| `export_kind` | `str` | `'named'` |  |
| `start_line` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |
| `start_column` | `int` | `-1` |  |
| `end_column` | `int` | `-1` |  |

### `TSExternalNode`

```python
class TSExternalNode(BaseModel)
```

A call target outside the project (library member / builtin), homed on the application
as `<appId>/@external/<module>/<name>`, keyed by that id.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `kind` | `str` | `'external'` |  |
| `module` | `str` |  |  |
| `name` | `str` |  |  |

### `TSExternalSymbol`

```python
TSExternalSymbol = TSExternalNode
```

Alias of [`TSExternalNode`](#tsexternalnode).

### `TSField`

```python
class TSField(BaseModel)
```

One open shape for a module variable, a class attribute / interface property, a
constructor parameter property and an enum member; each origin sets its own subset.
`span` is absent for constructor parameter properties, in which case the 1.x line/column
properties return `-1`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `kind` | `Literal['field']` | `'field'` |  |
| `span` | [`Optional[TSSpan]`](#tsspan) | `None` |  |
| `name` | `str` |  |  |
| `type` | `Optional[str]` | `None` |  |
| `initializer` | `Optional[str]` | `None` |  |
| `scope` | `Optional[str]` | `None` |  |
| `declaration_kind` | `Optional[str]` | `None` |  |
| `is_exported` | `bool` | `False` |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `decorators` | [`List[TSDecorator]`](#tsdecorator) | `[]` |  |
| `accessibility` | `Optional[str]` | `None` |  |
| `is_static` | `bool` | `False` |  |
| `is_readonly` | `bool` | `False` |  |
| `is_optional` | `bool` | `False` |  |
| `is_abstract` | `bool` | `False` |  |
| `value` | `Optional[str]` | `None` |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |

### `TSImport`

```python
class TSImport(BaseModel)
```

A TypeScript import binding (one entry per imported name).

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `module` | `str` |  |  |
| `resolved_module` | `Optional[str]` | `None` | 1.4.0 additive: the project-relative module key `module` resolves to under the importer's own program, from the compiler's own resolver. `None` when the specifier is external, a builtin, or unresolvable, and it is what the Neo4j projection homes `TS_IMPORTS` on. |
| `name` | `str` |  |  |
| `alias` | `Optional[str]` | `None` |  |
| `is_type_only` | `bool` | `False` |  |
| `import_kind` | `str` | `'named'` |  |
| `start_line` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |
| `start_column` | `int` | `-1` |  |
| `end_column` | `int` | `-1` |  |

### `TSImportBinding`

```python
class TSImportBinding(BaseModel)
```

A non-relative import no declared dependency accounts for.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `module` | `str` |  |  |
| `bound_to` | `Optional[str]` | `None` |  |
| `prov` | `List[str]` | `[]` |  |

### `TSInterface`

```python
class TSInterface(BaseModel)
```

An interface declaration.

#### Attributes

Inherited from `_Spanned` (`span`, `start_line`, `end_line`, `start_column`, `end_column`, `code`): A node with a mandatory span. `start_line`/`end_line`/`start_column`/`end_column` are the 1.x attribute paths, read off `span`; `code` is sliced from the owning module's `source`, which `TSModule` threads in after validation.

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |
| `code` | `Optional[str]` |  | The node's source text, `module.source` between the span's **UTF-8 byte** offsets. `None` until the node has been validated as part of a `TSModule`. |
| `id` | `str` |  |  |
| `name` | `str` |  |  |
| `signature` | `str` |  |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `is_exported` | `bool` | `False` |  |
| `is_ambient` | `bool` | `False` |  |
| `entrypoints` | [`Optional[List[TSEntrypoint]]`](#tsentrypoint) | `None` |  |
| `is_entrypoint` | `Optional[bool]` | `None` |  |
| `kind` | `Literal['interface']` | `'interface'` |  |
| `callables` | [`Dict[str, TSCallable]`](#tscallable) | `{}` |  |
| `fields` | [`Dict[str, TSField]`](#tsfield) | `{}` |  |
| `base_classes` | `List[str]` | `[]` |  |
| `type_parameters` | [`List[TSTypeParameter]`](#tstypeparameter) | `[]` |  |
| `call_signatures` | `List[str]` | `[]` |  |
| `index_signatures` | `List[str]` | `[]` |  |
| `extends_ids` | `List[str]` | `[]` |  |
| `methods` | [`Dict[str, TSCallable]`](#tscallable) |  |  |
| `properties` | [`Dict[str, TSField]`](#tsfield) |  |  |

### `TSModule`

```python
class TSModule(BaseModel)
```

A compilation unit (one `.ts`/`.tsx`/`.js` file). The symbol-table key is its
repo-relative path; the wire carries no `file_path`/`module_name`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `kind` | `Literal['module']` | `'module'` |  |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `source` | `str` |  |  |
| `imports` | [`List[TSImport]`](#tsimport) | `[]` |  |
| `exports` | [`List[TSExport]`](#tsexport) | `[]` |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `types` | [`Dict[str, TSType]`](#tstype) | `{}` |  |
| `functions` | [`Dict[str, TSCallable]`](#tscallable) | `{}` |  |
| `fields` | [`Dict[str, TSField]`](#tsfield) | `{}` |  |
| `is_tsx` | `bool` | `False` |  |
| `is_declaration_file` | `bool` | `False` |  |
| `content_hash` | `Optional[str]` | `None` |  |
| `classes` | [`Dict[str, TSClass]`](#tsclass) |  |  |
| `interfaces` | [`Dict[str, TSInterface]`](#tsinterface) |  |  |
| `enums` | [`Dict[str, TSEnum]`](#tsenum) |  |  |
| `type_aliases` | [`Dict[str, TSTypeAlias]`](#tstypealias) |  |  |
| `namespaces` | [`Dict[str, TSNamespace]`](#tsnamespace) |  |  |
| `variables` | [`List[TSField]`](#tsfield) |  |  |

### `TSNamespace`

```python
class TSNamespace(BaseModel)
```

A namespace / module block, a nested scope with the same buckets as a module.

#### Attributes

Inherited from `_Spanned` (`span`, `start_line`, `end_line`, `start_column`, `end_column`, `code`): A node with a mandatory span. `start_line`/`end_line`/`start_column`/`end_column` are the 1.x attribute paths, read off `span`; `code` is sliced from the owning module's `source`, which `TSModule` threads in after validation.

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |
| `code` | `Optional[str]` |  | The node's source text, `module.source` between the span's **UTF-8 byte** offsets. `None` until the node has been validated as part of a `TSModule`. |
| `id` | `str` |  |  |
| `name` | `str` |  |  |
| `signature` | `str` |  |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `is_exported` | `bool` | `False` |  |
| `is_ambient` | `bool` | `False` |  |
| `entrypoints` | [`Optional[List[TSEntrypoint]]`](#tsentrypoint) | `None` |  |
| `is_entrypoint` | `Optional[bool]` | `None` |  |
| `kind` | `Literal['namespace']` | `'namespace'` |  |
| `types` | [`Dict[str, TSType]`](#tstype) | `{}` |  |
| `functions` | [`Dict[str, TSCallable]`](#tscallable) | `{}` |  |
| `fields` | [`Dict[str, TSField]`](#tsfield) | `{}` |  |
| `classes` | [`Dict[str, TSClass]`](#tsclass) |  |  |
| `interfaces` | [`Dict[str, TSInterface]`](#tsinterface) |  |  |
| `enums` | [`Dict[str, TSEnum]`](#tsenum) |  |  |
| `type_aliases` | [`Dict[str, TSTypeAlias]`](#tstypealias) |  |  |
| `namespaces` | [`Dict[str, TSNamespace]`](#tsnamespace) |  |  |
| `variables` | [`List[TSField]`](#tsfield) |  |  |

### `TSOverloadSignature`

```python
class TSOverloadSignature(BaseModel)
```

An overload signature attached to the implementation callable.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `parameters` | [`List[TSCallableParameter]`](#tscallableparameter) | `[]` |  |
| `return_type` | `Optional[str]` | `None` |  |
| `type_parameters` | [`List[TSTypeParameter]`](#tstypeparameter) | `[]` |  |
| `start_line` | `int` | `-1` |  |
| `end_line` | `int` | `-1` |  |

### `TSParamEdge`

```python
class TSParamEdge(BaseModel)
```

An L4 `param_in`/`param_out` edge with **global** ordinal endpoints.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `src` | `str` |  |  |
| `dst` | `str` |  |  |
| `var` | `Optional[str]` | `None` |  |

### `TSSpan`

```python
class TSSpan(BaseModel)
```

`start`/`end` are `[line, column]` (1-based); `bytes` are `[from, to]` offsets into
the owning module's `source`.

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `start` | `Tuple[int, int]` |  |
| `end` | `Tuple[int, int]` |  |
| `bytes` | `Tuple[int, int]` |  |

### `TSSummaryEdge`

```python
class TSSummaryEdge(BaseModel)
```

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `src` | `str` |  |  |
| `dst` | `str` |  |  |
| `var` | `Optional[str]` | `None` |  |

### `TSSymbol`

```python
class TSSymbol(BaseModel)
```

1.x accessed-symbol record. Not on the v2 wire; kept importable.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `str` |  |  |
| `scope` | `str` |  |  |
| `kind` | `str` |  |  |
| `type` | `Optional[str]` | `None` |  |
| `qualified_name` | `Optional[str]` | `None` |  |
| `is_builtin` | `bool` | `False` |  |
| `lineno` | `int` | `-1` |  |
| `col_offset` | `int` | `-1` |  |

### `TSSynthesizedCallable`

```python
TSSynthesizedCallable = TSSynthesizedNode
```

Alias of [`TSSynthesizedNode`](#tssynthesizednode).

### `TSSynthesizedNode`

```python
class TSSynthesizedNode(BaseModel)
```

An entry of the anonymous-callable compatibility index: the map key is the **older** id
(`<enclosing>@<line>:<col>`) and `id` the tree id that replaced it; a residual fallback
node (no tree home) has key == `id` and carries `name`/`path`/`span`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `id` | `str` |  |  |
| `kind` | `str` | `'callable'` |  |
| `name` | `Optional[str]` | `None` |  |
| `path` | `Optional[str]` | `None` |  |
| `span` | [`Optional[TSSpan]`](#tsspan) | `None` |  |

### `TSType`

```python
TSType = Annotated[
    Union[TSClass, TSInterface, TSEnum, TSTypeAlias, TSNamespace],
    Field(discriminator='kind'),
]
```

One of [`TSClass`](#tsclass), [`TSInterface`](#tsinterface), [`TSEnum`](#tsenum), [`TSTypeAlias`](#tstypealias) or [`TSNamespace`](#tsnamespace).

### `TSTypeAlias`

```python
class TSTypeAlias(BaseModel)
```

A type-alias declaration.

#### Attributes

Inherited from `_Spanned` (`span`, `start_line`, `end_line`, `start_column`, `end_column`, `code`): A node with a mandatory span. `start_line`/`end_line`/`start_column`/`end_column` are the 1.x attribute paths, read off `span`; `code` is sliced from the owning module's `source`, which `TSModule` threads in after validation.

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `span` | [`TSSpan`](#tsspan) |  |  |
| `start_line` | `int` |  |  |
| `end_line` | `int` |  |  |
| `start_column` | `int` |  |  |
| `end_column` | `int` |  |  |
| `code` | `Optional[str]` |  | The node's source text, `module.source` between the span's **UTF-8 byte** offsets. `None` until the node has been validated as part of a `TSModule`. |
| `id` | `str` |  |  |
| `name` | `str` |  |  |
| `signature` | `str` |  |  |
| `comments` | [`List[TSComment]`](#tscomment) | `[]` |  |
| `is_exported` | `bool` | `False` |  |
| `is_ambient` | `bool` | `False` |  |
| `entrypoints` | [`Optional[List[TSEntrypoint]]`](#tsentrypoint) | `None` |  |
| `is_entrypoint` | `Optional[bool]` | `None` |  |
| `kind` | `Literal['type_alias']` | `'type_alias'` |  |
| `aliased_type` | `str` | `''` |  |
| `type_parameters` | [`List[TSTypeParameter]`](#tstypeparameter) | `[]` |  |

### `TSTypeParameter`

```python
class TSTypeParameter(BaseModel)
```

A generic type parameter, e.g. `T extends Base = Default`.

#### Attributes

| Name | Type | Default | Description |
| ---- | ---- | ------- | ----------- |
| `name` | `str` |  |  |
| `constraint` | `Optional[str]` | `None` |  |
| `default` | `Optional[str]` | `None` |  |

### `TSVariableDeclaration`

```python
TSVariableDeclaration = TSField
```

Alias of [`TSField`](#tsfield).

<!-- CLDK:API:END -->
