---
docType: guide
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: 'When installing, configuring, running, or integrating the TianGong AI MCP server.'
whenToUpdate: 'When tool behavior, auth, environment variables, package metadata, build commands, or server startup changes.'
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
lastReviewedAt: 2026-10-12
lastReviewedCommit: 71e65004e5246cfcfae95f0ee5e035fdecf16ec1
---

# TianGong-AI-MCP

<!-- tiangong-ai-migration-20260914:start -->

## GitHub organization migration / GitHub 组织迁移

This original repository now belongs to the [tiangong-ai organization](https://github.com/tiangong-ai), with its repository identity and history retained. The CLI package `@tiangong-ai/cli` and command `tiangong-ai` are unchanged. Wiki is now published as `@tiangong-ai/wiki`; its commands remain unchanged. See the [migration and upgrade notes](https://github.com/tiangong-ai/cli-toolkit/releases/tag/v0.0.63).

该仓库已迁入 [tiangong-ai 组织](https://github.com/tiangong-ai)，仓库身份与历史保留。CLI 包名 `@tiangong-ai/cli` 和命令 `tiangong-ai` 不变；Wiki 新包名为 `@tiangong-ai/wiki`，命令不变。升级方式见[迁移说明](https://github.com/tiangong-ai/cli-toolkit/releases/tag/v0.0.63)。原个人账号 `tiangong-ai-legacy` 保留历史；请自行 Follow 新组织。

<!-- tiangong-ai-migration-20260914:end -->

[中文](https://github.com/tiangong-ai/mcp-server/blob/main/README_CN.md) | [English](https://github.com/tiangong-ai/mcp-server/blob/main/README.md)

TianGong AI Model Context Protocol (MCP) Server supports Streamable Http protocol.

## Education graph retirement

The education knowledge graph service has been retired. The current source-built MCP server no longer advertises `Search_Edu_Graph_Tool`; clients must remove calls to that tool. `Search_Edu_Tool` continues to search education resources and does not provide graph traversal.

Previously published npm packages are not changed retroactively; npm publication is independent of this source-image deployment.

## Service Deployment

GitHub CI builds reviewed `main` source into an ARM64 image and deploys its exact ECR digest to the existing ECS service with OIDC. See the [deployment runbook](_docs/runbooks/deployment.md) for verification and rollback.

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
