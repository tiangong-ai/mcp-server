---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: zh-CN
whenToUse: 'When setting up, developing, testing, publishing, or deploying the MCP server with Chinese-language guidance.'
whenToUpdate: 'When setup, build, local server, publishing, or Docker deployment commands change.'
checkPaths:
  - README.md
  - README_CN.md
  - DEV_EN.md
  - package.json
  - Dockerfile
  - .env.example
  - src/**
lastReviewedAt: 2026-10-12
lastReviewedCommit: aabaceef96a38b0d23394e2da771b4fc2a213be0
---

# TianGong-AI-MCP

[中文](https://github.com/tiangong-ai/mcp-server/blob/main/DEV_CN.md) | [English](https://github.com/tiangong-ai/mcp-server/blob/main/DEV_EN.md)

## 环境设置

```bash
# 安装 Node.js
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
nvm install 22
nvm use

# 安装依赖
npm install
```

## 代码格式化

```bash
# 使用代码检查工具格式化代码
npm run lint
```

## 本地测试

### HTTP 服务器

```bash
npm run build
npx dotenv -e .env -- node dist/src/index_server.js
```

### 启动 MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

## NPM发布

```bash
npm login

npm run build && npm publish
```

## Dcoker发布

GitHub CI 的源码构建、OIDC 身份、ECS 部署与回滚流程见 [源码镜像部署手册](_docs/runbooks/deployment.md)。Docker 直接构建当前源码，无需先发布 npm 包，镜像默认监听 80 端口。
