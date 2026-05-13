/// <reference types="node" />

import { readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function collectTmpFiles(dir: string): string[] {
  const matches: string[] = [];

  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      matches.push(...collectTmpFiles(fullPath));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith(".tmp")) {
      matches.push(fullPath);
    }
  }

  return matches;
}

describe("source tree hygiene", () => {
  it("does not allow tmp artifacts under app/src", () => {
    const srcRoot = join(process.cwd(), "src");
    expect(collectTmpFiles(srcRoot)).toEqual([]);
  });
});
