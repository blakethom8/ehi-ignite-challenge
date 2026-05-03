import Fastify from "fastify";
import { runInvoke } from "./invoke.js";
import type { InvokeErrorBody, InvokeRequest } from "./types.js";

const PORT = Number(process.env.CURSOR_SIDECAR_PORT || "3040");

const app = Fastify({ logger: true });

app.get("/health", async () => ({ ok: true, service: "ehi-cursor-sidecar" }));

app.post<{ Body: InvokeRequest }>("/invoke", async (request, reply) => {
  const body = request.body;
  if (!body?.patient_id || !String(body.patient_id).trim()) {
    return reply.code(400).send({
      code: "bad_request",
      message: "patient_id is required",
    } satisfies InvokeErrorBody);
  }
  if (!body.question || !String(body.question).trim()) {
    return reply.code(400).send({
      code: "bad_request",
      message: "question is required",
    } satisfies InvokeErrorBody);
  }
  try {
    const result = await runInvoke({
      patient_id: String(body.patient_id).trim(),
      question: String(body.question).trim(),
      stance: String(body.stance || "opinionated"),
      history: body.history ?? undefined,
      baseline_evidence: body.baseline_evidence,
      model: body.model,
    });
    return result;
  } catch (e: unknown) {
    const x = e as { httpStatus?: number; body?: InvokeErrorBody; message?: string };
    if (x.httpStatus && x.body) {
      return reply.code(x.httpStatus).send(x.body);
    }
    request.log.error(e);
    return reply.code(500).send({
      code: "execution",
      message: x.message || "internal error",
    } satisfies InvokeErrorBody);
  }
});

async function main() {
  await app.listen({ port: PORT, host: "0.0.0.0" });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
