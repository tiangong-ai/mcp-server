---
docType: guide
scope: repo
status: current
authoritative: true
owner: mcp
language: zh-CN
whenToUse: "When installing, configuring, running, or integrating the TianGong AI MCP server with Chinese-language guidance."
whenToUpdate: "When tool behavior, auth, environment variables, package metadata, build commands, or server startup changes."
checkPaths:
  - AGENTS.md
  - AGENTS_ZH.md
  - .docpact/config.yaml
  - package.json
  - Dockerfile
  - .env.example
  - mcp_config.json
  - test.http
  - .github/prompts/**
  - README.md
  - DEV_EN.md
  - DEV_CN.md
  - src/**
lastReviewedAt: 2026-09-14
lastReviewedCommit: ea3c83bab1cb6590b0d94e8ae0372e9cf9c1b746
---

# TianGong-AI-MCP

<!-- tiangong-ai-migration-20260914:start -->

## GitHub organization migration / GitHub 组织迁移

This original repository now belongs to the [tiangong-ai organization](https://github.com/tiangong-ai), with its repository identity and history retained. The CLI package `@tiangong-ai/cli` and command `tiangong-ai` are unchanged. Wiki is now published as `@tiangong-ai/wiki`; its commands remain unchanged. See the [migration and upgrade notes](https://github.com/tiangong-ai/cli-toolkit/releases/tag/v0.0.63).

该仓库已迁入 [tiangong-ai 组织](https://github.com/tiangong-ai)，仓库身份与历史保留。CLI 包名 `@tiangong-ai/cli` 和命令 `tiangong-ai` 不变；Wiki 新包名为 `@tiangong-ai/wiki`，命令不变。升级方式见[迁移说明](https://github.com/tiangong-ai/cli-toolkit/releases/tag/v0.0.63)。原个人账号 `tiangong-ai-legacy` 保留历史；请自行 Follow 新组织。

<!-- tiangong-ai-migration-20260914:end -->

[中文](https://github.com/tiangong-ai/mcp-server/blob/main/README_CN.md) | [English](https://github.com/tiangong-ai/mcp-server/blob/main/README.md)

TianGong AI Model Context Protocol (MCP) Server 支持 Streamable Http 协议。

## 启动 MCP 服务器

### Streamable Http 服务器

```bash
npm install -g @tiangong-ai/mcp-server@latest

npx dotenv -e .env -- \
npx -p @tiangong-ai/mcp-server tiangong-ai-mcp-http
```

### 本地开发服务器

在仓库本地开发时，可通过以下命令构建并启动 HTTP 服务器：

```bash
npm run build
npx dotenv -e .env -- node dist/src/index_server.js
```

如需交互式检查 MCP 能力，请单独启动 Inspector。

### 启动 MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```
