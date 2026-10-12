import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import assert from 'node:assert/strict';
import { initializeServer } from './_shared/init_server_http.js';

// Validate the public tool inventory without credentials or backend searches.
const expectedNames = [
  'Search_ESG_Tool',
  'Search_Edu_Tool',
  'Search_Green_Deal_Tool',
  'Search_Internal_Tool',
  'Search_Patent_Tool',
  'Search_Report_Tool',
  'Search_Sci_Tool',
  'Search_Standard_Tool',
  'Search_Textbook_Tool',
];
const server = initializeServer();
const client = new Client({ name: 'offline-tool-registry-test', version: '1.0.0' });
const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
const originalFetch = globalThis.fetch;
let backendRequests = 0;
globalThis.fetch = async () => {
  backendRequests += 1;
  throw new Error('Tool inventory checks must not call a backend');
};

try {
  await server.connect(serverTransport);
  await client.connect(clientTransport);
  const { tools } = await client.listTools();
  assert.deepEqual(tools.map((tool) => tool.name).sort(), expectedNames);
  for (const tool of tools) {
    assert.equal(tool.inputSchema.type, 'object');
    assert.ok(tool.inputSchema.required?.includes('query'));
  }
  const retiredCall = await client.callTool({
    name: 'Search_Edu_Graph_Tool',
    arguments: { query: 'retired-tool-protocol-check', root: 1, depth: 3 },
  });
  assert.equal(retiredCall.isError, true);
  assert.match(JSON.stringify(retiredCall.content), /not found/);
  assert.equal(backendRequests, 0);
  console.log('Nine search tools listed; retired graph tool rejected without backend calls.');
} finally {
  globalThis.fetch = originalFetch;
  await client.close();
  await server.close();
}
