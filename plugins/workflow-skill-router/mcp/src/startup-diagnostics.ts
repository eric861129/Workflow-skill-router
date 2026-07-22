import { PythonDiscoveryError } from "./python-discovery.js";

export const PYTHON_STARTUP_FAILURE = "Workflow Skill Router：Python runtime 不可用；MCP server 無法啟動。請改用獨立安裝的 Skill-only 模式。\n";
export const GENERIC_STARTUP_FAILURE = "Workflow Skill Router：MCP 啟動失敗。請確認本機狀態目錄、檔案系統權限與 Plugin 安裝設定後再試。\n";

export function startupFailureMessage(error: unknown) {
  return error instanceof PythonDiscoveryError ? PYTHON_STARTUP_FAILURE : GENERIC_STARTUP_FAILURE;
}
