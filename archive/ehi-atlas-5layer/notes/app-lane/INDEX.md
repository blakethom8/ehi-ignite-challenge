# App Lane — Josh Mandel Stack

**Status:** ⏸ deferred. Data lane runs first; app lane resumes once Blake has an end-to-end mental model of the data shapes.

**Goal:** understand the React/OAuth/crypto/transport mechanics enough to (a) read Josh's code without getting lost, (b) lift the SMART client into Atlas if needed, (c) judge whether Josh's app-side patterns are worth adopting.

**Reading mindset (when activated):** the *opposite* of the data lane. Skim FHIR/TSV details, slow down on auth flows, key derivation, request lifecycle, and React state.

## Provisional session arc

| #   | Topic                                                                                            | Primary code                                                            | Status     | 1-line takeaway |
| --- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- | ---------- | --------------- |
| A01 | Anthropic Skill packaging mechanics: `SKILL.md` frontmatter, `argument-hint`, `allowed-tools`, ZIP layout | `request-my-ehi/SKILL.md` + `site/skill.zip`                            | ⏸ pending | —               |
| A02 | SMART OAuth client: PKCE, asymmetric client assertion, brand directory + tag filter              | `health-skillz/src/client/lib/smart/{oauth,client,client-assertion,launch}.ts` | ⏸ pending | —               |
| A03 | SMART client lineage diff: `health-record-mcp/clientFhirUtils.ts` (monolith) → `health-skillz/src/client/lib/smart/*` (modular) | both repos                                                              | ⏸ pending | —               |
| A04 | E2E-encrypted upload: ECDH P-256 + AES-256-GCM + 5 MB chunking + ciphertext-only relay          | `health-skillz/src/client/lib/crypto.ts` + `src/server.ts`              | ⏸ pending | —               |
| A05 | E2EE signature relay (smaller cousin of A04)                                                     | `request-my-ehi/scripts/{create-signature-session,poll-signature}.ts` + `request-my-ehi/server/src/routes/signature.ts` | ⏸ pending | —               |
| A06 | React redaction studio UI (the surface over the data model in D06)                              | `health-skillz/src/client/components/` + `pages/` redaction views       | ⏸ pending | —               |
| A07 | Skill bundler: ordered partials → `SKILL.md`; JSZip in-browser builder                          | `health-skillz/skill/build-skill.ts` + `src/client/lib/skill-builder.ts` | ⏸ pending | —               |
| A08 | MCP server architecture: stdio / SSE / IntraBrowser transports + 5 tools                        | `health-record-mcp/src/{cli,sse,oauth,tools}.ts` + `IntraBrowserTransport.ts` | ⏸ pending | —               |
| A09 | In-browser LLM agent: `@babel/standalone` live-compiles LLM-generated React                     | `my-health-data-ehi-wip/src/agent.ts` + guides                          | ⏸ pending | —               |

## When this lane reactivates

Likely triggers:
- Blake decides to lift the SMART client into Atlas → run A02 + A03 first.
- Blake wants to ship Atlas as a Claude Skill → run A01 + A07.
- Blake wants to understand the encrypted-relay trust model → run A04 + A05.

The lane does not need to be run in numeric order; it's a menu, not a sequence.
