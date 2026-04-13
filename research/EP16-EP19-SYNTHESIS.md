# Ep 16 + Ep 19 Synthesis — Technical & Positioning Insights

*Source transcripts: `research/transcripts/out-of-the-fhir-ep16-mark-scrimshire-blue-button-bulk-fhir.txt` and `research/transcripts/out-of-the-fhir-ep19-aaron-neiderhiser-phil-ballentine.txt`*

*Complements: `ideas/PODCAST-INSIGHTS-FHIR-POSITIONING.md` (which covers Ep 18, 21, 22, 24 — market positioning).*
*This doc covers the **technical & architectural** insights from Ep 16 and 19 and maps them to our EHI Ignite submission.*

---

## Executive Summary

Two episodes, two complementary stories about making FHIR data **actually usable**:

- **Ep 19 (Aaron Niederhiser / Phil Ballentine / Gene Geller)** is a technical conversation about the analytics layer: **SQL-on-FHIR**, **CQL→SQL transpilation**, Bulk FHIR export, and the emerging pattern of LLM agents generating clinical logic on top of flattened FHIR views. This is the "how do we turn FHIR JSON into something a data team can actually query?" story.

- **Ep 16 (Mark Scrimshire, ONIX Health)** is a regulatory/historical conversation about **how FHIR data gets liberated in the first place**: Blue Button 2.0, CMS 9115, CMS-0057 prior-auth, Bulk FHIR export APIs, and the trust framework (UDAP, FAST Security IG) that's actually gating adoption. This is the "who is forced to hand over the data, and on what timeline?" story.

**Net takeaway for us:** Our project is currently positioned as a clinician-facing visualization tool on top of parsed FHIR dataclasses. Both episodes suggest we have an opportunity to **reframe and extend** the project so it's also a credible contribution to the open FHIR analytics ecosystem — specifically by adopting SQL-on-FHIR View Definitions as our data contract and expressing our clinical rules (drug safety flags, episode detection, etc.) in a way that aligns with CQL. Doing so makes the submission technically distinctive and directly maps to the two regulatory tailwinds the Ep 16 guest describes.

The rest of this doc breaks this down into: (1) what each episode said, (2) what it means for our architecture, (3) recommended positioning for the EHI Ignite submission, and (4) a concrete near-term action plan.

---

## Episode 19 — SQL-on-FHIR, CQL, and Making FHIR Data Analytics-Ready

**Participants:** Aaron Niederhiser (co-founder, Tuva Project), Phil Ballentine (data engineering lead, Atropos Health), Gene Geller (host). Recorded around the **second annual SQL-on-FHIR conference**, where Gene was giving a talk the next day on converting CQL to SQL via LLMs and running it in Databricks.

### Core thesis

> FHIR analytics has always lagged FHIR operations because FHIR is JSON, deeply nested, and designed for REST APIs — not for aggregation. SQL-on-FHIR is finally closing that gap by giving the community a **standard, portable way to flatten FHIR resources into relational tables**, and AI is making the last mile (generating clinical logic on top of those views) dramatically easier.

### Key concepts

**1. SQL-on-FHIR as a working group and a spec.**
- A small group (Arjun and colleagues) meets **weekly** to evolve the SQL-on-FHIR v2 spec.
- Sponsored by **HealthSamurai** and **Reason Health**.
- Second annual conference just ran; talks on YouTube.
- The spec centers on **View Definitions** — declarative contracts that describe how a FHIR resource is flattened into columns.

**2. View Definitions are the contract.**
- Aaron's observation: he's talked to ~10 companies in the past year that have each built their own FHIR-flattening pipeline. They are all messy, all different, and none are portable.
- The View Definition approach inverts this: rather than every org writing flatteners, you **publish a View Definition** (e.g., "US Core Patient") and anyone with a "view runner" can produce the same flat table from the same FHIR bundle.
- **HealthSamurai has a View Definition Builder** — a GUI for defining which elements of a FHIR resource you care about.
- **Aaron's concrete aspiration:** have a community-maintained set of View Definitions for every US Core profile so that new teams can just download them instead of reinventing the wheel.

