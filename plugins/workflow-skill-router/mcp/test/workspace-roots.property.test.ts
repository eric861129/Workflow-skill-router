import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";
import fc from "fast-check";
import {
  WorkspaceRootTrustError,
  bindPlanWorkWorkspaceRoot,
  collectTrustedWorkspaceRoots,
} from "../src/workspace-roots.js";

test("property: non-file Client roots never grant filesystem authority", () => {
  fc.assert(fc.property(
    fc.constantFrom("https:", "http:", "ftp:", "data:"),
    fc.string({ maxLength: 100 }),
    (protocol, payload) => {
      const uri = protocol === "data:"
        ? `${protocol}${payload}`
        : `${protocol}//example.invalid/${encodeURIComponent(payload)}`;

      assert.deepEqual(collectTrustedWorkspaceRoots([{ uri }], []), []);
    },
  ), { numRuns: 200 });
});

test("property: non-string workspace roots always fail closed", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "router-root-property-"));
  const trustedRoot = path.join(temporary, "trusted");
  fs.mkdirSync(trustedRoot);
  try {
    const trusted = collectTrustedWorkspaceRoots(
      [{ uri: pathToFileURL(trustedRoot).href }],
      [],
    );
    const nonStringWorkspaceRoot = fc.oneof(
      fc.boolean(),
      fc.integer(),
      fc.array(fc.jsonValue(), { maxLength: 4 }),
      fc.dictionary(fc.string({ maxLength: 12 }), fc.jsonValue(), { maxKeys: 4 }),
    );

    fc.assert(fc.property(nonStringWorkspaceRoot, (workspaceRoot) => {
      assert.throws(
        () => bindPlanWorkWorkspaceRoot({
          routing_context: {
            workspace_root: workspaceRoot,
            domains: [],
            tags: [],
            current_phase_id: null,
          },
        }, trusted),
        WorkspaceRootTrustError,
      );
    }), { numRuns: 200 });
  } finally {
    fs.rmdirSync(trustedRoot);
    fs.rmdirSync(temporary);
  }
});

test("property: traversal aliases cannot escape a trusted workspace root", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "router-traversal-property-"));
  const trustedRoot = path.join(temporary, "trusted");
  const outsideRoot = path.join(temporary, "outside");
  fs.mkdirSync(trustedRoot);
  fs.mkdirSync(outsideRoot);
  try {
    const trusted = collectTrustedWorkspaceRoots(
      [{ uri: pathToFileURL(trustedRoot).href }],
      [],
    );

    fc.assert(fc.property(
      fc.array(fc.constant("."), { maxLength: 12 }),
      (dotSegments) => {
        const traversalAlias = path.join(
          trustedRoot,
          "..",
          path.basename(outsideRoot),
          ...dotSegments,
        );
        assert.throws(
          () => bindPlanWorkWorkspaceRoot({
            routing_context: {
              workspace_root: traversalAlias,
              domains: [],
              tags: [],
              current_phase_id: null,
            },
          }, trusted),
          WorkspaceRootTrustError,
        );
      },
    ), { numRuns: 200 });
  } finally {
    fs.rmdirSync(trustedRoot);
    fs.rmdirSync(outsideRoot);
    fs.rmdirSync(temporary);
  }
});
