import { mkdir, realpath } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export function defaultDataDir(platform: NodeJS.Platform, env: NodeJS.ProcessEnv, home: string): string {
  const paths = platform === "win32" ? path.win32 : path.posix;
  if (env.WORKFLOW_SKILL_ROUTER_DATA_DIR) return paths.resolve(env.WORKFLOW_SKILL_ROUTER_DATA_DIR);
  if (platform === "win32") return paths.join(env.LOCALAPPDATA ?? paths.join(home, "AppData", "Local"), "Codex", "workflow-skill-router");
  if (platform === "darwin") return paths.join(home, "Library", "Application Support", "Codex", "workflow-skill-router");
  return paths.join(env.XDG_STATE_HOME ?? paths.join(home, ".local", "state"), "codex", "workflow-skill-router");
}

export async function resolveState(platform: NodeJS.Platform, pluginRoot: string, env = process.env, home = os.homedir()) {
  const directory = defaultDataDir(platform, env, home);
  const relative = path.relative(path.resolve(pluginRoot), path.resolve(directory));
  if (!relative.startsWith("..") && !path.isAbsolute(relative)) throw new Error("state-path-inside-plugin");
  await mkdir(directory, { recursive: true });
  return { directory, database: path.join(directory, "router-v2.sqlite3") };
}
