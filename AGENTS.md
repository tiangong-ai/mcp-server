---
docType: agent-contract
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "Before editing the MCP server repository."
whenToUpdate: "When repo entry points, workflow commands, docpact config, MCP tools, auth behavior, or deployment boundaries change."
checkPaths:
  - AGENTS.md
  - .docpact/config.yaml
  - .github/workflows/docpact.yml
  - .github/prompts/**
  - _docs/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# TianGong AI MCP Agent Contract

This repository owns the MCP server surface for TianGong AI. Workspace-level
submodule policy remains in the root workspace; MCP implementation and
repo-local documentation belong here.

## Required Load Order

1. Read this file.
2. Read `.docpact/config.yaml`.
3. Run `docpact route --root . --paths <target-paths> --format json` from this
   repo root for the files you plan to change.
4. Read the relevant files under `_docs/contracts/**`, `_docs/architecture/**`,
   and `_docs/runbooks/**`.
5. Read the implementation files under `src/**`.

## Source Of Truth

- `.docpact/config.yaml`: machine-readable governance rules, routing aliases,
  coverage, document inventory, and freshness policy.
- `README.md`, `README_CN.md`, `DEV_EN.md`, and `DEV_CN.md`: user-facing and
  developer-facing workflow notes.
- `_docs/contracts/repo-contract.md`: durable ownership and boundary rules.
- `_docs/architecture/repo-architecture.md`: current MCP server topology.
- `_docs/runbooks/development.md`: repeatable build, local server, and
  validation steps.

## Hard Boundaries

- Do not move workspace submodule policy, branch policy, or integration
  completion rules into this repository.
- Treat MCP tool schemas, authentication behavior, and response streaming as
  public integration contracts.
- Do not commit real Supabase, Upstash, LangSmith, or deployment secrets.

## Completion Criteria

- Relevant docpact route output has been reviewed before code or docs changes.
- Docs touched by the route result are reviewed or updated.
- `docpact validate-config --root . --strict` passes after governance changes.
- For implementation changes, run the relevant build or server validation from
  `_docs/runbooks/development.md`.

## Implementation Pointers

For tool names, server entry points, auth, and commands, use
`_docs/architecture/repo-architecture.md`, `_docs/runbooks/development.md`, and
`package.json` as the maintained references.
