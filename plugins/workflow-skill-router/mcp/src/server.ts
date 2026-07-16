import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CoreBridgeError, CoreClient } from "./core-client.js";
import { TOOL_DEFINITIONS } from "./tool-definitions.js";

const core = new CoreClient();
try { await core.start(); } catch {
  process.stderr.write("Workflow Skill Router：Python runtime 不可用，切換為 skill-only-fallback。\n");
  process.exit(78);
}
const server = new McpServer({ name: "workflow-skill-router", version: "2.0.0-alpha.1" });
for (const definition of TOOL_DEFINITIONS) {
  server.registerTool(definition.name, {
    title: definition.title,
    description: definition.description,
    inputSchema: definition.inputSchema,
    outputSchema: definition.outputSchema,
    annotations: definition.annotations,
  },
    async (arguments_: unknown) => {
      try {
        const result = await core.call(definition.name, arguments_);
        return {
          content: [{ type: "text" as const, text: JSON.stringify(result) }],
          structuredContent: result as Record<string, unknown>,
        };
      } catch (error) {
        if (error instanceof CoreBridgeError && error.code === "capability-unavailable") {
          return {
            isError: true,
            content: [{ type: "text" as const, text: JSON.stringify(error.details) }],
          };
        }
        throw error;
      }
    });
}
process.once("SIGINT", async () => { await core.close(); process.exit(0); });
process.once("SIGTERM", async () => { await core.close(); process.exit(0); });
await server.connect(new StdioServerTransport());
