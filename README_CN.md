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
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# TianGong-AI-MCP

[中文](https://github.com/linancn/tiangong-ai-mcp/blob/main/README_CN.md) | [English](https://github.com/linancn/tiangong-ai-mcp/blob/main/README.md)

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
