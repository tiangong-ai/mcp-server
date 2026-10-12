import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { regEduTool } from '../tools/edu.js';
import { regESGTool } from '../tools/esg.js';
import { regGreenDealTool } from '../tools/green_deal.js';
import { regInternalTool } from '../tools/internal.js';
import { regPatentTool } from '../tools/patent.js';
import { regReportTool } from '../tools/report.js';
import { regSciTool } from '../tools/sci.js';
import { regStandardTool } from '../tools/standard.js';
import { regTextbookTool } from '../tools/textbook.js';

export function initializeServer(bearerKey?: string): McpServer {
  const server = new McpServer({
    name: 'TianGong-AI-MCP-Server',
    version: '1.0.0',
  });

  regEduTool(server, bearerKey);
  regESGTool(server, bearerKey);
  regGreenDealTool(server, bearerKey);
  regInternalTool(server, bearerKey);
  regPatentTool(server, bearerKey);
  regReportTool(server, bearerKey);
  regSciTool(server, bearerKey);
  regStandardTool(server, bearerKey);
  regTextbookTool(server, bearerKey);

  return server;
}

export function getServer(bearerKey?: string) {
  return initializeServer(bearerKey);
}
