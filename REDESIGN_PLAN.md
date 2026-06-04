# CLDK Docs — Total Redesign Plan

> **Status: IMPLEMENTED (2026-06-04).** Phases A–C built and shipped on the
> `astro` branch — foundations (mermaid + Carbon palette + Space Grotesk/Mono +
> new IA), flagship pages (splash landing, agent recipes, Java 3-zone), and the
> long-tail pages (concepts, common tasks, cheat sheet, CLDK-over-MCP, quickstart
> reframe, python/c/core reference zones). Verified by a clean `npm run build`
> (15 pages) and an adversarial per-page review (0 blockers; 11 major + 4 minor
> findings fixed). The visual direction chosen was "MCP-restraint on Carbon".

> Goal: make **static analysis feel as approachable as pandas/scikit-learn made
> dataframes/ML**, with the polish and agent-orientation of the **MCP** and
> **Claude SDK** docs — and a through-line that **agents should reach for CLDK**
> as their grounding/analysis layer.
>
> Reference aesthetics: MCP (modelcontextprotocol.io), Claude developer docs
> (docs.claude.com), pandas, scikit-learn. Stack: Astro 5 + Starlight 0.37.

This plan is grounded in (a) a verified read of the real CLDK API in
`../python-sdk`, (b) a capability audit of this Starlight site, and (c) design
analysis of the four reference sites. **No invented API.**

---

## 0. The single most important correction (locked facts)

The old todo guessed an `is_reachable()` method and a `target_method_name` arg.
The source says otherwise. **These are the verified, real names** (cite
`cldk/analysis/java/java_analysis.py`):

| Need | Real API | Notes |
| --- | --- | --- |
| Construct | `CLDK(language="java").analysis(project_path=APP)` | java also supports `source_code=`; python/c require `project_path` |
| Method body | `analysis.get_method(qualified_class_name, qualified_method_name).code` | **not** `get_method_body`; body is the `.code` attr of `JCallable` |
| Callers | `analysis.get_callers(target_class_name, target_method_declaration, using_symbol_table=False)` | returns `Dict` |
| Callees | `analysis.get_callees(source_class_name, source_method_declaration, using_symbol_table=False)` | returns `Dict` |
| Call graph | `analysis.get_call_graph() -> networkx.DiGraph` | edges caller→callee; also `get_call_graph_json()` |
| Class call graph | `analysis.get_class_call_graph(qualified_class_name, method_signature=None)` | |
| **Reachability** | **No `is_reachable()`.** Use `nx.has_path(cg, src, sink)` / `nx.all_simple_paths(cg, src, sink)` over `get_call_graph()` | this is the killer teaching point — see §6 |
| Tree-sitter prune | `cldk.tree_sitter_utils(source_code).sanitize_focal_class(focal_method)` | |

**Language coverage caveats (drive scope):**
- **Java** — richest: symbol table, classes/methods, call graph, callers/callees, class hierarchy, CRUD, comments, tree-sitter. *Anchor all flagship examples here.*
- **Python** — strong: `get_call_graph`, `get_callers`, `get_callees`, symbol table. (No `source_code` mode.)
- **C** — minimal: `get_c_application()`, `get_functions()`. **No call graph / callers / callees.** Do not show call-graph recipes for C.
- **TypeScript** — exists (`cldk.analysis.typescript`) but less mature; keep out of the flagship narrative for now.

---

## 1. North star & principles (from the reference sites)

