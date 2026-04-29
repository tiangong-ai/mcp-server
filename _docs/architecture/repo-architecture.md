---
docType: architecture
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When changing MCP tools, auth, transport, package entry points, or deployment packaging."
whenToUpdate: "When server topology, tool registration, auth flow, or runtime assumptions change."
checkPaths:
  - src/**
  - package.json
  - mcp_config.json
  - Dockerfile
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# MCP Architecture

## Overview

The repository provides a TypeScript MCP server for TianGong AI search tools.
`src/index_server.ts` runs an Express server on `PORT` with a `/mcp` endpoint.
Tools are registered through shared server initialization code and call
Supabase Edge Functions.

## Key Paths

- `src/index_server.ts`: Streamable HTTP server entry point.
- `src/_shared/**`: config, auth, HTTP initialization, and shared helpers.
- `src/tools/**`: MCP tool definitions and tool-specific schemas.
- `src/test.ts`: reference client for local server testing.
- `mcp_config.json`: MCP client/server configuration example.
- `package.json`: package metadata, binary, scripts, and dependencies.
- `Dockerfile`: deployment packaging.

## Runtime Shape

The package is an ESM TypeScript project targeting Node.js 18 or newer. Build
output lands in `dist/`, and the package exposes `tiangong-ai-mcp-http` as a
binary entry.

## Integration Points

- Incoming clients use the Streamable HTTP transport.
- Auth accepts Supabase bearer tokens or cached credential verification through
  Upstash Redis.
- Tool calls depend on Supabase Edge Functions owned by the edge-function
  repository.
