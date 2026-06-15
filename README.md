<picture>
  <source media="(prefers-color-scheme: dark)" srcset="public/assets/images/cldk-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="public/assets/images/cldk-light.png">
  <img src="public/assets/images/cldk-light.png" alt="Logo">
</picture>

<p align='center'>
  <a href="https://arxiv.org/abs/2410.13007">
    <img src="https://img.shields.io/badge/arXiv-2410.13007-b31b1b?style=for-the-badge" />
  </a>
  <a href="https://www.python.org/downloads/release/python-3110/">
    <img src="https://img.shields.io/badge/python-3.11-blue?style=for-the-badge" />
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge" />
  </a>
  <a href="https://ibm.github.io/codellm-devkit/">
    <img src="https://img.shields.io/badge/GitHub%20Pages-Docs-blue?style=for-the-badge" />
  </a>
  <a href="https://badge.fury.io/py/cldk">
    <img src="https://img.shields.io/pypi/v/cldk?style=for-the-badge&label=codellm-devkit&color=blue" />
  </a>
  <a href="https://discord.gg/zEjz9YrmqN">
    <img src="https://dcbadge.limes.pink/api/server/https://discord.gg/zEjz9YrmqN?style=for-the-badge"/>
  </a>
</p>

Codellm-Devkit (CLDK) is a multilingual program analysis framework for CodeLLM workflows. It turns source code into structured program facts such as symbols, method bodies, call graphs, and data-model objects that an LLM pipeline can query.

CLDK is an open-source Python library over language-specific analysis backends. The user calls one API; the backend handles parsing, symbol resolution, and graph construction for the selected language.

**The purpose of Codellm-Devkit is to help build analysis pipelines that combine program-analysis results with CodeLLMs.**
It gives those pipelines a consistent shape across languages and analysis tools.

CLDK integrates with tools such as WALA, Tree-sitter, LLVM, and CodeQL. It normalizes their outputs into typed models that downstream code can consume.

CLDK is an ongoing IBM Research project.

Codellm-Devkit is:

- **Unified**: one API over language-specific analysis backends.
- **Extensible**: new backends can add languages or analysis tools.
- **Structured**: code becomes typed models, call graphs, and other queryable artifacts.

## Contact

For any questions, feedback, or suggestions, please contact the authors:

| Name | Email |
| ---- | ----- |
| Rahul Krishna | [i.m.ralk@gmail.com](mailto:imralk+oss@gmail.com) |
| Rangeet Pan | [rangeet.pan@ibm.com](mailto:rangeet.pan@gmail.com) |
| Saurabh Sihna | [sinhas@us.ibm.com](mailto:sinhas@us.ibm.com) |
## Table of Contents

