---
docType: index
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When navigating MCP repository documentation."
whenToUpdate: "When repository documentation layers, key docs, or governance routing change."
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

# MCP Documentation

This directory contains the repo-local source documents governed by docpact.
Agent prompt files under `.github/prompts/**` are governed with the same
low-entropy source-of-truth rules.

## Layers

- Layer 0: `AGENTS.md` for mandatory agent entry guidance.
- Layer 1: `.docpact/config.yaml` for machine-readable governance.
- CI: `.github/workflows/docpact.yml` for config validation and PR
  documentation lint.
- Layer 2: current contracts, architecture, standards, and runbooks under
  `_docs/**`.
- Agent prompts: `.github/prompts/**` for MCP update guidance that is consumed
  by coding assistants.

## Current Documents

- `_docs/contracts/repo-contract.md`: repository ownership, boundaries, and
  completion rules.
- `_docs/architecture/repo-architecture.md`: MCP server topology.
- `_docs/runbooks/development.md`: build, local server, and validation workflow.
- `_docs/standards/documentation-standards.md`: repo-local documentation rules.
- `.github/prompts/mcp_update_guidelines_en.md`: English MCP update prompt.
- `.github/prompts/mcp_update_guidelines_zh.md`: Chinese MCP update prompt.
