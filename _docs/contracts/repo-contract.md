---
docType: contract
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: 'When deciding whether a change belongs in the MCP server repository.'
whenToUpdate: 'When ownership, MCP tool contracts, auth boundaries, or completion criteria change.'
checkPaths:
  - AGENTS.md
  - README.md
  - .docpact/config.yaml
  - src/**
lastReviewedAt: 2026-10-12
lastReviewedCommit: 3f39012edf73bc825944b15647fcce8ae6ad3cae
---

# MCP Repository Contract

## Ownership

This repository owns the Model Context Protocol server that exposes TianGong AI search capabilities over Streamable HTTP and local package entry points. It also owns MCP tool schemas, auth handling, server startup, and repo-local deployment metadata.

## Boundaries

- Supabase Edge Function implementation belongs in the edge-function repository.
- Knowledge-base ingestion and document processing belong in the KB and unstructure repositories.
- Root workspace governance, branch policy, and submodule integration remain in the workspace repository.

## Public Surface

The MCP tool names, Zod schemas, transport endpoint, auth requirements, and server binary name are integration contracts. Changes to those surfaces require review of:

- `AGENTS.md`
- `README.md` / `README_CN.md`
- `_docs/architecture/repo-architecture.md`
- `_docs/runbooks/development.md`

The retired education graph service has no supported MCP tool. Removal of `Search_Edu_Graph_Tool` is an intentional public-surface retirement, with no alias or replacement graph endpoint. Clients must stop issuing that tool call. `Search_Edu_Tool` retains its existing education-resource search contract.

Source-image CI and its deployment helper are repository-owned. IAM and shared AWS infrastructure remain infrastructure-owned. Routine deployment targets only the existing MCP service, with immutable image identity and guarded rollback; see `_docs/runbooks/deployment.md`.

## Completion Criteria

- Run `docpact route` before editing governed files.
- Run `docpact validate-config --root . --strict` after governance changes.
- Run `npm run build` for TypeScript or runtime changes.
- Run the local HTTP server command from `_docs/runbooks/development.md` or targeted client checks when HTTP transport, auth, or tool behavior changes.

- For deployment changes, run offline helper failure scenarios, actionlint, and the final ARM64 image registry check. Hosted validation and exact live image/health/auth-boundary evidence are required for runtime completion.
