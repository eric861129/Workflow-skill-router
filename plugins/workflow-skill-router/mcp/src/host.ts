// 與 Python core 的 workflow_skill_router.hosts 保持同一組 Host ID；由執行環境設定，不接受模型輸入。
export const HOST_ENVIRONMENT_VARIABLE = "WORKFLOW_SKILL_ROUTER_HOST";
export const HOST_IDS = ["codex", "claude-code"] as const;
export type HostId = typeof HOST_IDS[number];

export class HostConfigurationError extends Error {
  constructor(readonly value: string) {
    super("host-unsupported");
    this.name = "HostConfigurationError";
  }
}

export function resolveHost(env: NodeJS.ProcessEnv = process.env): HostId {
  const raw = (env[HOST_ENVIRONMENT_VARIABLE] ?? "").trim();
  if (!raw) return "codex";
  if ((HOST_IDS as readonly string[]).includes(raw)) return raw as HostId;
  throw new HostConfigurationError(raw);
}
