import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

type ClientRoot = { uri: string };

export class WorkspaceRootTrustError extends Error {
  readonly code = "workspace-root-untrusted";

  constructor() {
    super("Workspace profile access requires a matching MCP Client root or operator-configured root.");
    this.name = "WorkspaceRootTrustError";
  }
}

const canonicalExistingDirectory = (value: string): string | null => {
  try {
    const resolved = fs.realpathSync.native(path.resolve(value));
    return fs.statSync(resolved).isDirectory() ? resolved : null;
  } catch {
    return null;
  }
};

const isWithin = (candidate: string, root: string) => {
  const relative = path.relative(root, candidate);
  return relative === "" || (
    relative !== ".."
    && !relative.startsWith(`..${path.sep}`)
    && !path.isAbsolute(relative)
  );
};

export function collectTrustedWorkspaceRoots(
  clientRoots: ClientRoot[],
  configuredRoots: string[],
): string[] {
  const roots = new Set<string>();
  for (const root of clientRoots) {
    try {
      const url = new URL(root.uri);
      if (url.protocol === "file:") {
        const canonical = canonicalExistingDirectory(fileURLToPath(url));
        if (canonical !== null) roots.add(canonical);
      }
    } catch {
      // A malformed or non-file Client root grants no filesystem authority.
    }
  }
  for (const root of configuredRoots) {
    if (root.trim()) {
      const canonical = canonicalExistingDirectory(root);
      if (canonical !== null) roots.add(canonical);
    }
  }
  return [...roots].sort((left, right) => left.localeCompare(right));
}

export function bindPlanWorkWorkspaceRoot(
  arguments_: Record<string, unknown>,
  trustedRoots: string[],
): Record<string, unknown> {
  const canonicalRoots = trustedRoots
    .map(canonicalExistingDirectory)
    .filter((root): root is string => root !== null);
  const rawContext = arguments_.routing_context;
  if (rawContext === undefined) {
    if (canonicalRoots.length !== 1) return arguments_;
    return {
      ...arguments_,
      routing_context: {
        workspace_root: canonicalRoots[0],
        domains: [],
        tags: [],
        current_phase_id: null,
      },
    };
  }
  if (rawContext === null || typeof rawContext !== "object" || Array.isArray(rawContext)) {
    return arguments_;
  }
  const context = rawContext as Record<string, unknown>;
  if (context.workspace_root === null || context.workspace_root === undefined) return arguments_;
  if (typeof context.workspace_root !== "string") throw new WorkspaceRootTrustError();
  const requested = canonicalExistingDirectory(context.workspace_root);
  if (requested === null || !canonicalRoots.some((root) => isWithin(requested, root))) {
    throw new WorkspaceRootTrustError();
  }
  return {
    ...arguments_,
    routing_context: { ...context, workspace_root: requested },
  };
}