1. **Lead with a definition + one analogy, not a feature wall** (MCP: "USB-C port for AI"). CLDK's analog: *"CLDK is pandas for source code — one object model over call graphs, symbol tables, and ASTs across languages, ready to hand to an LLM."*
2. **Time-to-first-analysis in seconds** (pandas): `pip install cldk` on line one; a 5-line "first analysis" above the fold.
3. **A capability map at a glance** (scikit-learn's 6-card grid): the landing *is* a map of what CLDK can do, each card = one capability with a one-line definition + a real artifact thumbnail + example bullets.
4. **Task language, not API nouns** (pandas/scikit): pages titled "Find who calls this method", "Is this sink reachable?", not "`get_callers`".
5. **The generated symbol dump is the *appendix* of a page, not the page** (MCP). Author the top; generate the bottom.
6. **Separate LEARN from REFERENCE** (all four): Guides/Concepts vs API Reference as distinct top-level lanes.
7. **Agent-native is the headline, not a footnote**: analysis methods are *tools the model calls*. CLDK = the deterministic ground truth that stops the model hallucinating about code.
8. **Honest input→output everywhere** (pandas/scikit): every snippet shows its printed/returned result.
9. **One recurring sample codebase** (pandas' Titanic): use **Apache Commons CLI** (already in the quickstart) as the "Titanic of CLDK" across all Java examples.

---

## 2. Visual design system

**Direction:** MCP-style restraint (near-monochrome, let code + diagrams carry
color, disciplined typography/whitespace) carried on CLDK's existing **IBM
Carbon** identity (IBM Plex + `#0f62fe` blue). Warmth/approachability comes from
pandas/scikit devices (cards, thumbnails, friendly task titles), not loud color.

- **Palette:** extend `src/styles/docs.css` beyond the accent ramp — define the full Starlight token set (gray scale, `--sl-color-bg`/`-bg-nav`/`-bg-sidebar`/`-bg-inline-code`, hairlines, callout colors) for both themes so it stops looking like "default Starlight + blue". Carbon-influenced neutrals; one accent (`#0f62fe`), darker surfaces in dark mode.
- **Type:** keep IBM Plex Sans / Plex Mono (already wired). Tighten the `--sl-text-*` scale and `--sl-content-width` for a denser, reference-grade feel.
- **Components to actually use** (mostly unused today): `Steps` (quickstart/recipes loop), `LinkCard`/`CardGrid` (landing + "next steps"), `LinkButton` (hero CTAs), `Badge` (language/maturity tags, e.g. `Java` `Python` `C: limited`), `Tabs` with `syncKey` (sync language across the whole site), `FileTree` (project layout), `Aside` (replace the raw `<details>` in quickstart), `Code` (render generated/imported snippets).
- **Mermaid:** **not wired today.** Add `astro-mermaid` (`npm i astro-mermaid mermaid`), register **before** `starlight()`, `autoTheme: true`. Restores the architecture diagram lost in the migration and powers the call-graph / data-layer diagrams.
- **Expressive Code:** add `@expressive-code/plugin-collapsible-sections` (fold boilerplate in long recipe snippets) and `@expressive-code/plugin-line-numbers`; set `styleOverrides.borderRadius`. Use frames + titles + line highlighting (already partly used).
- **Custom landing:** switch home to Starlight's `template: splash` with a structured `hero` (title/tagline/dark+light image/action buttons). Optionally a `Hero` component override for a bespoke marketing band above the capability grid.
- **Tailwind:** *not* required — the CSS-custom-property approach is enough. (Note `@astrojs/starlight-tailwind` as an option if we later want utility-class landing sections.)

---

## 3. Information architecture (new sidebar)

Two-axis IA: **personas on the landing page**, **Learn vs Reference in the sidebar.**

```
Top nav / sidebar groups
├─ Start here
│   ├─ What is CLDK?           (concept + analogy + architecture mermaid)   [new]
│   ├─ Quickstart              (agent-native, 3 Steps)                       [rework]
│   └─ Installation
├─ Guides  (LEARN — prose-first, deep-link into Reference)
│   ├─ Core concepts: symbol table, call graph, reachability, analysis levels [new]
│   ├─ Common tasks            (task-titled snippet index)                    [new, todo #9]
│   ├─ Agent recipes ★         (the centerpiece — agent-native, Anthropic SDK) [new, todo #1]
│   └─ Coming from… (tree-sitter / CodeQL / raw mkdocstrings)                 [new, stretch]
├─ API Reference  (REFERENCE — authored top, generated bottom)
│   ├─ Overview                (mental model + capability grid + mermaid)     [rework, todo #2]
│   ├─ Core (CLDK)
│   ├─ Java analysis           (3-zone: overview/backend → worked example → symbols) [rework, todo #3]
│   ├─ Python analysis         (3-zone)
│   └─ C analysis              (3-zone; mark call-graph features N/A)
└─ Resources
    ├─ Cheat sheet             (one-page quick reference; pandas-style)        [new]
    └─ CLDK over MCP           (analysis methods as MCP tools)                 [stretch, todo #8]
```

Covers every todo item: #1 Agent recipes, #2 reference overview, #3 three-zone
language pages, #4 IA split, #5 symbol-gen, #6 quickstart, #7 mermaid+EC, #8 MCP,
#9 common tasks.

---

## 4. Landing page (`index.mdx` → splash)

Anatomy (scikit-learn grid × pandas approachability × MCP restraint):

1. **Hero**: wordmark + one sentence ("pandas for source code…") + `pip install cldk` + two `LinkButton`s: **Quickstart** and **Agent recipes**.
2. **First analysis above the fold**: a ~6-line tabbed (Java/Python) snippet that loads a project and prints the call graph size — *input→output*.
3. **Capability grid (the scikit-learn move)** — `CardGrid` of 6 cards, each = one-line definition + thumbnail (a real rendered artifact — call-graph mermaid, symbol-table JSON, sanitized class) + 2 example bullets, linking to the matching capability/reference page:
   - Symbol tables · Call graphs · Reachability · Class structure & hierarchy · CRUD/data-access · Tree-sitter utilities
4. **"Agents prefer CLDK" band**: short pitch + the data-layer mermaid (Claude ⇄ tool loop ⇄ CLDK ⇄ {call graph, symbol table, tree-sitter}) → link to Agent recipes.
5. **Start-building / Learn-more `CardGrid`s** (MCP pattern) and the existing badges/contact.

---

## 5. "What is CLDK?" + reference overview (todo #2)

- Plain-language mental model: **`CLDK(language)` → `analysis` facade → typed `models`/schema**, backed by real engines (Java=WALA/codeanalyzer, Python=Jedi+CodeQL, C=libclang, all + Tree-sitter). The home page name-drops these engines but never connects them to the API — **make that connection explicit** (todo #3, Zone A).
- **Architecture mermaid** (restored/expanded from README) and the analysis-level model.
- Replace the bullet-link reference index with the capability `CardGrid` + `LinkCard`s.

---

## 6. Agent recipes — the centerpiece (todo #1)

New page `src/content/docs/guides/agent-recipes.mdx`. Anthropic SDK tool-use,
**prompt caching from the start** (per the `claude-api` skill), three recipes on
**one shared, verified tool layer**. Anchor in **Java + Commons CLI**.

**Shared tool layer (verified against source):**

```python
import anthropic, networkx as nx
from cldk import CLDK

analysis = CLDK(language="java").analysis(project_path=APP)   # JavaAnalysis facade

TOOLS = [
  {"name": "get_method_body", "description": "...",
   "input_schema": {"type":"object","properties":{
       "qualified_class_name":{"type":"string"},
       "qualified_method_name":{"type":"string"}}, "required":[...]}},
  {"name": "get_callers", "description": "...",
   "input_schema": {... "target_class_name","target_method_declaration" ...}},
  {"name": "get_callees", "description": "...",
   "input_schema": {... "source_class_name","source_method_declaration" ...}},
  {"name": "is_reachable", "description": "Is sink reachable from source in the call graph?",
   "input_schema": {... "source","sink" ...}},
]

CG = analysis.get_call_graph()                # networkx.DiGraph, cached once

def dispatch(name, args):
    if name == "get_method_body":
        return analysis.get_method(args["qualified_class_name"],
                                   args["qualified_method_name"]).code
    if name == "get_callers":
        return analysis.get_callers(args["target_class_name"],
                                    args["target_method_declaration"])
    if name == "get_callees":
        return analysis.get_callees(args["source_class_name"],
                                    args["source_method_declaration"])
    if name == "is_reachable":
        return nx.has_path(CG, args["source"], args["sink"])   # ground truth, not a guess

# run_agent(task): messages.create tool-use loop until stop_reason != "tool_use".
# Cache the stable TOOLS + system block:  "cache_control": {"type": "ephemeral"}
```

> **Build-time TODO:** confirm the exact node-identity convention of the
> `get_call_graph()` DiGraph (node = method id?) on a real Commons CLI run before
> finalizing the `is_reachable` node resolution. Verify by inspecting a live graph,
> not by guessing.

- **Recipe 1 — Call-graph-guided Q&A** (gentle intro): "How does `Option.create` work, and what calls it?" Show the trace of tool calls the model chooses. Establishes the loop.
- **Recipe 2 — Source-to-sink reachability** (the killer demo): feed a Bandit/Semgrep-style alert; agent calls `get_callers`/`is_reachable` to confirm or refute. **Teaching point, stated explicitly:** CLDK returns *ground truth the model would otherwise hallucinate*. Cross-link the `poe-with-cldk` / `triage-and-pov` skills.
- **Recipe 3 — Targeted refactor**: agent enumerates **all** callers via CLDK *before* proposing an API change, so the edit is safe — CLDK preventing a whole class of agent mistakes.
- Components: `Steps` for the loop, `Tabs` for request/response pairs, `Aside type="caution"` for gotchas, the data-layer **mermaid**, collapsible EC sections for boilerplate.

---

## 7. Per-language API reference → three zones (todo #3)

For `java.md` / `python.md` / `c-cpp.md` (+ `core.md`):
- **Zone A — Overview**: what this analyzer does, which **backend** it wraps, analysis levels, a `Badge` maturity row.
- **Zone B — Worked example**: `Tabs`/`Steps` walkthrough ("Get the symbol table" / "Build a call graph" / "Find callers") on Commons CLI, input→output.
- **Zone C — Reference**: the generated symbols (from §8), grouped by category.

C page explicitly marks call-graph/callers/callees as **not available**.

---

## 8. API symbol generation (todo #5)

Keep & **extend** `scripts/gen_api_docs.py` (griffe). Port the spirit of the old
mkdocstrings options: group **by category** (use the `category` we already derive),
clean signatures, source links, `filters: ["!^_"]`, source member order. Emit the
**Zone C** block that gets composed under the authored Zones A/B (e.g. generate a
partial that the hand-authored page imports, or generate full pages whose top
matter is hand-authored and bottom is generated between markers). Decision to lock
at build time: *generated partial included into authored MDX* (cleanest).

---

## 9. Quickstart reframe (todo #6)

Current example is the old paradigm (build prompt string → `ollama.generate()` →
text). Reframe as **agent-native** with `Steps`, or explicitly label it the
"hello world" and link to Agent recipes as the real pattern. Recommendation:
keep a 3-step *hello world* (install → load project → one analysis call with
printed output), then a prominent `LinkCard` to Agent recipes. Replace raw
`<details>` with `<Aside>`.

---

## 10. Stretch (todos #8, #9)

- **Common tasks** index (todo #9): task-titled list → tabbed snippets, each feeding the agent-native framing.
- **CLDK over MCP** (todo #8): show CLDK analysis methods exposed as an MCP server (each method = an MCP tool) — closes the conceptual loop with our reference point. Even a short stub lands hard.
- **Cheat sheet** (pandas): one-page quick reference of the handful of objects/methods.

---

## 11. Build sequence (honours the todo's REVIEW GATE)

**Phase A — Foundations (no visible risk):**
1. Wire `astro-mermaid` + EC plugins; extend `docs.css` into a full token palette; add `src/components/` scaffold.
2. Restructure the sidebar/IA in `astro.config.mjs` (Start here / Guides / API Reference / Resources).

**Phase B — Prototype slice for SIGN-OFF (the review gate):**
3. New **splash landing** with hero + 6-card capability grid + agent band.
4. **Agent recipes** page: shared tool layer + Recipe 1 in full, Recipes 2 & 3 stubbed.
5. **`java.md`** reworked into the three-zone structure.
6. → **Review with maintainer before rolling out.**

**Phase C — Roll out after sign-off:**
7. Apply three-zone to `python.md` / `c-cpp.md` / `core.md`; extend `gen_api_docs.py` for Zone C.
8. "What is CLDK?" + concepts + common-tasks + quickstart reframe.
9. Stretch: cheat sheet, CLDK-over-MCP, "Coming from…" guides.

**Verification each phase:** `npm run build` clean + Playwright screenshots of
landing / recipes / a language page in light & dark.

---

## 12. Risks & how this plan de-risks them

- **Inventing API** (the #1 risk the todo flags): mitigated — every method above is verified against source with an adversarial cross-check; `is_reachable` corrected to a NetworkX query; `get_method` arg names corrected.
- **C over-promising**: scope rules keep call-graph recipes Java/Python-only.
- **Call-graph node identity** for `is_reachable`: flagged as a build-time verification on a live graph before the recipe ships.
- **"Looks like default Starlight"**: addressed by the full token palette + splash template + component overrides, not just accent color.
