import assert from "node:assert/strict";
import test from "node:test";
import { z } from "zod";
import { PUBLIC_TOOL_NAMES } from "../src/tool-definitions.js";
import { TOOL_INPUT_SHAPES } from "../src/tool-schemas.js";

test("只公開核准的十個工具", () => {
  assert.equal(PUBLIC_TOOL_NAMES.length, 10); assert.equal(new Set(PUBLIC_TOOL_NAMES).size, 10);
});

test("十個工具都拒絕空值與未知欄位", () => {
  for (const name of PUBLIC_TOOL_NAMES) {
    assert.equal(z.object(TOOL_INPUT_SHAPES[name]).strict().safeParse({ unknown: true }).success, false, name);
  }
});
