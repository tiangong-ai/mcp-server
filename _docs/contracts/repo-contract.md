---
docType: contract
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When deciding whether a change belongs in the MCP server repository."
whenToUpdate: "When ownership, MCP tool contracts, auth boundaries, or completion criteria change."
checkPaths:
  - AGENTS.md
  - README.md
  - .docpact/config.yaml
  - src/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# MCP Repository Contract

## Ownership

This repository owns the Model Context Protocol server that exposes TianGong AI
search capabilities over Streamable HTTP and local package entry points. It also
owns MCP tool schemas, auth handling, server startup, and repo-local deployment
metadata.

## Boundaries

- Supabase Edge Function implementation belongs in the edge-function repository.
- Knowledge-base ingestion and document processing belong in the KB and
  unstructure repositories.
- Root workspace governance, branch policy, and submodule integration remain in
  the workspace repository.

## Public Surface

The MCP tool names, Zod schemas, transport endpoint, auth requirements, and
server binary name are integration contracts. Changes to those surfaces require
review of:

- `AGENTS.md`
- `README.md` / `README_CN.md`
- `_docs/architecture/repo-architecture.md`
- `_docs/runbooks/development.md`

## Completion Criteria

- Run `docpact route` before editing governed files.
- Run `docpact validate-config --root . --strict` after governance changes.
- Run `npm run build` for TypeScript or runtime changes.
- Run the local HTTP server command from `_docs/runbooks/development.md` or
  targeted client checks when HTTP transport, auth, or tool behavior changes.
