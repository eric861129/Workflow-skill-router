import { spawn } from "node:child_process";

export type PythonCommand = Readonly<{ command: string; prefixArgs: readonly string[] }>;
export type Probe = (candidate: PythonCommand) => Promise<string>;

export function candidates(platform: NodeJS.Platform): readonly PythonCommand[] {
  return platform === "win32"
    ? [{ command: "py", prefixArgs: ["-3.11"] }, { command: "python", prefixArgs: [] }]
    : [{ command: "python3", prefixArgs: [] }, { command: "python", prefixArgs: [] }];
}

export async function defaultProbe(candidate: PythonCommand): Promise<string> {
  return await new Promise((resolve, reject) => {
    const child = spawn(candidate.command, [...candidate.prefixArgs, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
      { shell: false, stdio: ["ignore", "pipe", "ignore"] });
    let output = "";
    const timer = setTimeout(() => { child.kill(); reject(new Error("python-probe-timeout")); }, 3000);
    child.stdout.setEncoding("utf8"); child.stdout.on("data", (chunk) => { output += chunk; });
    child.once("error", reject);
    child.once("close", (code) => { clearTimeout(timer); code === 0 ? resolve(output.trim()) : reject(new Error("python-probe-failed")); });
  });
}

export async function discoverPython(platform: NodeJS.Platform, probe: Probe = defaultProbe,
  override = process.env.WORKFLOW_SKILL_ROUTER_PYTHON): Promise<PythonCommand> {
  const choices = override ? [{ command: override, prefixArgs: [] as string[] }] : candidates(platform);
  for (const choice of choices) {
    try {
      const [major, minor] = (await probe(choice)).split(".").map(Number);
      if (major > 3 || (major === 3 && minor >= 11)) return choice;
    } catch { /* 嘗試下一個明確候選。 */ }
  }
  throw new Error("python-3.11-unavailable");
}
