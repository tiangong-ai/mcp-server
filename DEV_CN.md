---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: zh-CN
whenToUse: "When setting up, developing, testing, publishing, or deploying the MCP server with Chinese-language guidance."
whenToUpdate: "When setup, build, local server, publishing, or Docker deployment commands change."
checkPaths:
  - README.md
  - README_CN.md
  - DEV_EN.md
  - package.json
  - Dockerfile
  - .env.example
  - src/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# TianGong-AI-MCP

[中文](https://github.com/linancn/tiangong-ai-mcp/blob/main/DEV_CN.md) | [English](https://github.com/linancn/tiangong-ai-mcp/blob/main/DEV_EN.md)

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

```bash
docker build --no-cache -t 339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp:latest .

aws ecr get-login-password --region us-east-1  | docker login --username AWS --password-stdin 339712838008.dkr.ecr.us-east-1.amazonaws.com

docker push 339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp:latest

docker run -d -p 9277:9277 --env-file .env 339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp:latest
```

镜像元数据声明 `EXPOSE 80`，但服务默认监听 `PORT=9277`；如部署平台固定端口，请显式设置 `PORT`。
