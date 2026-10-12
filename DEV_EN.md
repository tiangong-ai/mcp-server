---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: 'When setting up, developing, testing, publishing, or deploying the MCP server.'
whenToUpdate: 'When setup, build, local server, publishing, or Docker deployment commands change.'
checkPaths:
  - README.md
  - README_CN.md
  - DEV_CN.md
  - package.json
  - Dockerfile
  - .env.example
  - src/**
lastReviewedAt: 2026-10-12
lastReviewedCommit: aabaceef96a38b0d23394e2da771b4fc2a213be0
---

# TianGong-AI-MCP

[中文](https://github.com/tiangong-ai/mcp-server/blob/main/DEV_CN.md) | [English](https://github.com/tiangong-ai/mcp-server/blob/main/DEV_EN.md)

## Environment Setup

```bash
# Install Node.js
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
nvm install 22
nvm use

# Install dependencies
npm install
```

## Code Formatting

```bash
# Format code using the linter
npm run lint
```

## Local Testing

### HTTP Server

```bash
npm run build
npx dotenv -e .env -- node dist/src/index_server.js
```

### Launch MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

## NPM Publishing

```bash
npm login

npm run build && npm publish

```

## Docker Deployment

Use [Source Image Deployment](_docs/runbooks/deployment.md) for the GitHub CI source build, OIDC credentials, ECS rollout and rollback. Npm publication is independent; Docker builds the checked-out source. The image listens on port 80.
