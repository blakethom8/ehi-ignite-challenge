import { Agent, CursorAgentError } from "@cursor/sdk";
import * as fs from "node:fs";
import * as path from "node:path";
import { buildUserPrompt } from "./prompt.js";
import { buildSuccess } from "./parse.js";
import type { InvokeErrorBody, InvokeRequest, InvokeSuccess } from "./types.js";

function readAllowlist(): Set<string> | null {
  const raw = (process.env.CURSOR_SIDECAR_MODEL_ALLOWLIST || "").trim();
  if (!raw) return null;
  return new Set(
    raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );
}

export function resolveModel(requested: string | null | undefined): string {
  const fallback = (process.env.CURSOR_SIDECAR_MODEL || "composer-2").trim() || "composer-2";
  const candidate = (requested?.trim() || fallback).trim() || fallback;
  const allow = readAllowlist();
  if (allow && !allow.has(candidate)) {
    const err: InvokeErrorBody = {
      code: "bad_request",
      message: `model not allowed: ${candidate}; allowlist: ${[...allow].join(", ")}`,
    };
    throw Object.assign(new Error(err.message), { httpStatus: 400, body: err });
  }
  return candidate;
}

function ensureWorkspaceCwd(): string {
  const cwd = (process.env.CURSOR_SIDECAR_CWD || "/workspace").trim();
  fs.mkdirSync(cwd, { recursive: true });
  const marker = path.join(cwd, ".ehi-cursor-workspace");
  if (!fs.existsSync(marker)) {
    fs.writeFileSync(
      marker,
      "This directory is the Cursor local agent cwd. Chart data is supplied via the invoke payload, not from repo files.\n",
      "utf8"
    );
  }
  return cwd;
}

export async function runInvoke(req: InvokeRequest): Promise<InvokeSuccess> {
  const apiKey = (process.env.CURSOR_API_KEY || "").trim();
  if (!apiKey) {
    const body: InvokeErrorBody = {
      code: "config",
      message: "CURSOR_API_KEY is required for the sidecar",
    };
    throw Object.assign(new Error(body.message), { httpStatus: 503, body });
  }

  const modelId = resolveModel(req.model);
  const cwd = ensureWorkspaceCwd();
  const prompt = buildUserPrompt(req);

  try {
    const result = await Agent.prompt(prompt, {
      apiKey,
      model: { id: modelId },
      local: { cwd, settingSources: [] },
    });

    if (result.status === "error") {
      const body: InvokeErrorBody = {
        code: "execution",
        message: "Cursor agent run finished with error status",
      };
      throw Object.assign(new Error(body.message), { httpStatus: 502, body });
    }

    const rawText = result.result ?? "";
    const used =
      typeof result.model === "object" && result.model && "id" in result.model
        ? String((result.model as { id: string }).id)
        : modelId;

    return buildSuccess(rawText, used, result.id, result.durationMs);
  } catch (e) {
    if (e && typeof e === "object" && "httpStatus" in e) throw e;
    if (e instanceof CursorAgentError) {
      const retry = e.isRetryable ? " (retryable)" : "";
      const body: InvokeErrorBody = {
        code: "config",
        message: `${e.message}${retry}`,
      };
      throw Object.assign(new Error(body.message), { httpStatus: 503, body });
    }
    const msg = e instanceof Error ? e.message : String(e);
    const body: InvokeErrorBody = {
      code: "execution",
      message: msg || "invoke failed",
    };
    throw Object.assign(new Error(body.message), { httpStatus: 502, body });
  }
}
