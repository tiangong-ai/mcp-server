---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: 'When developing, validating, or packaging the MCP server.'
whenToUpdate: 'When setup, build, local server, auth, or publishing commands change.'
checkPaths:
  - README.md
  - DEV_EN.md
  - DEV_CN.md
  - package.json
  - src/**
lastReviewedAt: 2026-10-12
lastReviewedCommit: 96a1863d8504b9b15f0c2b7235ab5a63f0690846
---

# MCP Development Runbook

## Setup

1. Use Node.js 18 or newer; repo development notes use Node.js 22.
2. Run `npm install`.
3. Create `.env` from `.env.example` and provide required Supabase, Upstash, region, deployment URL, and optional LangSmith values.

## Build

Run:

```bash
npm run build
```

This clears previous build output, compiles TypeScript, and marks generated server binaries executable. Clearing `dist/` prevents a removed tool module from remaining in the published package.

## Local Server

Run:

```bash
npm run build
npx dotenv -e .env -- node dist/src/index_server.js
```

This starts `dist/src/index_server.js`. Launch the MCP Inspector separately if interactive inspection is needed.

## Validation

Run:

```bash
npm run build
npm run lint
docpact validate-config --root . --strict
```

For an offline public tool inventory check after building, run:

```bash
node dist/src/test_tool_registry.js
```

This uses an in-memory MCP client, verifies all nine active tool names and required query schemas, and rejects the retired graph tool without contacting Supabase. It does not validate authentication or backend searches.

Use `src/test.ts`, `test.http`, or the MCP Inspector when tool schemas, transport, auth, or response behavior changes.

## Container Notes

`Dockerfile` installs `@tiangong-ai/mcp-server@0.0.19` and runs `tiangong-ai-mcp-http`. The image metadata exposes port `80`, while `src/index_server.ts` defaults to `PORT=9277`; set `PORT` explicitly when the runtime platform expects a fixed port.

## Publishing

Before NPM publishing, run:

```bash
npm run build
npm publish
```

Confirm package metadata and binary paths in `package.json` before publishing.

The prepared retirement release is `0.0.19`. Publish it from the reviewed, merged source before building the pinned container; the image cannot install that version until npm publication is verified. Source merge and workspace integration alone do not update a running MCP service. Confirm the deployed image digest and tool inventory through the infrastructure owner.