**3. CQL (Clinical Quality Language) — and why it's hard.**
- CQL was designed as the standardized, portable way to express clinical logic — the obvious use case being **HEDIS quality measures**, which today are published as narrative specs that every vendor interprets slightly differently.
- CQL compiles down to **ELM** (Expression Logical Model), which is the actual executable form.
- The problem: **CQL engines are slow, niche, and not performant.** Gene's words: "If you want people to use CQL, let's do the common-sense thing, which is convert it to SQL."
- The clinical-logic-as-code problem is real regardless — everyone doing HEDIS has built their own SQL measures for years.

**4. Gene's talk thesis: use CQL as a spec, execute as SQL.**
- Rather than running CQL natively, treat it as a **standardized requirements document** for clinical logic.
- Use LLMs (with a standardized prompt + input harness) to **transpile CQL → SQL**.
- Run the generated SQL against View Definition–flattened tables in Databricks / DuckDB / Snowflake.
- Result: you get CQL's standardization benefits (portable clinical semantics, US Core alignment) and SQL's execution benefits (performance, ecosystem, any data team can read/debug it).

**5. The end-to-end pipeline of the future.**
Aaron described this as the direction everything is moving:

1. An agent writes CQL from a plain-language clinical requirement.
2. An LLM transpiles CQL → SQL.
3. SQL-on-FHIR View Definitions provide the flattened tables.
4. The generated SQL runs immediately against those views.
5. Everything is wired through **MCP endpoints** so downstream agents can use it without human in the loop.

**6. Bulk FHIR is the other half of the story.**
- Traditional FHIR servers were built for single-patient transactions (`GET Patient/123`). Running a population-scale export would crash early implementations.
- **Bulk FHIR** (`$export` operation, FHIR Group resource as a cohort roster) is the answer — ask for "all procedures for everyone in Group X" and get a bulk dump.
- **CMS BCDA** (Beneficiary Claims Data API) is the canonical example for ACOs — it's a bulk FHIR endpoint serving Medicare claims data at population scale. Tuva users use it for claims ingestion.
- Epic, Cerner/Oracle, Athena, and Meditech all technically support Bulk FHIR, but enablement quality varies wildly per health system. "Prisoners of the still."

**7. Heterogeneity is still real and R6 is trying to fix it.**
- **R4 is the Windows 95 of FHIR** — what everyone's on. **R5 got skipped.** **R6** is being finalized now.
- Graham Grieve (creator of FHIR) called the spec's flexibility "the **original sin of FHIR**" — too many things are optional, leading to profile proliferation (US Core, DaVinci, custom extensions, etc.).
- R6's pitch: **more resources will be normative, fewer trial-use elements, less experimental surface area.** The expectation is that US Core regulations will mandate R6 around 2027–2028, which will force EHR vendors to move.
- Practical implication: if you're building new tooling now, target R4 (because that's what Epic/Cerner serve today) but design your data contracts so R6 migration is a rename exercise, not a rewrite.

**8. The "Larry problem" — admin bottleneck even when tech works.**
- Even if the technical pipeline is perfect, the gating factor is usually a human approver ("Larry") with 700 tickets. Bulk FHIR enablement lives in that queue.
- Automated auth (UDAP, FAST Security IG) is the technical answer, but org-level willingness is still the real bottleneck.

**9. FHIR as common data model — yes or no?**
- Aaron's nuanced answer: **depends on your data sources.** If you're aggregating data from many external providers and 80%+ of incoming data is already FHIR, then yes — flatten and standardize with View Definitions.
- If most of your data arrives as relational CSVs over SFTP (the reality for most health plans today), converting those to FHIR just to flatten them back to SQL is silly. Stay relational.
- **The calculus flips as industry adoption of Bulk FHIR grows** — and both hosts expect that to happen over the next 2–3 years driven by CMS-0057.

