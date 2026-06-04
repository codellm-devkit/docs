import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mermaid from "astro-mermaid";
import { pluginCollapsibleSections } from "@expressive-code/plugin-collapsible-sections";
import { pluginLineNumbers } from "@expressive-code/plugin-line-numbers";

// https://astro.build/config
export default defineConfig({
  site: "https://codellm-devkit.info",
  integrations: [
    // Mermaid must run BEFORE Starlight so it can preprocess ```mermaid blocks.
    mermaid({
      theme: "neutral",
      autoTheme: true,
      mermaidConfig: {
        flowchart: { curve: "basis" },
      },
    }),
    starlight({
      title: "CLDK",
      tagline: "One analysis interface over every language: program analysis your agents can call.",
      description:
        "CLDK is a multilingual program analysis framework: one typed analysis facade over call graphs and symbol tables, the same across languages, ready to hand to a code LLM.",
      logo: {
        light: "./src/assets/logo-light.svg",
        dark: "./src/assets/logo-white.svg",
        replacesTitle: false,
      },
      favicon: "/favicon.png",
      customCss: ["./src/styles/docs.css"],
      expressiveCode: {
        plugins: [pluginCollapsibleSections(), pluginLineNumbers()],
        styleOverrides: {
          borderRadius: "0.4rem",
          frames: {
            shadowColor: "transparent",
          },
        },
        defaultProps: {
          // Opt in to line numbers per-block with showLineNumbers.
          showLineNumbers: false,
        },
      },
      head: [
        {
          tag: "link",
          attrs: { rel: "preconnect", href: "https://fonts.googleapis.com" },
        },
        {
          tag: "link",
          attrs: {
            rel: "preconnect",
            href: "https://fonts.gstatic.com",
            crossorigin: "",
          },
        },
        {
          tag: "link",
          attrs: {
            rel: "stylesheet",
            href: "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap",
          },
        },
      ],
      social: [
        {
          icon: "github",
          label: "CLDK on GitHub",
          href: "https://github.com/codellm-devkit/python-sdk",
        },
        {
          icon: "seti:python",
          label: "CLDK on PyPI",
          href: "https://pypi.org/project/cldk",
        },
        {
          icon: "discord",
          label: "CLDK on Discord",
          href: "https://discord.gg/zEjz9YrmqN",
        },
      ],
      editLink: {
        baseUrl: "https://github.com/codellm-devkit/docs/edit/main/",
      },
      sidebar: [
        {
          label: "Start here",
          items: [
            { label: "Home", link: "/", attrs: { "data-cldk-icon": "layers-16" } },
            { label: "What is CLDK?", slug: "what-is-cldk", attrs: { "data-cldk-icon": "cube-16" } },
            { label: "Quickstart", slug: "quickstart", attrs: { "data-cldk-icon": "flame-16" } },
            { label: "Installation", slug: "installing", attrs: { "data-cldk-icon": "archive-16" } },
          ],
        },
        {
          label: "Guides",
          items: [
            { label: "Core concepts", slug: "guides/concepts", attrs: { "data-cldk-icon": "learning-16" } },
            { label: "Common tasks", slug: "guides/common-tasks", attrs: { "data-cldk-icon": "workflow-16" } },
          ],
        },
        {
          label: "Build with CLDK",
          items: [
            {
              label: "A Code Context Agent (COCOA)",
              slug: "cocoa",
              badge: { text: "★", variant: "tip" },
              attrs: { "data-cldk-icon": "chat-16" },
            },
          ],
        },
        {
          label: "Examples",
          items: [
            { label: "Overview", slug: "examples", attrs: { "data-cldk-icon": "widget-16" } },
            { label: "Java examples", slug: "examples/java", attrs: { "data-cldk-icon": "cube-16" } },
            { label: "Python examples", slug: "examples/python", attrs: { "data-cldk-icon": "model-16" } },
          ],
        },
        {
          label: "API Reference",
          items: [
            { label: "Overview", slug: "reference/python-api", attrs: { "data-cldk-icon": "manual-16" } },
            { label: "Core (CLDK)", slug: "reference/python-api/core", attrs: { "data-cldk-icon": "layers-16" } },
            { label: "Java analysis", slug: "reference/python-api/java", attrs: { "data-cldk-icon": "developer-16" } },
            { label: "Python analysis", slug: "reference/python-api/python", attrs: { "data-cldk-icon": "developer-16" } },
          ],
        },
        {
          label: "Backends",
          items: [
            { label: "Overview", slug: "backends", attrs: { "data-cldk-icon": "dataset-16" } },
            { label: "codeanalyzer-java", slug: "backends/codeanalyzer-java", attrs: { "data-cldk-icon": "cube-16" } },
            { label: "codeanalyzer-python", slug: "backends/codeanalyzer-python", attrs: { "data-cldk-icon": "cube-16" } },
            { label: "codeanalyzer-ts", slug: "backends/codeanalyzer-ts", attrs: { "data-cldk-icon": "cube-16" } },
          ],
        },
        {
          label: "Contributing",
          items: [
            { label: "Overview", slug: "contributing", attrs: { "data-cldk-icon": "developer-16" } },
            { label: "Add a language backend (Go)", slug: "contributing/add-language-backend", attrs: { "data-cldk-icon": "workflow-16" } },
            { label: "Add a Rust frontend", slug: "contributing/rust-frontend", attrs: { "data-cldk-icon": "polygon-16" } },
          ],
        },
        {
          label: "Resources",
          items: [
            { label: "Cheat sheet", slug: "resources/cheatsheet", attrs: { "data-cldk-icon": "results-16" } },
            { label: "CLDK over MCP", slug: "resources/cldk-over-mcp", attrs: { "data-cldk-icon": "globe-network-16" } },
          ],
        },
      ],
    }),
  ],
});
