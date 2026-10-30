import { HostConfigurationError } from "./host.js";
import { PythonDiscoveryError } from "./python-discovery.js";

export const PYTHON_STARTUP_FAILURE = "Workflow Skill Router：Python runtime 不可用；MCP server 無法啟動。請改用獨立安裝的 Skill-only 模式。\n";
export const HOST_STARTUP_FAILURE = "Workflow Skill Router：WORKFLOW_SKILL_ROUTER_HOST 不受支援；MCP server 無法啟動。請設定為 codex 或 claude-code，或移除這個變數。\n";
export const GENERIC_STARTUP_FAILURE = "Workflow Skill Router：MCP 啟動失敗。請確認本機狀態目錄、檔案系統權限與 Plugin 安裝設定後再試。\n";

export function startupFailureMessage(error: unknown) {
  if (error instanceof HostConfigurationError) return HOST_STARTUP_FAILURE;
  return error instanceof PythonDiscoveryError ? PYTHON_STARTUP_FAILURE : GENERIC_STARTUP_FAILURE;
}
