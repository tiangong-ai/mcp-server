---
docType: architecture
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: 'When changing MCP tools, auth, transport, package entry points, or deployment packaging.'
whenToUpdate: 'When server topology, tool registration, auth flow, or runtime assumptions change.'
checkPaths:
  - src/**
  - package.json
  - mcp_config.json
  - Dockerfile
lastReviewedAt: 2026-10-12
lastReviewedCommit: 3f39012edf73bc825944b15647fcce8ae6ad3cae
---

# MCP Architecture

## Overview

The repository provides a TypeScript MCP server for TianGong AI search tools. `src/index_server.ts` runs an Express server on `PORT` with a `/mcp` endpoint. Tools are registered through shared server initialization code and call Supabase Edge Functions.

## Key Paths

- `src/index_server.ts`: Streamable HTTP server entry point.
- `src/_shared/**`: config, auth, HTTP initialization, and shared helpers.
- `src/tools/**`: MCP tool definitions and tool-specific schemas.
- `src/test.ts`: reference client for local server testing.
- `mcp_config.json`: MCP client/server configuration example.
- `package.json`: package metadata, binary, scripts, and dependencies.
- `Dockerfile`: deployment packaging.

## Runtime Shape

The package is an ESM TypeScript project targeting Node.js 18 or newer. Build output lands in `dist/`, and the package exposes `tiangong-ai-mcp-http` as a binary entry.

## Integration Points

- Incoming clients use the Streamable HTTP transport.
- Auth accepts Supabase bearer tokens or cached credential verification through Upstash Redis.
- Tool calls depend on Supabase Edge Functions owned by the edge-function repository.

## Current Search Tools

`src/_shared/init_server_http.ts` registers nine tools: `Search_Edu_Tool`, `Search_ESG_Tool`, `Search_Green_Deal_Tool`, `Search_Internal_Tool`, `Search_Patent_Tool`, `Search_Report_Tool`, `Search_Sci_Tool`, `Search_Standard_Tool`, and `Search_Textbook_Tool`.

The education graph tool and its `edu_graph_search` adapter were removed after the backing education graph service was retired. No graph traversal capability is advertised.

## Source Image Delivery

GitHub Actions builds the merged source as a `linux/arm64` image, validates its offline public tool inventory, and uses production-environment OIDC to push an immutable ECR digest and roll the existing ECS service. Deployment settings, role migration, credential handling and recovery are defined in `_docs/runbooks/deployment.md`. Npm publishing is independent of this path.
