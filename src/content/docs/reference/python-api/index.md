---
title: Python API Reference
description: "The CLDK Python SDK: the CLDK factory, per-language analysis APIs, and typed data models."
---

[![Source on GitHub](https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)](https://github.com/codellm-devkit/python-sdk)

Every CLDK program follows the same shape: construct a `CLDK` object for a
language, ask it for an `analysis` object over your project, then call typed
methods that return data models.

```mermaid
flowchart LR
    C["CLDK(language)"] --> A["analysis(project_path)"]
    A --> J[JavaAnalysis]
    A --> P[PythonAnalysis]
    J & P --> M[Typed models]
```

The `analysis` API and its methods are the same across languages; only the
`language` argument changes. For an introduction to the library, see [What is
CLDK?](/what-is-cldk/), or the [Quickstart](/quickstart/).

## Reference pages

- **[Core (CLDK)](/reference/python-api/core/)**, the factory: `CLDK(language)` and the `analysis()` entry point.
- **[Python analysis](/reference/python-api/python/)**: symbol table and call graph via Jedi + optional CodeQL.
- **[Java analysis](/reference/python-api/java/)**, the most complete analyzer: symbol table, call graph, subclasses/interfaces, CRUD.

More languages (Go, TypeScript, Rust, and C) are on the way.

For runnable patterns rather than symbol lists, see [Common
tasks](/guides/common-tasks/) and the [cocoa](/cocoa/).
