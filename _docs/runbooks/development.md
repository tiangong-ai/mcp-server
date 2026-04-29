---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When developing, validating, or packaging the MCP server."
whenToUpdate: "When setup, build, local server, auth, or publishing commands change."
checkPaths:
  - README.md
  - DEV_EN.md
  - DEV_CN.md
  - package.json
  - src/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# MCP Development Runbook

## Setup

1. Use Node.js 18 or newer; repo development notes use Node.js 22.
2. Run `npm install`.
3. Create `.env` from `.env.example` and provide required Supabase, Upstash,
   region, deployment URL, and optional LangSmith values.

## Build

Run:

```bash
npm run build
```

This compiles TypeScript and marks generated server binaries executable.

## Local Server

Run:

```bash
npm run build
npx dotenv -e .env -- node dist/src/index_server.js
```

This starts `dist/src/index_server.js`. Launch the MCP Inspector separately if
interactive inspection is needed.

## Validation

Run:

```bash
npm run build
npm run lint
docpact validate-config --root . --strict
```

Use `src/test.ts`, `test.http`, or the MCP Inspector when tool schemas,
transport, auth, or response behavior changes.

## Container Notes

`Dockerfile` installs `@tiangong-ai/mcp-server@0.0.18` and runs
`tiangong-ai-mcp-http`. The image metadata exposes port `80`, while
`src/index_server.ts` defaults to `PORT=9277`; set `PORT` explicitly when the
runtime platform expects a fixed port.

## Publishing

Before NPM publishing, run:

```bash
npm run build
npm publish
```

Confirm package metadata and binary paths in `package.json` before publishing.
