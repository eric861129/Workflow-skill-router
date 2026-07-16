import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const tests = process.argv.includes("--tests");
const outputIndex = process.argv.indexOf("--output");
const explicitOutput = outputIndex === -1 ? null : process.argv[outputIndex + 1];
if (outputIndex !== -1 && !explicitOutput) throw new Error("--output requires a path");
if (tests && explicitOutput) throw new Error("--output cannot be combined with --tests");
const entries = tests
  ? ["bundled-runtime", "python-discovery", "state-path", "tool-surface"].map((name) => ({ in: path.join(root, "mcp", "test", `${name}.test.ts`), out: path.join(root, ".test-build", `${name}.test.mjs`) }))
  : [{ in: path.join(root, "mcp", "src", "server.ts"), out: explicitOutput ? path.resolve(explicitOutput) : path.join(root, "mcp", "server.bundle.mjs") }];
for (const entry of entries) {
  fs.mkdirSync(path.dirname(entry.out), { recursive: true });
  await build({ entryPoints: [entry.in], outfile: entry.out, platform: "node", format: "esm", target: "node24", bundle: true, sourcemap: false, logLevel: "warning" });
}
