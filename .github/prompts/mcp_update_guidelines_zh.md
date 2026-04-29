---
docType: agent-prompt
scope: repo
status: current
authoritative: true
owner: mcp
language: zh-CN
whenToUse: "When updating MCP tool registration, schemas, auth, or transport behavior."
whenToUpdate: "When tool inventory, server entry points, validation commands, or agent-facing MCP update guidance changes."
checkPaths:
  - AGENTS.md
  - AGENTS_ZH.md
  - .docpact/config.yaml
  - package.json
  - src/**
lastReviewedAt: 2026-04-29
lastReviewedCommit: 04a3868c3b259fd4fe32b35b8198e20bbf4f329c
---

# MCP 更新指引

## 准备阶段
- 复查 `src/_shared/init_server_http.ts` 中既有工具的注册方式，优先复用通用辅助函数。
- 明确对应的 Supabase Edge Function，并确认输入/输出契约后再调整 SDK 层逻辑。
- 如果引入新的环境变量，请同步更新 `src/_shared/config.ts`，并说明默认值或降级策略。

## 实现原则
- 使用 `zod` 为所有工具入参做严格校验，并保持与 MCP schema 导出的类型一致。
- 在调用 Supabase 前，通过 `clean_object.ts` 过滤掉可选参数中的 `undefined` 值，避免污染请求。
- 确保结果通过 HTTP 传输时可以流式返回；优先采用逐步 `writer.send()` 输出而非一次性大 payload。
- 保持认证流程完整：优先校验 bearer token，再回退到 Supabase 凭据缓存，严禁打印敏感信息。
- `filter` / `dateFilter` 必须使用与 Edge Function 契约完全一致的字段名称（如 `effective_date`、`publication_date`），并在请求体中沿用下游要求的 snake_case 键名（`meta_contains`、`datefilter` 等）。

## 工具注册清单
- 参考 `sci.ts` 的写法，在 `src/tools` 中为每个 Supabase Edge Function 编写 schema、请求封装与 `reg*Tool` 导出。
- 当前的 HTTP 搜索工具及其对应函数：\
  `Search_Standard_Tool` → `standard_search`、\
  `Search_Textbook_Tool` → `textbook_search`、\
  `Search_Report_Tool` → `report_search`、\
  `Search_Edu_Graph_Tool` → `edu_graph_search`、\
  `Search_Green_Deal_Tool` → `green_deal_search`、\
  `Search_Internal_Tool` → `internal_search`、\
  `Search_Patent_Tool` → `patent_search`、\
  `Search_Sci_Tool` → `sci_search`、\
  `Search_ESG_Tool` → `esg_search`、\
  `Search_Edu_Tool` → `edu_search`。
- 新增或更新工具后，务必在 `src/_shared/init_server_http.ts` 中完成注册，确保 HTTP 服务能暴露能力。

## 质量验证
- 在 `src/test.ts` 或配套测试文件中补充场景，方便 MCP Inspector 端到端验证新能力。
- 运行 `npm run build`，必要时使用有效凭据执行 `npx dotenv -e .env -- node dist/src/index_server.js` 确认整体链路。
- 执行 `npm run lint` 并处理格式问题，确保提交的提示文件保持整洁一致。

## 文档与发布
- 当工具能力或参数变化时，及时同步到 `AGENTS.md` / `AGENTS_ZH.md` 及相关手册。
- 将部署注意事项（Edge Function 版本、Redis 缓存调整等）记录在 `AGENTS.md` / `AGENTS_ZH.md`。
- 发布前确认 `dist/src/index_server.js` 中的 CLI 二进制已导出最新工具。
