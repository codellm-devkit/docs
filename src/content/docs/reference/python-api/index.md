---
title: Python API Reference
description: "The CLDK Python SDK: the CLDK factory, per-language analysis APIs, and typed data models."
---

[![Source on GitHub](https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)](https://github.com/codellm-devkit/python-sdk)

Every CLDK program follows the same shape. Call the per-language factory, for
example `CLDK.java(project_path=...)`, to get an analysis object over your
project. Then call typed methods that return data models.

```mermaid
flowchart LR
    C["CLDK"] --> JF["CLDK.java(project_path)"]
    C --> PF["CLDK.python(project_path)"]
    JF --> J[JavaAnalysis]
    PF --> P[PythonAnalysis]
    J & P --> M[Typed models]
```

The analysis API and its methods are the same across languages. Only the factory
that you call changes. For an introduction to the library, see [What is
CLDK?](/what-is-cldk/), or the [Quickstart](/quickstart/).

## Reference pages

- **[Core (CLDK)](/reference/python-api/core/)**, the factory: the per-language `CLDK.java()`, `CLDK.python()`, and `CLDK.typescript()` entry points.
- **[Python analysis](/reference/python-api/python/)**: symbol table and call graph, from Jedi and the level-2 defuse linker.
- **[Java analysis](/reference/python-api/java/)**, the most complete analysis: symbol table, call graph, subclasses, and interfaces.
- **[TypeScript analysis](/reference/python-api/typescript/)** <span title="beta">(beta)</span>: symbol table, call graph, interfaces, enums, decorators, and framework entrypoints.

CLDK 2.0 adds the dataflow and taint methods to all three. See [Dataflow graphs](/guides/dataflow/). Go and Rust are planned.

For runnable patterns rather than symbol lists, see [Common
tasks](/guides/common-tasks/) and the [cocoa](/cocoa/).
