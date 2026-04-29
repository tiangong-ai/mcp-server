---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: "When setting up, developing, testing, publishing, or deploying the MCP server."
whenToUpdate: "When setup, build, local server, publishing, or Docker deployment commands change."
checkPaths:
  - README.md
  - README_CN.md
  - DEV_CN.md
  - package.json
  - Dockerfile
  - .env.example
  - src/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# TianGong-AI-MCP

[中文](https://github.com/linancn/tiangong-ai-mcp/blob/main/DEV_CN.md) | [English](https://github.com/linancn/tiangong-ai-mcp/blob/main/DEV_EN.md)

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

```bash
docker build --no-cache -t 339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp:latest .

aws ecr get-login-password --region us-east-1  | docker login --username AWS --password-stdin 339712838008.dkr.ecr.us-east-1.amazonaws.com

docker push 339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp:latest

docker run -d -p 9277:9277 --env-file .env 339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp:latest
```

The container image metadata exposes port `80`, while the server defaults to
`PORT=9277`; set `PORT` explicitly if deploying behind a fixed platform port.