**10. Tools and projects mentioned:**
| Name | What it is |
|---|---|
| **SQL-on-FHIR v2 spec** | HL7 working group spec for View Definitions and view runners |
| **HealthSamurai** | Sponsor of SQL-on-FHIR conference; View Definition Builder GUI |
| **Reason Health** | Co-sponsor of the conference |
| **Tuva Project** | Open-source healthcare analytics data model; clinical tables modeled on US Core / US CDI |
| **FHIR Inferno** | Tuva's FHIR → Tuva data model connector |
| **FlexPA / Afastin Health / Health Gorilla** | Data aggregators trying to be "the Plaid of healthcare" |
| **Databricks** | Execution engine for Gene's CQL→SQL demo |
| **CQF Ruler / cql-execution** | Existing CQL engines (the "slow and niche" ones) |
| **US Core / US CDI** | The profile/data-element set ONC mandates for interop |

---

## Episode 16 — Data Liberation via Regulation (Mark Scrimshire, ONIX Health)

**Participant:** Mark Scrimshire, Chief Interoperability Officer at ONIX Health (`onixhealth.io`). Co-chair of HL7 Financial Management. Helped define the Explanation of Benefit (EoB) resource that underpins Blue Button 2.0. Former entrepreneur-in-residence at CMS. Currently writing and implementing specs for the **CMS-0057 prior-auth rule** via the DaVinci Accelerator (Payer Data Exchange, PlanNet, formulary, attribution).

### Core thesis

> Healthcare interoperability has always been bottlenecked by data access, not data utility. Regulation (Blue Button 1/2, CMS 9115, CMS-0057) is what actually forces payers and EHRs to expose data via FHIR, and Bulk FHIR is what finally "flips the script" — letting teams spend 80% of their time on *using* the data instead of 80% of their time on *getting* it. But the real bottleneck now is trust/auth, not tech.

### Key concepts

**1. The regulatory arc.**
- **Blue Button 1.0 (2009):** Veterans Affairs + CMS let beneficiaries download a 1,700-page text file of their claims history. Not usable, but symbolic.
- **Blue Button 2.0 (2018):** Built on FHIR (initially STU3, now R4), anchored by the **Explanation of Benefit (EoB) resource** that Mark helped define. Gives 60M+ Medicare fee-for-service beneficiaries programmatic access to their claims.
- **CMS 9115 (2020):** The "interoperability and patient access" rule. Forced regulated plans to stand up patient-access FHIR APIs. This was the catalyst that made payer-side FHIR real.
- **CMS-0057 (2024, mandatory January 1, 2027):** The prior-auth rule. Providers can query payers via FHIR APIs for prior-auth status and medical guidelines. Also includes **Provider Access**, **Payer-to-Payer**, and **Patient Access** expansions — all built on DaVinci IGs.

**2. "Flip the script" — the 80/20 reversal.**
- Mark's most repeated line: without Bulk FHIR, you spend **80% on extraction and 20% on what you actually want to do**. With it, you flip to **20% on extraction, 80% on utilization**.
- This directly mirrors Aaron's complaint in Ep 19 about every org building its own FHIR-flattening pipeline. Both episodes agree: the grunt work is the real enemy.

**3. Trust framework is the real bottleneck now, not tech.**
- Technically: the IGs are written, the APIs work, the auth standards exist.
- Organizationally: if you're a third-party app developer, you'd need to bilaterally establish trust with **every payer** (~300–900 impacted) and every EHR vendor at every health system. Without automation, that's man-years of handshake.
- **The answer is UDAP (User-Directed Access Profile)**, rolled into the **FAST Security IG** as a layer on top of OAuth 2. Certificate-based identity + **automated/dynamic client registration**. Mark demoed this at FHIR DevDays back in 2018.
- Until UDAP is universally adopted, the "Larry problem" from Ep 19 persists — every connection still requires a human approval.

**4. The underrated payer value prop: "connectivity of the care journey."**
- Payers don't have deep clinical data. But they have **every claim, from every provider, across the entire patient journey**. They know every ED visit, every specialist referral, every prescription filled — even at facilities where the patient's primary EHR has no record.
- Mark's framing: payers have the **connectivity of the care journey**, even when they lack clinical depth. That longitudinal, cross-provider visibility is uniquely valuable and structurally invisible to any single provider.
- This is a major product signal that the existing positioning doc doesn't fully capture — see recommendations below.

