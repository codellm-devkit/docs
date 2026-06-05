---
title: Python API Reference
description: "The CLDK Python SDK: the CLDK factory, the per-language analysis facades, and the typed data models they return."
---

[![Source on GitHub](https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)](https://github.com/codellm-devkit/python-sdk)

Every CLDK program follows the same shape: construct a `CLDK` object for a
language, ask it for an `analysis` facade over your project, then call typed
methods that return data models.

```mermaid
flowchart LR
    C["CLDK(language)"] --> A["analysis(project_path)"]
    A --> J[JavaAnalysis]
    A --> P[PythonAnalysis]
    J & P --> M[Typed models]
```

It's the same `analysis` facade and the same methods across languages, only the
`language` argument changes. New to the library? Start with [What is
CLDK?](/what-is-cldk/) for the mental model, or jump to the
[Quickstart](/quickstart/).

## Reference pages

- **[Core (CLDK)](/reference/python-api/core/)**, the factory: `CLDK(language)` and the `analysis()` entry point.
- **[Python analysis](/reference/python-api/python/)**: symbol table and call graph via Jedi + optional CodeQL.
- **[Java analysis](/reference/python-api/java/)**, the deepest analyzer: symbol table, call graph, subclasses/interfaces, CRUD.

More languages (Go, TypeScript, Rust, and C) are on the way.

Looking for runnable patterns instead of symbol lists? See [Common
tasks](/guides/common-tasks/) and the [cocoa](/cocoa/).
