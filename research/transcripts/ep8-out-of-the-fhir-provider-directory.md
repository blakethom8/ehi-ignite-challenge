# Out of the FHIR — Episode 8
## "Why Provider Data Is Still Broken (And How to Fix It)"
### Guest: Ron Urwongse (Founder, Defacto Health)

*Podcast: Out of the FHIR | Host: Gene | Published: August 1, 2025*
*Spotify: https://open.spotify.com/episode/3oCW3OxCFU4u4BqBujhO0s*
*YouTube: https://www.youtube.com/watch?v=PUQQR21gbXo*

---

## Summary

Ron Urwongse is a provider data specialist who founded Defacto Health after years working inside health plans and with payers on provider data infrastructure. This episode is a frank conversation about why provider directories have been broken for a decade — and why FHIR mandates alone won't fix them.

---

## Key Themes & Insights

### 1. Provider Directory Accuracy Is Stuck at ~50%

> "It's been about 50% accuracy... about the same over the past seven years."

The most damning finding: accuracy hasn't improved despite regulatory pressure. The reasons:
- Providers submit rosters to payers and it becomes a one-way data dump with no feedback loop
- Data is only as fresh as the last roster submission — often monthly or quarterly
- No accountability for payers to keep data accurate; they've been "let's check the box" compliant
- There have been lawsuits and regulatory enforcement, but it hasn't moved the needle
- Even best-case payers Ron has seen top out at ~70% accuracy

**Implication for Blake/Cedars:** Any payer FHIR directory you pull is roughly half accurate on things like accepting-new-patients, current location, and phone number. You need to layer in verification signals.

---

### 2. The Root Problem Is Business Logic, Not Data Formatting

> "You can't clean up provider data until you change the incentives, rebuild the system logic, and stop pretending it's just a data formatting issue."

FHIR solves the *format* problem. It doesn't solve:
- Who is responsible for updating a provider's accepting status when they close their panel?
- How do you know if a provider actually sees patients at the address listed?
- How do you reconcile conflicting data from multiple payers for the same provider?

Ron's framing: most healthcare APIs are "glorified databases" — they expose data but have no business logic about what that data means. The field needs an **operational model** rebuild, not just a data standards refresh.

---

### 3. The National Provider Directory Dream vs. Reality

CMS put out an RFI on a national provider directory. Ron's take: it won't work as a silver bullet.

- A national directory solves the aggregation problem but not the accuracy problem
- The genesis event (what triggers a data update) has to be at the source — EMRs, credentialing systems, provider self-attestation
- Epic and Humana's integration is interesting here: Humana can now pull provider data directly from Epic as the source of truth — bypassing the roster CSV problem
- **Ron's ideal:** Provider data flows from EMR → Payer automatically, event-driven, not batch roster

**Key company mentioned:** Fast Health (Jason Kulatunga + Brendan Keeler) working on appointment scheduling endpoints — a related interoperability layer that matters for provider directory completeness.

---

### 4. AI Agents Are the Real Opportunity

Ron's most forward-looking take: the fix isn't a better directory — it's an AI agent layer on top of imperfect data.

- An agent that can query multiple payer directories for the same provider and reconcile conflicts
- An agent that does "secret shopper" verification — calling offices to confirm data
- An agent that curates incoming data, flags anomalies, and requests updates from providers
- The analogy he uses: **Plaid for healthcare** — an aggregation/normalization layer that connects fragmented endpoints and makes them useful

> "You have to market to bots now. You have to make your data available not only to third-party apps but also to agents."

This is essentially what Blake's venture could be.

---

### 5. Dental and Behavioral Health Are Even Worse

- Dental plans have not been held to the same FHIR mandates
- Behavioral health providers (especially solo practitioners) have the least consistent data
- Diagnostic radiologists and anesthesiologists — providers patients don't choose — have the worst directory coverage

---

### 6. The Humana + Epic Integration Is a Signal

Humana and Epic are now directly integrated — Humana can pull clinical and provider data from Epic's FHIR APIs. This is the future:
- EHR becomes the authoritative provider data source
- Payers pull from EHRs rather than relying on rosters
- Eventually eliminates the monthly CSV batch problem

Epic is also building payer-facing APIs as part of their interoperability push.

---

### 7. Network Adequacy Is the Regulatory Lever

CMS does secret shopper audits of payer provider directories for Medicare Advantage:
- They call providers listed in the directory and verify: are you at this address? Do you accept this plan? Are you taking new patients?
- Results have been "pretty bad" — but enforcement is inconsistent
- The regulatory story: payers haven't been held accountable because CMS has been reluctant to enforce aggressively

---

## Relevant Quotes

- *"It's like going shopping — do you want to find me the right provider? I actually make an appointment with Dr. [X] and that's not the right person."*
- *"Providers are not being held accountable for their directory data. Payers are not being held accountable. And so the data just sits there."*
- *"The endpoint was always there. It was not required and it was never populated. So the fact that it is a requirement [now], that's very meaningful."*
- *"Healthcare is well ahead of regulations in some ways, and interoperability is one of them — there's amazing foresight in what CMS has done."*

---

## Companies / Projects Mentioned

| Name | What They Do |
|---|---|
| **Defacto Health** (Ron's company) | Provider data infrastructure, large provider data set, API integrations with payers |
| **Fast Health** (Jason Kulatunga + Brendan Keeler) | Appointment scheduling FHIR endpoints, interoperability |
| **Epic** | EHR — becoming a source-of-truth provider data layer via FHIR |
| **Humana** | Early mover on FHIR integrations, Epic integration, launched ~1 week before episode |
| **United Health / Optum** | Integrated with Defacto, large network data |

---

## Implications for Blake's Work

### For Cedars-Sinai BD
1. When querying payer FHIR APIs, treat data as **50% baseline accuracy** — use as a starting point, not ground truth
2. The most valuable signal isn't directory data alone — it's **cross-referencing** payer directories with Cedars' own claims data and NPI registry
3. Accepting-new-patients status is the field with the highest inaccuracy — payers often don't know panel status in real time

### For the Venture
1. The "Plaid for provider data" framing Ron uses is exactly the product vision: aggregate, normalize, enrich across payer APIs
2. AI agent verification layer (secret shopper automation) is a real product gap Ron identifies
3. First opportunity: help health systems like Cedars understand their own competitive position within payer networks

### For EHI Ignite
1. Provider directory accuracy is an active challenge the industry is trying to solve — good problem space to reference
2. The FHIR-native approach (querying payer APIs directly) is the right technical path
3. The operational layer (who updates data and when) is the unsolved problem — framing a solution here would be compelling

---

*Transcript source: YouTube auto-captions via yt-dlp*
*Research doc: ~/Repo/ehi-ignite-challenge/research/PAYER-PROVIDER-DIRECTORY-APIs.md*