**5. AI + standards are complementary, not substitutes.**
- Mark pushed back explicitly on the "AI can parse anything, we don't need standards" argument.
- Analogy: OCR + NLP on a PDF of what was originally structured data is monumentally wasteful. Standards make AI **cheaper, more reliable, and more deterministic** because the LLM isn't burning tokens on format reconciliation.
- Anecdote: the ICD-9 → ICD-10 NLP translation problem ultimately hit a ceiling because **human coding experts couldn't agree on canonical interpretations**. AI inherits whatever disagreement lives in the ground truth. This generalizes: AI can't bridge semantic gaps that humans haven't agreed how to bridge.

**6. The use cases Mark called out as concrete wins of this regulatory push:**
| Use case | What it unlocks |
|---|---|
| Medicare Advantage plan shopping | "Based on your claims history, this MA plan is best for you" |
| Research enrollment triggers | Claims history → auto-qualification → Apple Watch arrives |
| Real-time prior-auth approval | 15-second yes/no instead of fax loops |
| Payer-to-payer data transfer at plan switch | New plan already knows your prior-auth, care gaps, care plan |
| Patient communities | Caregivers for rare diseases often better-informed than providers |

**7. The "Walking Gallery of Healthcare" anecdote.**
- A patient-empowerment art movement where supporters wear painted jackets telling a patient's data story. Mark owns one of the first 10 jackets.
- Not directly relevant to our build, but a useful reminder that the **patient-empowerment framing** carries moral weight in the FHIR community. Judges and reviewers in the EHI Ignite space tend to resonate with it.

---

## Mapping the Insights to Our Current Project

What we already have (as of `master` at the time of writing):

| Layer | What's built | Relevance to Ep 16/19 |
|---|---|---|
| **FHIR parsing** | `fhir_explorer/parser/` — dataclasses for Patient, Encounter, Condition, Medication, Observation, Procedure, etc. | Works, but it's a **bespoke flattening layer** — exactly the kind of thing Aaron's been seeing at 10+ companies. It's correct but not portable. |
| **Drug classifier** | 12 surgical-risk classes, keyword + RxNorm matching | This is **clinical logic expressed as Python code**. It's effectively a mini CQL library, except it's not CQL. No external org can reuse our safety rules. |
| **Episode detector** | Groups medication requests into continuous episodes | Same story — valid clinical logic, locked in Python. |
| **Drug interaction checker** | 13 interaction rules with severity | Same. |
| **Patient Journey Streamlit app** | 6 views: Timeline, Safety Panel, Medication History, Drug Interactions, Conditions, Clinical Search | User-facing and concrete. This is our **demo surface**. |
| **FastAPI backend** | `api/` with routers, tracing, Anthropic Agent SDK integration | Positions us for the agentic/MCP future Aaron described, but currently serves Python dataclasses, not SQL views. |
| **React frontend** | `app/` with Explorer and Patient Journey routes | The polished demo surface for the submission. |
| **Tracing + Langfuse** | LLM observability | Nice to have — matches the "measure everything" expectation for serious LLM products. |

### What the podcasts say we're missing

**1. A portable data contract (SQL-on-FHIR View Definitions).**
Right now our parser *is* our data contract. That means:
- Every new analytic question requires Python code, not SQL.
- Cross-patient (corpus) analysis is awkward — bundles are loaded individually into memory.
- Nothing we build is a reusable artifact for the broader FHIR community.
- We can't leverage DuckDB / dbt / Databricks / any SQL tooling.

**2. Clinical logic as a shareable artifact.**
Our drug classifier + interaction rules are the cleanest possible example of clinical logic that *should* be expressed in CQL (or at least in SQL views generated from CQL). Right now:
- Nobody outside this repo can reuse our 12-class surgical risk taxonomy.
- If a clinical quality reviewer wants to audit the rules, they have to read Python.
- We can't publish the rules as a "clinical intelligence library."

**3. A Bulk FHIR ingestion path.**
We only read individual Synthea bundles today. We have no `$export` / `Group` handling. Given CMS BCDA exists and CMS-0057 is mandatory in 2027, the ability to say "our pipeline consumes Bulk FHIR from BCDA or a payer's Patient Access API" is a strong regulatory-alignment signal.

