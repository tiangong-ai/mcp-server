---
docType: standard
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When creating, moving, or reviewing MCP repository documentation."
whenToUpdate: "When documentation layers, metadata rules, or source-of-truth boundaries change."
checkPaths:
  - AGENTS.md
  - AGENTS_ZH.md
  - .docpact/config.yaml
  - .github/workflows/docpact.yml
  - .github/prompts/**
  - _docs/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# MCP Documentation Standards

## Layers

- `AGENTS.md`: mandatory repo entry guidance for agents.
- `.docpact/config.yaml`: machine-readable governance, routing, coverage, and
  document inventory.
- `.github/workflows/docpact.yml`: CI enforcement for config validation and PR
  documentation lint.
- `_docs/contracts/**`: current constraints and ownership rules.
- `_docs/architecture/**`: current server topology and integration facts.
- `_docs/runbooks/**`: executable procedures.
- `_docs/standards/**`: repo-local documentation and engineering standards.
- `.github/prompts/**`: agent-consumed update guidance for MCP changes.

## Rules

- Keep deterministic governance facts in `.docpact/config.yaml`.
- Keep explanatory architecture, auth, tool, and workflow details in `_docs/**`.
- Update docs when MCP tool names, schemas, auth behavior, transport paths,
  package binaries, or required environment variables change.
- Keep localized docs aligned when user-visible setup or operational behavior
  changes.
- Keep agent prompts aligned with maintained entry points and validation
  commands; remove stale workaround notes when package metadata has moved on.
- Do not duplicate root workspace branch policy or submodule integration policy
  in this repository.
