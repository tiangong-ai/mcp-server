---
docType: guide
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When installing, configuring, running, or integrating the TianGong AI MCP server."
whenToUpdate: "When tool behavior, auth, environment variables, package metadata, build commands, or server startup changes."
checkPaths:
  - AGENTS.md
  - .docpact/config.yaml
  - package.json
  - Dockerfile
  - .env.example
  - mcp_config.json
  - test.http
  - .github/prompts/**
  - README_CN.md
  - DEV_EN.md
  - DEV_CN.md
  - src/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# TianGong-AI-MCP

[中文](https://github.com/linancn/tiangong-ai-mcp/blob/main/README_CN.md) | [English](https://github.com/linancn/tiangong-ai-mcp/blob/main/README.md)

TianGong AI Model Context Protocol (MCP) Server supports Streamable Http protocol.

## Starting MCP Server

### Streamable Http Server

```bash
npm install -g @tiangong-ai/mcp-server@latest

npx dotenv -e .env -- \
npx -p @tiangong-ai/mcp-server tiangong-ai-mcp-http
```

### Local Development Server

From this repository you can build and launch the HTTP server with:

```bash
npm run build
npx dotenv -e .env -- node dist/src/index_server.js
```

Launch the Inspector separately when interactive MCP inspection is needed.

### Launch MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```
