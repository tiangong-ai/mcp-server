---
docType: agent-prompt
scope: repo
status: current
authoritative: true
owner: mcp
language: en
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

# MCP Update Guidelines

## Preparation
- Review existing tools in `src/_shared/init_server_http.ts` and reuse shared helpers where possible.
- Map the Supabase Edge Function that will back the MCP tool and confirm its contract before making SDK changes.
- Capture any new environment variables in `src/_shared/config.ts` and document defaults or fallback behavior.

## Implementation Principles
- Validate every tool input with `zod` and mirror the types exported through the MCP schema.
- Sanitize optional arguments via `clean_object.ts` before sending them to Supabase to avoid leaking `undefined` values.
- Ensure responses stream cleanly over the HTTP transport; prefer incremental `writer.send()` updates to large payloads.
- Keep authentication paths intact: honor bearer tokens first, fall back to the Supabase credential cache, and never log secrets.
- Model `filter` and `dateFilter` inputs with explicit field names that match the Edge Function contract (e.g., `effective_date`, `publication_date`) and serialize payload keys in the snake_case expected downstream (`meta_contains`, `datefilter`, etc.).

## Tool Registry Checklist
- Mirror every Supabase Edge Function in `src/tools` using the `sci.ts` pattern (schema, fetch wrapper, `reg*Tool` export).
- Current HTTP-backed tools and their functions:\
  `Search_Standard_Tool` → `standard_search`,\
  `Search_Textbook_Tool` → `textbook_search`,\
  `Search_Report_Tool` → `report_search`,\
  `Search_Edu_Graph_Tool` → `edu_graph_search`,\
  `Search_Green_Deal_Tool` → `green_deal_search`,\
  `Search_Internal_Tool` → `internal_search`,\
  `Search_Patent_Tool` → `patent_search`,\
  `Search_Sci_Tool` → `sci_search`,\
  `Search_ESG_Tool` → `esg_search`,\
  `Search_Edu_Tool` → `edu_search`.
- After creating or updating a tool module, register it in `src/_shared/init_server_http.ts` so the HTTP server exposes the capability.

## Quality & Verification
- Add integration coverage in `src/test.ts` or companion files so the MCP Inspector can exercise the new behavior.
- Run `npm run build` and, where possible, `npx dotenv -e .env -- node dist/src/index_server.js` with representative credentials to verify end-to-end flow.
- Execute `npm run lint` and address formatting so the distributed prompts remain clean.

## Documentation & Release
- Update `AGENTS.md` / `AGENTS_ZH.md` and agent handbooks when tool capabilities change or new parameters surface.
- Note any deployment considerations (Edge Function version bumps, Redis cache changes) in `AGENTS.md` / `AGENTS_ZH.md`.
- Before publishing, confirm the built artifact in `dist/src/index_server.js` exposes the new tool via the CLI binary.