**4. MCP-first data access for agents.**
Our Anthropic Agent SDK integration is a good start, but we're not yet exposing patient data through an MCP server. Aaron's vision of "an agent asks the FHIR MCP endpoint for blood-thinner patients and gets a structured answer" is a natural fit for where our provider assistant is heading.

**5. A "connectivity of the care journey" framing.**
Our current pitch is surgeon-facing and provider-side. The Ep 16 insight — that payers see everywhere the patient has been, and CMS-0057 will make that visible to providers by 2027 — is a positioning angle we haven't fully exploited.

---

## Architectural Recommendations

These are ordered from "highest value, lowest effort" to "most ambitious."

### 1. Add a SQL-on-FHIR View Definition layer on top of the existing parser *(recommended)*

Don't throw away `fhir_explorer/parser/`. Add a new module that:
- Loads a FHIR bundle as-is.
- Runs a set of community-standard **View Definitions** (US Core Patient, Condition, MedicationRequest, Encounter, Observation, Procedure) against it.
- Writes the flattened output into **DuckDB** (zero-install, in-process, no server).
- Exposes the resulting tables to both the FastAPI backend and any ad-hoc SQL query.

**Why DuckDB specifically:** single binary, no infra, works great for single-patient and small-corpus analytics. Can scale to 100k+ patients with no code changes. Same engine the SQL-on-FHIR community uses for view runner prototypes.

**Why this is high-value:**
- **We become credible SQL-on-FHIR citizens** — our submission can cite the spec and point to our view runner.
- We can answer corpus-level questions immediately ("how many patients in the dataset have active anticoagulant + antiplatelet combos?") without loading every bundle into Python memory.
- We keep the existing parser and views working — the SQL layer is *additive*, not a rewrite.
- It unblocks a real demo of cross-patient analytics for the EHI Ignite submission.

**What this looks like in the repo:**
```
api/core/sql_on_fhir/
    view_definitions/          # .json View Definition files (US Core)
    view_runner.py             # loads bundle, applies views, writes to DuckDB
    queries/                   # named SQL queries (safety, cohort, etc.)
api/routers/corpus.py          # new endpoints backed by DuckDB
```

### 2. Express clinical rules as portable artifacts (CQL-aligned, SQL-executed) *(stretch)*

Right now `patient-journey/data/drug_classes.json` is the closest thing we have to a clinical rule spec. It's not CQL, but conceptually it's the same shape: "here's a named clinical concept (anticoagulants), here's how you recognize it (keywords + RxNorm codes), here's why it matters (surgical note)."

Two paths:

- **Minimum-effort path:** treat our `drug_classes.json` and interaction rules as **our own rule language**, document it rigorously, and show one or two examples where we demonstrate the same rule expressed in CQL as a reference. We don't need to run CQL — we just need to show our rules are *CQL-compatible by construction*.

- **Ambitious path:** actually write one or two safety rules in CQL, use an LLM (Claude) to transpile them to SQL against our View Definition tables, and run them. This is literally Gene's talk thesis, applied to our specific use case. If it works, it's a strong demo artifact for the submission.

**Either way, the positioning win is:** our clinical logic is **not a hard-coded Python wall**. It's a portable library that another team — or a future CQL-native system — could reuse.

### 3. Add a Bulk FHIR ingestion path *(stretch)*

We don't need to run a Bulk FHIR server. We just need a script that:
- Consumes a `$export` output (NDJSON files, one per resource type).
- Runs the View Definition view runner over them.
- Produces the same DuckDB tables as the single-bundle path.

This is a small amount of code but a huge positioning signal: "our pipeline can consume BCDA, any EHR with Bulk FHIR enabled, or any Tefca-style export — not just individual Synthea bundles."

For the submission, we can demonstrate this against **the existing sample bulk FHIR dataset** already sitting in `data/synthea-samples/sample-bulk-fhir-datasets-10-patients/`. That dataset exists explicitly because Bulk FHIR is the expected ingestion path for real-world pipelines.

### 4. Expose patient data via MCP *(experimental)*

