---
title: "Tree-sitter utilities"
description: "Tree-sitter parsers for Java and Python source code, and the Java source sanitizer."
---

The tree-sitter helpers parse source code without an analysis. They read one string of
code at a time. They need no project directory, no build and no analyzer.

The outputs on this page come from cldk 2.0.0 on Commons CLI 1.7.0 and Flask 3.1.3.
To run the samples, clone the two projects. Then run the samples from the directory
that holds the clones.

```bash
git clone --depth 1 --branch rel/commons-cli-1.7.0 https://github.com/apache/commons-cli.git
git clone --depth 1 --branch 3.1.3 https://github.com/pallets/flask.git
```

## When to use these helpers

Use a tree-sitter helper in these cases:

- You have one file or a part of a file, and no project directory.
- The project does not build, or you do not want to run the analyzer.
- You need only syntax facts, for example the class name, the imports or the syntax tree.
- Your code used the `source_code` mode of cldk 1.x.

The helpers read syntax only. They do not resolve types, and they do not follow calls
into other files. For types, the call graph or dataflow, use an analysis from
`CLDK.java`, `CLDK.python` or `CLDK.typescript`. See
[Build an analysis](/reference/python-api/core/#build-an-analysis).

### Move from the 1.x `source_code` mode

cldk 2.0 removed the `source_code` mode.
`CLDK(language="java").analysis(source_code=...)` now raises
`CldkInitializationException` with the message
`source_code mode was removed in 2.0; pass project_path`. Do one of these instead:

- For syntax facts about one Java string, use `TreesitterJava`.
- To remove comments, call `TreesitterJava().remove_all_comments(code)`. In 2.0,
  `JavaAnalysis.remove_all_comments()` raises `NotImplementedError`. The helper keeps
  the text from the `package` line to the end. Use it only on a whole file that has a
  `package` line. If the code has no `package` line, the helper keeps only the text
  after the last newline. For a file that ends with a newline, it returns an empty
  string.
- For the symbol table of one Java file, put the file in a directory that matches its
  package. For example, put the file of `package demo;` in `demo/Greeter.java`. Then
  pass the directory that holds `demo/` as `project_path`. This needs
  `pip install "cldk[java]"`. If the directory does not match the package, the analysis
  finds no classes and shows no error.

:::caution[This helper can change code]
`remove_all_comments()` can also change code that is not a comment. It merges identical
lines that follow each other, and it deletes each line that starts with `*` or `/` after
its indentation. It also removes the text of each `//` comment everywhere in the code.
For example, if the file has an empty `//` comment, `"https://"` in a string becomes
`"https:"`. Compare the output with the input.
:::

## Get a helper

| Helper | Language | Import | Other ways to get it |
| --- | --- | --- | --- |
| [`TreesitterJava`](#treesitterjava) | Java | `from cldk.analysis.commons.treesitter import TreesitterJava` | `CLDK(language="java").treesitter_parser()`, or the `treesitter_java` attribute of a `JavaAnalysis` |
| [`TreesitterPython`](#treesitterpython) | Python | `from cldk.analysis.commons.treesitter import TreesitterPython` | The `treesitter_python` attribute of a `PythonAnalysis` |
| [`TreesitterSanitizer`](#treesittersanitizer) | Java | `from cldk.utils.sanitization.java import TreesitterSanitizer` | `CLDK(language="java").tree_sitter_utils(source_code)` |

`pip install cldk` installs the helpers. They do not need the `java` extra or a JDK.

`treesitter_parser()` and `tree_sitter_utils()` are instance methods. Call them on
`CLDK(language="java")`, not on the `CLDK` class. For `"python"` and `"typescript"`,
both methods raise `NotImplementedError`. cldk 2.0.0 has no tree-sitter helper for
TypeScript.

`JavaAnalysis` and `PythonAnalysis` also have `is_parsable()` and `get_raw_ast()`. These
methods call the helper for their language.

## Parse a Java file

```python
from pathlib import Path

from cldk.analysis.commons.treesitter import TreesitterJava

code = Path("commons-cli/src/main/java/org/apache/commons/cli/Option.java").read_text()

parser = TreesitterJava()
print(parser.is_parsable(code))                  # True
print(parser.get_pacakge_name(code))             # org.apache.commons.cli
print(parser.get_class_name(code))               # Option
print(sorted(parser.get_all_interfaces(code)))   # ['Cloneable', 'Serializable']
print(len(code), len(parser.remove_all_comments(code)))   # 31487 12253
```

In cldk 2.0.0, the name of the method that reads the package name is
`get_pacakge_name`. There is no `get_package_name`.

For other syntax, run a tree-sitter query. The result holds one capture for each match.
Use one capture name in each query. If the query has two or more capture names, the
result keeps the captures of only one name, and it shows no error. It is not always the
last name in the query. This block continues the previous one:

```python
query = "(method_declaration name: (identifier) @name)"
captures = parser.frame_query_and_capture_output(query, code)
names = {capture.node.text.decode() for capture in captures}
print(len(captures), len(names))   # 67 57
print(sorted(names)[:3])           # ['acceptsArg', 'add', 'addValue']
```

The 67 captures are 48 methods of `Option` and 19 methods of the nested `Builder`
class. A name with more than one declaration, for example an overloaded method, has
one capture for each declaration.

## Parse a Python file

```python
from pathlib import Path

from cldk.analysis.commons.treesitter import TreesitterPython

code = Path("flask/src/flask/app.py").read_text()

parser = TreesitterPython()
print(parser.is_parsable(code))   # True

tree = parser.get_raw_ast(code)
print(tree.root_node.type)        # module
classes = [
    node.child_by_field_name("name").text.decode()
    for node in tree.root_node.children
    if node.type == "class_definition"
]
print(classes)                    # ['Flask']
```

`TreesitterPython` has only these two methods. `get_raw_ast()` returns a `Tree` from the
[py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter) package. Use its API to
walk the tree.

## Keep one Java method and its callees

`TreesitterSanitizer` cuts a Java class down to one method and the methods that it calls
in the same class. Use it to make a smaller context, for example for a prompt.

```python
from pathlib import Path

from cldk.utils.sanitization.java import TreesitterSanitizer

code = Path("commons-cli/src/main/java/org/apache/commons/cli/Util.java").read_text()

focused = TreesitterSanitizer(code).keep_only_focal_method_and_its_callees(
    "stripLeadingAndTrailingQuotes"
)
print("isEmpty" in focused)               # True
print("stripLeadingHyphens" in focused)   # False
print("EMPTY_STRING_ARRAY" in focused)    # True

cleaned = TreesitterSanitizer(code).sanitize_focal_class(
    "static String stripLeadingAndTrailingQuotes(final String str) {}"
)
print("EMPTY_STRING_ARRAY" in cleaned)    # False
```

`stripLeadingAndTrailingQuotes` calls `isEmpty`, so the sanitizer keeps `isEmpty`. It
removes `stripLeadingHyphens` and the comments. `sanitize_focal_class()` also removes the
unused field `EMPTY_STRING_ARRAY`. It removes unused imports and inner classes too.

`keep_only_focal_method_and_its_callees()` takes the method name.
`sanitize_focal_class()` takes a method declaration, as in the sample. If you pass only
the name, it raises `IndexError`. The `sanitize_focal_class` reference below says that
it also takes a name. In cldk 2.0.0, this is not correct.

The sanitizer finds callees by method name in the same class. It does not tell
overloaded methods apart. It keeps every method with the name of a callee. But it
follows the calls of only one of them, and it does not tell you which one. If the class
has overloaded methods, make sure that the output keeps the callees that you need.

Both methods also merge identical lines that follow each other, and they delete each
line that starts with `*` or `/` after its indentation. Compare the output with the
input.

## `is_parsable` misses some syntax errors

`is_parsable()` looks for `ERROR` nodes in the syntax tree. Tree-sitter repairs some
syntax errors with a `MISSING` node instead, for example a missing semicolon. For such
code, `is_parsable()` returns `True`. For a strict check, read `has_error` on the root
node of `get_raw_ast()`.

```python
from cldk.analysis.commons.treesitter import TreesitterJava, TreesitterPython

java = TreesitterJava()
code = "class A { int x = 1 }"
print(java.is_parsable(code))                       # True
print(java.get_raw_ast(code).root_node.has_error)   # True

python = TreesitterPython()
code = "def f(:"
print(python.is_parsable(code))                       # True
print(python.get_raw_ast(code).root_node.has_error)   # True
```

`JavaAnalysis.is_parsable()` and `PythonAnalysis.is_parsable()` call these helpers, so
they have the same limit. The `is_parsable` reference below says that it returns `True`
only for code with no syntax errors. In cldk 2.0.0, this is not correct.

## API reference

The reference below comes from the docstrings of cldk 2.0.0.

<!-- CLDK:API:START -->

<!-- AUTO-GENERATED by scripts/gen_api_docs.py, do not edit by hand. -->

[![Source on GitHub](https://img.shields.io/badge/source-codellm--devkit%2Fpython--sdk-181717?logo=github&logoColor=white)](https://github.com/codellm-devkit/python-sdk) [![cldk 2.0.0](https://img.shields.io/badge/cldk-2.0.0-3776AB?logo=pypi&logoColor=white)](https://pypi.org/project/cldk/2.0.0/)

_API reference generated from cldk 2.0.0._

## Java parser

```python
from cldk.analysis.commons.treesitter import TreesitterJava
```

### `TreesitterJava`

```python
TreesitterJava()
```

| Method | Summary |
| ------ | ------- |
| [`method_is_not_in_class`](#treesitterjavamethod_is_not_in_class) | Check if a method is NOT declared in a class body. |
| [`is_parsable`](#treesitterjavais_parsable) | Check if the given code is syntactically valid Java. |
| [`get_raw_ast`](#treesitterjavaget_raw_ast) | Parse code and return the Tree-sitter AST. |
| [`get_all_imports`](#treesitterjavaget_all_imports) | Return all import statements in the source. |
| [`get_pacakge_name`](#treesitterjavaget_pacakge_name) | Return the package name from the source code. |
| [`get_class_name`](#treesitterjavaget_class_name) | Return the class name from the source code. |
| [`get_superclass`](#treesitterjavaget_superclass) | Return the superclass name if present. |
| [`get_all_interfaces`](#treesitterjavaget_all_interfaces) | Return interfaces implemented by a class. |
| [`frame_query_and_capture_output`](#treesitterjavaframe_query_and_capture_output) | Execute a Tree-sitter query and return captured nodes. |
| [`get_method_name_from_declaration`](#treesitterjavaget_method_name_from_declaration) | Get the method name from the method signature. |
| [`get_method_name_from_invocation`](#treesitterjavaget_method_name_from_invocation) | Extract the method name from a method invocation string. |
| [`get_identifier_from_arbitrary_statement`](#treesitterjavaget_identifier_from_arbitrary_statement) | Get the identifier from an arbitrary statement. |
| [`safe_ascend`](#treesitterjavasafe_ascend) | Ascend parent pointers safely in the AST. |
| [`get_call_targets`](#treesitterjavaget_call_targets) | Return call targets referenced in a method body. |
| [`get_calling_lines`](#treesitterjavaget_calling_lines) | Return line numbers where the target method is called in the source method. |
| [`get_test_methods`](#treesitterjavaget_test_methods) | Return methods annotated with @Test in a class. |
| [`get_methods_with_annotations`](#treesitterjavaget_methods_with_annotations) | Return methods grouped by annotation. |
| [`get_all_type_invocations`](#treesitterjavaget_all_type_invocations) | Return all type identifiers referenced in the source. |
| [`get_method_return_type`](#treesitterjavaget_method_return_type) | Return the return type of a method. |
| [`get_lexical_tokens`](#treesitterjavaget_lexical_tokens) | Return lexical tokens from the code. |
| [`remove_all_comments`](#treesitterjavaremove_all_comments) | Return source code with all comments removed. |
| [`make_pruned_code_prettier`](#treesitterjavamake_pruned_code_prettier) | Prettify the pruned code after comment removal. |

Tree-sitter helper class for Java source code parsing and analysis.

This class provides comprehensive utilities for parsing Java source code
using Tree-sitter. It offers methods for:
- Syntax validation
- AST generation and traversal
- Code element extraction (classes, methods, imports)
- Pattern matching via S-expression queries
- Code transformation (comment removal)

The class is stateless and uses module-level parser and language objects,
making it thread-safe for concurrent use.

> **See Also**
>
> - `JavaAnalysis`: High-level analysis facade.
> - `TreesitterPython`: Equivalent for Python.

#### Methods

##### `TreesitterJava.method_is_not_in_class`

```python
method_is_not_in_class(method_name: str, class_body: str) -> bool
```

Check if a method is NOT declared in a class body.

Searches for method declarations in the given class body and checks
if the specified method name is absent.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `method_name` | `str` | The method name to check for (without parentheses or parameters). |
| `class_body` | `str` | The Java class source code to search within. |

**Returns:**

- `bool`: `True` if the method is NOT found in the class body,
  `False` if the method IS found.

##### `TreesitterJava.is_parsable`

```python
is_parsable(code: str) -> bool
```

Check if the given code is syntactically valid Java.

Parses the code using Tree-sitter and recursively checks for ERROR
nodes in the resulting AST. Returns `True` only if the entire
code parses without syntax errors.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `code` | `str` | A string containing Java source code to validate. Can be a complete compilation unit, a class, a method, or any syntactically valid Java fragment. |

**Returns:**

- `bool`: `True` if the code parses without syntax errors, `False`
  otherwise. Also returns `False` if parsing triggers a
  RecursionError (for extremely nested code).

:::note
This checks syntactic validity only, not semantic correctness.
Code with undefined types or methods will still be "parsable".
:::

> **See Also**
>
> - `get_raw_ast`: To obtain the AST for further analysis.

##### `TreesitterJava.get_raw_ast`

```python
get_raw_ast(code: str) -> Tree
```

Parse code and return the Tree-sitter AST.

Parses the provided Java source code using Tree-sitter and returns
the resulting abstract syntax tree. The AST can be traversed to
extract syntactic information about the code structure.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `code` | `str` | A string containing Java source code to parse. |

**Returns:**

- `Tree`: A Tree-sitter `Tree` object representing the parsed AST. The
  tree's `root_node` provides access to the entire syntax tree:
  - `root_node.type`: Typically `"program"` for Java
  - `root_node.children`: Top-level declarations
  - `root_node.text`: Original source bytes

:::note
If the source contains syntax errors, Tree-sitter returns a tree
with ERROR nodes at parse error locations. Use `is_parsable`
to check for valid syntax first.
:::

> **See Also**
>
> - `is_parsable`: To validate syntax before parsing.

##### `TreesitterJava.get_all_imports`

```python
get_all_imports(source_code: str) -> Set[str]
```

Return all import statements in the source.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `Set[str]`: set[str]: Import identifiers.

##### `TreesitterJava.get_pacakge_name`

```python
get_pacakge_name(source_code: str) -> str
```

Return the package name from the source code.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `str`: Package declaration value, or None if absent.

##### `TreesitterJava.get_class_name`

```python
get_class_name(source_code: str) -> str
```

Return the class name from the source code.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `str`: Class identifier.

##### `TreesitterJava.get_superclass`

```python
get_superclass(source_code: str) -> str
```

Return the superclass name if present.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `str`: Superclass identifier or empty string.

##### `TreesitterJava.get_all_interfaces`

```python
get_all_interfaces(source_code: str) -> Set[str]
```

Return interfaces implemented by a class.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `Set[str]`: set[str]: Interface identifiers.

##### `TreesitterJava.frame_query_and_capture_output`

```python
frame_query_and_capture_output(query: str, code_to_process: str) -> Captures
```

Execute a Tree-sitter query and return captured nodes.

Parses the provided source code and runs the given S-expression
query against the AST, returning all captured nodes.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `query` | `str` | A Tree-sitter S-expression query string defining the pattern to match and captures to extract. Captures are denoted with `@name` syntax. |
| `code_to_process` | `str` | Java source code to parse and query. |

**Returns:**

- `Captures`: A `Captures`
  object containing all nodes matched by the query, with their
  capture names and node references.

:::note
The query syntax follows Tree-sitter's S-expression format.
See Tree-sitter documentation for query syntax details.
:::

> **See Also**
>
> - `Captures`: The return type for captured nodes.

##### `TreesitterJava.get_method_name_from_declaration`

```python
get_method_name_from_declaration(method_name_string: str) -> str
```

Get the method name from the method signature.

##### `TreesitterJava.get_method_name_from_invocation`

```python
get_method_name_from_invocation(method_invocation: str) -> str
```

Extract the method name from a method invocation string.

##### `TreesitterJava.get_identifier_from_arbitrary_statement`

```python
get_identifier_from_arbitrary_statement(statement: str) -> str
```

Get the identifier from an arbitrary statement.

##### `TreesitterJava.safe_ascend`

```python
safe_ascend(node: Node, ascend_count: int) -> Node
```

Ascend parent pointers safely in the AST.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `node` | `Node` | Starting node. |
| `ascend_count` | `int` | Levels to ascend. |

**Returns:**

- `Node`: Ancestor node after ascending.

**Raises:**

- `ValueError`: If node is None or has no parent.

##### `TreesitterJava.get_call_targets`

```python
get_call_targets(method_body: str, declared_methods: dict) -> Set[str]
```

Return call targets referenced in a method body.

Uses simple name resolution over the AST.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `method_body` | `str` | Method source. |
| `declared_methods` | `dict` | Declared methods in the class. |

**Returns:**

- `Set[str]`: set[str]: Call target method names.

##### `TreesitterJava.get_calling_lines`

```python
get_calling_lines(source_method_code: str, target_method_name: str) -> List[int]
```

Return line numbers where the target method is called in the source method.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_method_code` | `str` | Source method code. |
| `target_method_name` | `str` | Target method signature or name. |

**Returns:**

- `List[int]`: list[int]: Line numbers within the source method.

##### `TreesitterJava.get_test_methods`

```python
get_test_methods(source_class_code: str) -> Dict[str, str]
```

Return methods annotated with @Test in a class.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_class_code` | `str` | Java class source. |

**Returns:**

- `Dict[str, str]`: dict[str, str]: Map of method name to body.

##### `TreesitterJava.get_methods_with_annotations`

```python
get_methods_with_annotations(
    source_class_code: str,
    annotations: List[str],
) -> Dict[str, List[Dict]]
```

Return methods grouped by annotation.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_class_code` | `str` | Java class source. |
| `annotations` | `list[str]` | Annotation names to include. |

**Returns:**

- `Dict[str, List[Dict]]`: dict[str, list[dict]]: Mapping of annotation to list of method info dicts.

##### `TreesitterJava.get_all_type_invocations`

```python
get_all_type_invocations(source_code: str) -> Set[str]
```

Return all type identifiers referenced in the source.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `Set[str]`: set[str]: Type identifiers.

##### `TreesitterJava.get_method_return_type`

```python
get_method_return_type(source_code: str) -> str
```

Return the return type of a method.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java method source. |

**Returns:**

- `str`: Return type identifier.

##### `TreesitterJava.get_lexical_tokens`

```python
get_lexical_tokens(code: str, filter_by_node_type: List[str] | None = None) -> List[str]
```

Return lexical tokens from the code.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `code` | `str` | Java source code. |
| `filter_by_node_type` | `list[str] \| None` | Optional node type filter. |

**Returns:**

- `List[str]`: list[str]: Collected token strings.

##### `TreesitterJava.remove_all_comments`

```python
remove_all_comments(source_code: str) -> str
```

Return source code with all comments removed.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | Java source. |

**Returns:**

- `str`: Source with comments removed.

##### `TreesitterJava.make_pruned_code_prettier`

```python
make_pruned_code_prettier(pruned_code: str) -> str
```

Prettify the pruned code after comment removal.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `pruned_code` | `str` | Source after pruning. |

**Returns:**

- `str`: Prettified source code.

## Python parser

```python
from cldk.analysis.commons.treesitter import TreesitterPython
```

### `TreesitterPython`

```python
TreesitterPython()
```

Tree-sitter helper class for Python source code parsing.

This class provides utility methods for parsing Python source code using
Tree-sitter. It offers syntax validation and raw AST generation for
further analysis.

The class is stateless and thread-safe - it uses module-level parser
and language objects.

#### Methods

##### `TreesitterPython.is_parsable`

```python
is_parsable(code: str) -> bool
```

Check if the given code is syntactically valid Python.

Parses the code using Tree-sitter and recursively checks for ERROR
nodes in the resulting AST. Returns `True` only if the entire
code parses without syntax errors.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `code` | `str` | A string containing Python source code to validate. Can be a complete module, a function, a class, or any valid Python code fragment. |

**Returns:**

- `bool`: `True` if the code parses without syntax errors, `False`
  otherwise. Also returns `False` if parsing triggers a
  RecursionError (for extremely nested code).

:::note
This only checks syntactic validity, not semantic correctness.
Code with undefined variables or type errors will still be
considered "parsable".
:::

> **See Also**
>
> - `get_raw_ast`: To obtain the AST for further analysis.

##### `TreesitterPython.get_raw_ast`

```python
get_raw_ast(code: str) -> Tree
```

Parse code and return the Tree-sitter AST.

Parses the provided Python source code using Tree-sitter and returns
the resulting abstract syntax tree. The AST can be traversed to
extract syntactic information about the code structure.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `code` | `str` | A string containing Python source code to parse. |

**Returns:**

- `Tree`: A Tree-sitter `Tree` object representing the parsed AST. The
  tree's `root_node` provides access to the entire syntax tree:
  - `root_node.type`: Always `"module"` for valid Python
  - `root_node.children`: Top-level statements
  - `root_node.text`: Original source bytes

:::note
If the source code contains syntax errors, Tree-sitter will still
return a tree but with ERROR nodes at the locations of parse errors.
Use `is_parsable` to check for valid syntax first.
:::

> **See Also**
>
> - `is_parsable`: To validate syntax before parsing.

## Java sanitizer

```python
from cldk.utils.sanitization.java import TreesitterSanitizer
```

### `TreesitterSanitizer`

```python
TreesitterSanitizer(source_code)
```

| Method | Summary |
| ------ | ------- |
| [`keep_only_focal_method_and_its_callees`](#treesittersanitizerkeep_only_focal_method_and_its_callees) | Remove all methods except the focal method and its callees. |
| [`remove_unused_imports`](#treesittersanitizerremove_unused_imports) | Remove imports not referenced in the class body. |
| [`remove_unused_fields`](#treesittersanitizerremove_unused_fields) | Remove fields not referenced in any method or constructor. |
| [`remove_unused_classes`](#treesittersanitizerremove_unused_classes) | Remove unused inner classes. |
| [`sanitize_focal_class`](#treesittersanitizersanitize_focal_class) | Produce sanitized source focused on a focal method. |

Sanitize Java source code using tree-sitter queries.

The sanitizer focuses a class to a given focal method by keeping that
method and its callees, then removes unused fields, imports, and inner
classes. It also strips block comments before processing.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` | `str` | The full Java source code to sanitize. |

#### Attributes

| Name | Type | Description |
| ---- | ---- | ----------- |
| `source_code` |  |  |
| `sanitized_code` |  |  |

#### Methods

##### `TreesitterSanitizer.keep_only_focal_method_and_its_callees`

```python
keep_only_focal_method_and_its_callees(focal_method: str) -> str
```

Remove all methods except the focal method and its callees.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `focal_method` | `str` | The name of the focal method. |

**Returns:**

- `str`: The pruned source code.

**Examples:**

```python
>>> src = 'class A { void keep(){} void drop(){} }'
>>> tz = TreesitterSanitizer(src)
>>> out = tz.keep_only_focal_method_and_its_callees('keep')
>>> 'drop' in out
False
```

##### `TreesitterSanitizer.remove_unused_imports`

```python
remove_unused_imports(sanitized_code: str) -> str
```

Remove imports not referenced in the class body.

Assumes fields have already been pruned. Scans type identifiers and
other identifiers to decide which imports are used. Wildcard imports
are preserved.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `sanitized_code` | `str` | Source code after earlier pruning steps. |

**Returns:**

- `str`: The pruned source code with unused imports removed.

Notes:
- Compare the last segment of each import against collected
  identifiers and type identifiers.
- Keep wildcard imports (ending with '*').

##### `TreesitterSanitizer.remove_unused_fields`

```python
remove_unused_fields(sanitized_code: str) -> str
```

Remove fields not referenced in any method or constructor.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `sanitized_code` | `str` | Source after removing unused methods. |

**Returns:**

- `str`: Source with unused fields removed.

Notes:
- Collect identifiers used in all methods and constructors, then
  drop field declarations whose identifiers don't appear.

**Examples:**

```python
>>> src = 'class A { int x; void f(){ int y = 1; } }'
>>> out = TreesitterSanitizer(src).remove_unused_fields(src)
>>> 'int x;' in out
False
```

##### `TreesitterSanitizer.remove_unused_classes`

```python
remove_unused_classes(sanitized_code: str) -> str
```

Remove unused inner classes.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `sanitized_code` | `str` | The sanitized code to process. |

**Returns:**

- `str`: The pruned source code with unused inner classes removed.

Notes:
- Start from the outermost class, traverse type invocations, and
  keep only reachable inner classes.

**Examples:**

```python
>>> src = 'class A { class B{} }'
>>> out = TreesitterSanitizer(src).remove_unused_classes(src)
>>> 'class B' in out
False
```

##### `TreesitterSanitizer.sanitize_focal_class`

```python
sanitize_focal_class(focal_method: str) -> str
```

Produce sanitized source focused on a focal method.

**Parameters:**

| Name | Type | Description |
| ---- | ---- | ----------- |
| `focal_method` | `str` | The focal method declaration text or name. |

**Returns:**

- `str`: Pruned source code with only relevant members retained.

<!-- CLDK:API:END -->
