---
docType: agent-contract
scope: repo
status: current
authoritative: true
owner: mcp
language: zh-CN
whenToUse: "Before editing the MCP server repository with Chinese-language agent guidance."
whenToUpdate: "When repo entry points, workflow commands, docpact config, MCP tools, auth behavior, or deployment boundaries change."
checkPaths:
  - AGENTS.md
  - AGENTS_ZH.md
  - .docpact/config.yaml
  - .github/prompts/**
  - _docs/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# TianGong AI MCP – Agent 指南

## 项目概览
- 提供一个基于 Model Context Protocol (MCP) 的无状态服务器，通过 Streamable HTTP 传输暴露天工搜索能力。
- 入口文件为 `src/index_server.ts`：启动 Express 服务，默认监听 `9277` 端口，并在 `/mcp` 提供需要 Bearer Token 或 `x-api-key` 的接口。
- 工具在 `src/_shared/init_server_http.ts` 中注册，并通过 Supabase Edge Functions 完成实际搜索，再把结果流式返回给 MCP 客户端。

## 可用的 MCP 工具
- `Search_ESG_Tool`：检索 ESG 报告分片；支持 `metaContains`、`filter`（记录 ID、国家）及基于 `publication_date` 的 `dateFilter`，务必仅在用户明确要求收窄范围时使用可选项。
- `Search_Sci_Tool`：搜索学术出版物，可按期刊 / DOI 过滤，并支持基于 `date` 的时间区间。
- `Search_Edu_Tool`：查询环保教育资源，可选 `rec_id`、`course` 过滤。
- `Search_Edu_Graph_Tool`：遍历教育知识图谱，可配置 `root`（起点数量）与 `depth`（遍历深度）来展开相关概念。
- `Search_Report_Tool`：检索可持续发展与政策报告，可按 `rec_id`、`organization`、`title` 过滤。
- `Search_Green_Deal_Tool`：查询欧盟绿色协议资料，可选 `rec_id`、`document_id`、`issue_agency`、`tags`、`title` 等过滤条件。
- `Search_Internal_Tool`：搜索内部知识库，可按 `rec_id` 或 `title` 限定结果。
- `Search_Patent_Tool`：检索专利摘要与元数据，可按 `country`、`title` 过滤，并支持基于 `publication_date` 的 `dateFilter`。
- `Search_Standard_Tool`：访问环保 / 可持续标准，可选 `metaContains`、`filter`（记录 ID、发布机构、标准号、标题）与基于 `effective_date` 的 `dateFilter`。
- `Search_Textbook_Tool`：获取精选环保教材内容，可按 `rec_id`、`title`、`author`、`company_name`、`isbn_number` 过滤，并支持基于 `publication_date` 的时间范围。
- 所有工具都会先通过 `clean_object.ts` 清洗可选参数，再调用 Supabase Edge Functions。

## 运行时与依赖
- TypeScript 项目，推荐 Node.js ≥ 18（开发手册使用 `nvm` 安装 Node 22）。
- 核心依赖：`@modelcontextprotocol/sdk`（MCP 传输层）、`express`（HTTP 服务）、`zod`（输入校验）、`@supabase/supabase-js`（认证）、`@upstash/redis`（令牌缓存）。
- 开发工具：`typescript`、`prettier`、`dotenv-cli`、`npm-check-updates`、`@modelcontextprotocol/inspector`。

## 环境变量
需要配置下列变量（见 `src/_shared/config.ts`）；仓库提供了演示默认值，但正式环境需覆盖：

```
SUPABASE_BASE_URL
SUPABASE_PUBLISHABLE_KEY
UPSTASH_REDIS_URL
UPSTASH_REDIS_TOKEN
X_REGION
PORT
HOST
LOCAL_DEPLOYMENT_URL / REMOTE_DEPLOYMENT_URL
LOCAL_LANGSMITH_API_KEY / REMOTE_LANGSMITH_API_KEY
```

认证支持两个路径：
1. 使用 Supabase 识别的 Bearer Token（`supabase.auth.getUser` 校验）。
2. 提交 Base64 编码的 `{"email":"...","password":"..."}` JSON；通过 Supabase 校验后会把用户 ID 缓存在 Upstash Redis 中。

## 开发流程
1. `npm install`：安装依赖。
2. `npm run build`：编译 TypeScript 到 `dist/` 并调整脚本权限。
3. `npx dotenv -e .env -- node dist/src/index_server.js`：在 `npm run build` 后启动本地 HTTP MCP 服务器。
4. `npx @modelcontextprotocol/inspector`：需要交互式调试时单独启动 Inspector。
5. `npm run lint`：使用 Prettier 自动格式化 / 修复。

`src/test.ts` 给出了如何通过 Streamable HTTP 方式连接 `http://localhost:9277/mcp` 的示例客户端。

## 部署说明
- Dockerfile 会构建服务器镜像并开放 `9277` 端口；AWS ECR 发布流程参考 `DEV_CN.md`/`DEV_EN.md`。
- NPM 包提供可执行文件 `tiangong-ai-mcp-http`（`package.json` 的 `bin` 字段），指向 `dist/src/index_server.js`。
- 发布前执行 `npm run build && npm publish`，并确保已登录 NPM。

## 进一步资料
- 开发者手册：`DEV_EN.md`、`DEV_CN.md`。
- 项目 README：`README.md`、`README_CN.md`。
- MCP 协议文档：<https://modelcontextprotocol.io>