- [Contact](#contact)
- [Table of Contents](#table-of-contents)
- [Architectural and Design Overview](#architectural-and-design-overview)
- [Quick Start: Example Walkthrough](#quick-start-example-walkthrough)
  - [Prerequisites](#prerequisites)
  - [Step 1:  Set up an Ollama server](#step-1--set-up-an-ollama-server)
    - [Pull the latest version of Granite 8b instruct model from ollama](#pull-the-latest-version-of-granite-8b-instruct-model-from-ollama)
  - [Step 2:  Install CLDK](#step-2--install-cldk)
  - [Step 3:  Build a code summarization pipeline](#step-3--build-a-code-summarization-pipeline)
  - [Publication (papers and blogs related to CLDK)](#publication-papers-and-blogs-related-to-cldk)

## Architectural and Design Overview

Below is a high-level view of CLDK's architecture:


```mermaid
graph TD
User <--> A[CLDK]
    A --> 15[Retrieval ‡]
    A --> 16[Prompting ‡]
    A[CLDK] <--> B[Languages]
        B --> C[Java, Python, Go ‡, C ‡, JavaScript ‡, TypeScript ‡, Rust ‡]
            C --> D[Data Models]
                D --> 13{Pydantic}
            13 --> 7            
            C --> 7{backends}
                7 <--> 9[WALA]
                    9 <--> 14[Analysis]
                7 <--> 10[Tree-sitter] 
                    10 <--> 14[Analysis]
                7 <--> 11[LLVM ‡]
                    11 <--> 14[Analysis]
                7 <--> 12[CodeQL ‡]
                    12 <--> 14[Analysis]

    

X[‡ Yet to be implemented]
```

The user invokes the CLDK API. CLDK delegates the request to the language-specific module.

Each language has two main components: data models and backends.

1. **Data Models:** Pydantic models for language constructs such as files, classes, methods, fields, and call edges. They support attribute access and serialization.

2. **Analysis Backends:** Components that call program-analysis tools such as Treesitter, Javaparser, WALA, LLVM, and CodeQL. The user calls high-level methods such as `get_method_body`, `get_method_signature`, or `get_call_graph`; the backend runs the required analysis and returns the result.

    Some languages may have multiple backends. For example, Java uses WALA, Javaparser, Treesitter, and CodeQL-backed analysis.

Retrieval and prompting components are still in progress. Retrieval will pull relevant code snippets for RAG use cases. Prompting will generate CodeLLM prompts with frameworks such as `PDL`, `Guidance`, or `LMQL`.

## Quick Start: Example Walkthrough

In this section, we will walk through a simple example to demonstrate how to use CLDK. We will:

* Set up a local ollama server to interact with CodeLLMs
* Build a simple code summarization pipeline for a Java and a Python application.

### Prerequisites

Before we begin, make sure you have the following prerequisites installed:

  * Python 3.11 or later
  * Ollama v0.3.4 or later

### Step 1:  Set up an Ollama server

If don't already have ollama, please download and install it from here: [Ollama](https://ollama.com/download). 

Once you have ollama, start the server and make sure it is running.

If you're on MacOS, Linux, or WSL, you can check to make sure the server is running by running the following command:

```bash
sudo systemctl status ollama
```

You should see an output similar to the following:

```bash
➜ sudo systemctl status ollama
● ollama.service - Ollama Service
     Loaded: loaded (/etc/systemd/system/ollama.service; enabled; preset: enabled)
     Active: active (running) since Sat 2024-08-10 20:39:56 EDT; 17s ago
   Main PID: 23069 (ollama)
      Tasks: 19 (limit: 76802)
     Memory: 1.2G (peak: 1.2G)
        CPU: 6.745s
     CGroup: /system.slice/ollama.service
             └─23069 /usr/local/bin/ollama serve
```

If not, you may have to start the server manually. You can do this by running the following command:

```bash
sudo systemctl start ollama
```

#### Pull the latest version of Granite 8b instruct model from ollama

To pull the latest version of the Granite 8b instruct model from ollama, run the following command:

```bash
ollama pull granite-code:8b-instruct
```

Check to make sure the model was successfully pulled by running the following command:

```bash
ollama run granite-code:8b-instruct 'Write a function to print hello world in python'
```

The output should be similar to the following:

```
➜ ollama run granite-code:8b-instruct 'Write a function to print hello world in python'

def say_hello():
    print("Hello World!")
```

### Step 2:  Install CLDK

You may install the latest version of CLDK from [PyPi](https://pypi.org/project/cldk/):

```python
pip install cldk
```

Once CLDK is installed, you can import it into your Python code:

```python
from cldk import CLDK
```

### Step 3:  Build a code summarization pipeline

Now that we have set up the ollama server and installed CLDK, we can build a simple code summarization pipeline for a Java application.

1. Let's download a sample Java (apache-commons-cli):

    * Download and unzip the sample Java application:
        ```bash
        wget https://github.com/apache/commons-cli/archive/refs/tags/rel/commons-cli-1.7.0.zip -O commons-cli-1.7.0.zip && unzip commons-cli-1.7.0.zip
        ```
    * Record the path to the sample Java application:
        ```bash
        export JAVA_APP_PATH=/path/to/commons-cli-1.7.0 
      ```

Below is a simple code summarization pipeline for a Java application using CLDK. It does the following things:

* Creates a new instance of the CLDK class (see comment `# (1)`)
* Creates an analysis object over the Java application (see comment `# (2)`)
* Iterates over all the files in the project (see comment `# (3)`)
* Iterates over all the classes in the file (see comment `# (4)`)
* Iterates over all the methods in the class (see comment `# (5)`)
* Gets the code body of the method (see comment `# (6)`)
* Initializes the treesitter utils for the class file content (see comment `# (7)`)
* Sanitizes the class for analysis (see comment `# (8)`)
* Formats the instruction for the given focal method and class (see comment `# (9)`)
* Prompts the local model on Ollama (see comment `# (10)`)
* Prints the instruction and LLM output (see comment `# (11)`)

```python
# code_summarization_for_java.py

from cldk import CLDK


def format_inst(code, focal_method, focal_class):
    """
    Format the instruction for the given focal method and class.
    """
    inst = f"Question: Can you write a brief summary for the method `{focal_method}` in the class `{focal_class}` below?\n"

    inst += "\n"
    inst += f"```{language}\n"
    inst += code
    inst += "```" if code.endswith("\n") else "\n```"
    inst += "\n"
    return inst

def prompt_ollama(message: str, model_id: str = "granite-code:8b-instruct") -> str:
    """Prompt local model on Ollama"""
    response_object = ollama.generate(model=model_id, prompt=message)
    return response_object["response"]


if __name__ == "__main__":
    # (1) Create a new instance of the CLDK class
    cldk = CLDK(language="java")

    # (2) Create an analysis object over the java application
    analysis = cldk.analysis(project_path=os.getenv("JAVA_APP_PATH"))

    # (3) Iterate over all the files in the project
    for file_path, class_file in analysis.get_symbol_table().items():
        class_file_path = Path(file_path).absolute().resolve()
        # (4) Iterate over all the classes in the file
        for type_name, type_declaration in class_file.type_declarations.items():
            # (5) Iterate over all the methods in the class
            for method in type_declaration.callable_declarations.values():
                
                # (6) Get code body of the method
                code_body = class_file_path.read_text()
                
                # (7) Initialize the treesitter utils for the class file content
                tree_sitter_utils = cldk.tree_sitter_utils(source_code=code_body)
                
                # (8) Sanitize the class for analysis
                sanitized_class = tree_sitter_utils.sanitize_focal_class(method.declaration)

                # (9) Format the instruction for the given focal method and class
                instruction = format_inst(
                    code=sanitized_class,
                    focal_method=method.declaration,
                    focal_class=type_name,
                )

                # (10) Prompt the local model on Ollama
                llm_output = prompt_ollama(
                    message=instruction,
                    model_id="granite-code:20b-instruct",
                )

                # (11) Print the instruction and LLM output
                print(f"Instruction:\n{instruction}")
                print(f"LLM Output:\n{llm_output}")
```

### Publication (papers and blogs related to CLDK)
1. Krishna, Rahul, Rangeet Pan, Raju Pavuluri, Srikanth Tamilselvam, Maja Vukovic, and Saurabh Sinha. "[Codellm-Devkit: A Framework for Contextualizing Code LLMs with Program Analysis Insights.](https://arxiv.org/pdf/2410.13007)" arXiv preprint arXiv:2410.13007 (2024).
2. Pan, Rangeet, Myeongsoo Kim, Rahul Krishna, Raju Pavuluri, and Saurabh Sinha. "[Multi-language Unit Test Generation using LLMs.](https://arxiv.org/abs/2409.03093)" arXiv preprint arXiv:2409.03093 (2024).
3. Pan, Rangeet, Rahul Krishna, Raju Pavuluri, Saurabh Sinha, and Maja Vukovic., "[Simplify your Code LLM solutions using CodeLLM Dev Kit (CLDK).](https://www.linkedin.com/pulse/simplify-your-code-llm-solutions-using-codellm-dev-kit-rangeet-pan-vnnpe/?trackingId=kZ3U6d8GSDCs8S1oApXZgg%3D%3D)", Blog.

---

## Building the documentation site

This documentation site is built with [Astro](https://astro.build/) +
[Starlight](https://starlight.astro.build/) (migrated from MkDocs).

```sh
npm install
npm run dev        # dev server at http://localhost:4321
npm run build      # production build into dist/
```

### Regenerating the Python API reference

The `src/content/docs/reference/python-api/{core,java,python,c-cpp}.md` pages are
auto-generated from the release-tagged
[`codellm-devkit/python-sdk`](https://github.com/codellm-devkit/python-sdk)
with [griffe](https://mkdocstrings.github.io/griffe/) (the engine behind
mkdocstrings). Run it from an environment where `cldk` is installed, so the
re-exported schema models resolve to their real definitions:

```sh
python -m venv .venv-docs && . .venv-docs/bin/activate
pip install cldk griffe            # or: pip install -e ../python-sdk
python scripts/gen_api_docs.py     # pass --search-path ../python-sdk for a local checkout
```

Deployment is automated by `.github/workflows/deploy.yml` on every push to
`main`: it clones the python-sdk at its latest release tag, regenerates the API
reference, builds the site, and publishes `dist/` to `gh-pages`
(custom domain `codellm-devkit.info` via `public/CNAME`).