Our Agent SDK work is already close to this. One more step: wrap the FastAPI endpoints (or the DuckDB tables directly) as an **MCP server** so any MCP-aware agent (including ours) can query patient data with structured tool calls.

This is where Aaron's "future of healthcare data access" quote comes in: *"everybody's going to want to interact with an AI, whether you're a developer or analyst or consumer."* Demoing an MCP-native path for a clinical agent is a differentiating artifact for the submission.

### 5. Don't rewrite the UI — reframe it *(positioning, not code)*

The current Streamlit/React patient-journey UI is fine. Don't replace it. Instead, **reframe what it is in the submission narrative:** it's not "the product," it's **the demo surface for an open clinical intelligence layer**. The product is the layer (parser + View Definitions + CQL-compatible rules + MCP access). The UI is how we prove the layer is useful to a surgeon.

This framing makes our submission much harder for judges to dismiss as "just another patient viewer."

---

## Positioning Recommendations for the EHI Ignite Challenge

The existing `ideas/PODCAST-INSIGHTS-FHIR-POSITIONING.md` already locked in a strong positioning: **doctor-first, medication-centered patient-journey intelligence, "the right 5 facts in 30 seconds."** Don't abandon that. Augment it with the technical credibility layer from Ep 19 and the regulatory-tailwind framing from Ep 16.

Three angles worth considering, in order of my recommendation:

### Angle A *(recommended)*: "Clinical intelligence layer, with a clinician demo on top"

**The story:** We built an open, portable clinical intelligence layer on top of SQL-on-FHIR View Definitions. Our drug-safety rules, episode detection, and interaction checker are expressed as reusable artifacts, not locked-in Python. The Patient Journey app is the proof — a surgeon pre-op briefing that turns a FHIR bundle into "the 5 facts that matter" in under 30 seconds.

**Why it wins:**
- Technically credible (aligns directly with where the SQL-on-FHIR community is going — judges who know FHIR will recognize this).
- Clinically credible (keeps the Max Gibber surgeon use case, which is already concrete and compelling).
- Regulatorily credible (we can cite Bulk FHIR / CMS-0057 as the realistic ingestion path).
- Doesn't require throwing away anything we've built.

**What it requires:** implementing Recommendation #1 (SQL-on-FHIR layer) and at least gesturing at #2 (CQL-compatible rule artifacts). Recommendations #3 and #4 are nice-to-have.

### Angle B: "Payer-aware surgical briefing" — the Ep 16 play

**The story:** Given the longitudinal, cross-provider data a payer sees (via CMS-0057 Provider Access APIs and Bulk FHIR), what could a surgeon know 48 hours before a case that they currently can't? Our app is that briefing — the first tool designed to consume payer-source longitudinal data and render it as a clinician-ready safety brief.

**Why it's interesting:**
- Rides the CMS-0057 tailwind directly (mandatory 2027 — judges will see the timing).
- Novel framing — most surgeon-facing tools today use siloed provider EHRs, not payer-origin data.
- "Connectivity of the care journey" is a quote-worthy phrase from an HL7 co-chair.

**Why I'm not recommending it as primary:**
- Requires either access to real payer data or a convincing simulation. Synthea bundles don't naturally model the cross-provider gaps that make payer data valuable.
- Further from what we already have built, so more delivery risk in the submission window.

**When it makes sense:** as a **secondary narrative** alongside Angle A. Something like: "today the demo runs on Synthea; the pipeline is built to consume BCDA or a payer Patient Access API on day one."

### Angle C: "Agentic clinical Q&A over FHIR" — the AI-native play

**The story:** We're building the MCP-native interface to patient FHIR data. Agents (clinical assistants, research bots, care-coordination workflows) can query patient records via structured MCP tools, with tracing, cost tracking, and auditable clinical reasoning.

**Why it's not my first recommendation:**
- "AI-powered FHIR" is exactly the positioning the existing doc warned against. It's crowded and easy to dismiss.
- Our differentiation needs to be the **clinical layer** (safety flags, interaction rules, medication episodes), not just the chat-over-FHIR capability.
- This angle works as flavor, not as the headline.

**When it makes sense:** as a **tertiary element** inside Angle A. The MCP server + Agent SDK integration is a proof point *that the layer is accessible to AI systems*, not the product itself.

### Net recommendation

**Lead with Angle A. Include Angle B as "how this extends to payer data with CMS-0057." Include Angle C as "how agents and LLMs consume the same layer."** All three framings are compatible because they share the same underlying architecture — the SQL-on-FHIR layer with CQL-compatible clinical rules, surfaced through multiple clients.

---

## Near-Term Action Plan

Concrete steps, ordered by dependency:

### Week 1 — Prove the SQL-on-FHIR layer works
- [ ] Add `duckdb` and `sql-on-fhir` / view runner dependency to the backend.
- [ ] Add `api/core/sql_on_fhir/` module skeleton.
- [ ] Pick **3 View Definitions** to start: US Core Patient, Condition, MedicationRequest.
- [ ] Either download them from the SQL-on-FHIR repo or build them with HealthSamurai's View Definition Builder, then commit them to `api/core/sql_on_fhir/view_definitions/`.
- [ ] Write `view_runner.py` — takes a bundle path, runs views, writes to a DuckDB file.
- [ ] Write one end-to-end test that loads a Synthea bundle, runs views, queries the resulting DuckDB, and asserts row counts.

### Week 2 — Use it
- [ ] Rewrite one existing safety query (e.g., "patients on active anticoagulants") as a SQL query against the DuckDB tables. Keep the Python version alongside for comparison.
- [ ] Add an `api/routers/corpus.py` endpoint that runs population-level queries over the DuckDB.
- [ ] Add one cross-patient analytic to the Explorer UI that was impossible with the per-bundle Python path — e.g., "show the drug-class distribution across all 1,180 patients."

### Week 3 — Clinical rule artifacts
- [ ] Document our drug-class + interaction rules as a proper **rule spec** — a README in `patient-journey/data/` explaining the schema and design principles.
- [ ] Pick **one** rule (the anticoagulant-NSAID interaction is a strong candidate) and write a CQL equivalent. It doesn't need to execute — it just needs to exist as a reference artifact we can point to in the submission.
- [ ] *(Stretch)* Use Claude to transpile that CQL rule to SQL against our DuckDB tables. Compare the output to the Python version.

### Week 4 — Bulk FHIR path + submission narrative
- [ ] Add a Bulk FHIR `$export` NDJSON ingestion path. Use the existing `data/synthea-samples/sample-bulk-fhir-datasets-10-patients/` dataset to prove it.
- [ ] Write the submission narrative document. Lead with Angle A. Reference the SQL-on-FHIR community by name. Cite CMS-0057 as the regulatory path to real-world data.
- [ ] Record a short demo video.

---

## Open Questions

Things I'd want to resolve before acting on this plan:

1. **Which SQL-on-FHIR view runner to use.** HealthSamurai's implementation? Google's `sql-on-fhir` reference? A DuckDB-native one? The spec has multiple implementations and choosing wrong costs a week.
2. **How much CQL is worth writing ourselves** vs. just gesturing at compatibility. Writing one rule is cheap. Writing ten is a project. Where's the right cutoff for the submission window?
3. **Whether to demo with a real Bulk FHIR endpoint** (CMS BCDA has a sandbox — requires application) or just simulate with the local NDJSON dataset. Real BCDA is more credible but has an approval lead time.
4. **Whether to lean harder into the payer framing (Angle B).** It's novel but requires data we don't have. Is it worth building a "simulated cross-provider gap" into the Synthea fixtures?

---

## Bottom Line

**The existing product positioning is right — don't move off it.** What Ep 16 and Ep 19 add is a **technical credibility layer and a regulatory-alignment framing** that makes the same product dramatically more defensible in front of FHIR-literate judges.

The single most leveraged move is implementing a SQL-on-FHIR View Definition layer on top of our existing parser. It's additive (no rewrite), it makes us a credible citizen of the community Aaron and Gene are building, it unlocks corpus-level analytics we can't do today, and it gives us concrete artifacts (View Definitions, CQL-aligned rules, Bulk FHIR ingestion) to cite in the submission narrative. Everything else in this doc is a multiplier on that move.





