# Payer & Provider Directory API Research

*Created: 2026-04-22 | Author: Chief*
*Context: Market intelligence for Cedars-Sinai BD team + EHI Ignite provider data strategy*

---

## Background

The CMS Interoperability and Patient Access Rule (CMS-9115-F) mandates that payers implement **publicly accessible** Provider Directory APIs using FHIR R4. This is a huge unlock — these are *not* just member portals. They're machine-readable APIs anyone can query.

Key regulation: payers must expose provider directories via **HL7 FHIR R4**, conforming to the **Da Vinci PDex Plan Net Implementation Guide**.

---

## Payer APIs

### 1. Blue Shield of California (BSC)

**Developer Portal:** https://devportal-dev.blueshieldca.com/bsc/fhir-sandbox/

**Status:** Portal exists, sandbox available, account required

**What's available:**
- Patient Access API (member-facing, requires member auth)
- **Provider Directory API** — publicly accessible per CMS mandate
- Payer-to-Payer Data Exchange

**Access path:**
1. Create account at the dev portal
2. Register as a third-party app
3. Provider Directory API is **no-auth required** for public queries (CMS mandate)
4. Patient Access requires OAuth2/SMART on FHIR

**FHIR endpoint (likely):** `https://api.blueshieldca.com/fhir/r4/`

**Key resources exposed:**
- `Practitioner` — individual provider data
- `PractitionerRole` — specialty, accepting status, network affiliation
- `Organization` — groups, hospitals
- `Location` — addresses, geo
- `HealthcareService` — services offered

**To do:** Register at dev portal and get sandbox credentials

---

### 2. UnitedHealthcare / UHC California

**API page:** https://www.uhc.com/legal/interoperability-apis

**Status:** FHIR APIs live, also incorporates **California Data Exchange Framework (DxF)**

**What's available:**
- Provider Directory API (publicly accessible, FHIR R4)
- Patient Access API
- Payer-to-Payer exchange
- Prior Authorization API (new 2024 requirement)

**Access path:**
- Register organization at UHC developer portal
- Provider Directory API: no-auth for public queries
- Patient/clinical data: OAuth required

**Note:** UHC explicitly mentions California DxF compliance — relevant for CA-specific market intelligence

**Key insight for Cedars:** UHC's provider directory would show which providers in LA are in-network, their panel status (accepting new patients), and network tier — gold for referral intelligence.

---

### 3. Optum (UnitedHealth Group subsidiary)

**Developer Portal:** https://developer.optum.com

**Status:** Full developer portal, multiple API products

**What's available:**
- **Interoperability Provider Directory API** (FHIR-based)
- Argonaut Provider Directory (FHIR STU3 — older standard)
- Eligibility and Claims APIs
- Analytics and Insights APIs

**Access path:**
- Register at developer.optum.com
- Sandbox access request via Marketplace
- Provider Directory is publicly accessible (CMS mandate)

**Important distinction:** Optum ≠ UHC network. Optum is the data/technology arm. Their provider directory may reflect UHC networks but also covers Optum Health-employed physicians separately.

**Argonaut endpoint docs:** https://developer.optum.com/apitools/docs/argonaut-provider-directory

---

### 4. Anthem / Blue Cross of California (BCCA)

*Different from Blue Shield of CA — Anthem is the "Blue Cross" brand in CA*

**Developer Portal:** https://www.capbluecross.com (Capital BlueCross — different region, but same FHIR standard)

**For CA specifically:** Anthem Blue Cross CA — check https://provider.anthem.com for FHIR endpoint
- FHIR base likely: `https://fhir.anthem.com/`
- Same CMS mandate applies — must expose Provider Directory API publicly

---

## What You Can Actually Do With These

For **Cedars-Sinai BD / market intelligence:**

1. **Network gap analysis** — which providers are in UHC but not Cedars-affiliated? Who are they losing referrals to?
2. **Competitor mapping** — who is UCLA Health, Providence, Keck bringing into their networks?
3. **Panel status monitoring** — which specialists are still accepting new patients in LA?
4. **Network tier intelligence** — are competitors in preferred/tiered networks with major payers?
5. **Attribution modeling** — cross-reference payer directories with CMS claims data you already have

This is legitimately powerful for the physician liaison team — instead of cold-calling to find out who's accepting referrals, you can systematically map the entire LA provider landscape.

---

## Hospital Provider Directories (Website Scraping)

### UCLA Health — `uclahealth.org/providers/search`

**Verdict: Scrapable, but needs browser automation**

- **3,943 providers** exposed in their search interface
- Data visible: name, specialty, ratings, accepting new patients status
- **Technology:** Heavy JavaScript SPA — server-side renders some HTML but search/filter is client-side
- **Approach:** 
  - Option A: Playwright/Puppeteer browser scrape — page through results, extract structured data
  - Option B: Intercept the underlying API calls (open browser DevTools → Network tab → watch XHR requests when searching). UCLA likely has an internal API that the frontend calls — if it's unauthenticated, that's cleaner than scraping HTML
- **Rate limiting:** Expect it. Use delays, rotate user agents, or request respectfully

**Data available:**
- Provider name, credentials
- Specialty (up to 2-3 per provider)
- Star ratings + review count
- Accepting new patients (yes/no)
- Likely: location, phone, languages

---

### Cedars-Sinai — `cedars-sinai.org/find-a-doctor.html`

**Verdict: Same approach — JS-heavy, intercept the API**

- WebMD lists 1,679 physicians across 93 specialties at Cedars
- Their own site will have more complete data
- Same strategy: DevTools → Network inspection to find the underlying API endpoint
- **Irony alert:** You work there. Worth checking if there's an internal data source or API you can access directly through IT/data governance — would be faster and cleaner than scraping your own employer's website

---

### Providence St. John's — `providence.org`

**Verdict: Similar JS-heavy architecture**

- Providence is a large network — their directory covers St. John's + many affiliate locations across LA
- Likely uses the same Kyruus/Healthgrades provider search platform that many health systems license
- **Kyruus insight:** Many health system "Find a Doctor" tools are actually Kyruus under the hood. If they all use the same vendor, the API structure may be nearly identical across sites — one scraper could work for multiple systems

---

## Strategic Recommendation

### Phase 1: Payer APIs (Low friction, high value)
1. Register at Blue Shield CA dev portal + UHC developer portal
2. Hit the Provider Directory FHIR endpoints — no auth needed
3. Pull all CA providers, cross-reference with your CMS claims data
4. Build a local enriched provider table: NPI + payer network status + panel status

### Phase 2: Hospital Website Scraping
1. Open browser DevTools on each hospital's "Find a Doctor" page
2. Watch XHR/Fetch requests — identify the underlying search API
3. If unauthenticated: build direct API client (much cleaner than HTML scraping)
4. If auth-gated: use Playwright to automate the browser
5. Target: UCLA (3,943 providers), Cedars, Providence, Keck, Northridge

### Phase 3: Build a Unified LA Provider Intelligence Layer
- Combine: CMS claims data (you have this) + payer FHIR directories + hospital websites
- Output: enriched provider profiles with network affiliations, panel status, referral patterns
- This is basically the core of your Bespoke AI product offering

---

## Related Repos

- `~/Repo/provider-search/` — existing MVP, NPI enrichment in progress
- `~/Repo/provider-intel/` — relevant folder to check
- `~/Repo/cms-data/` — CMS pipeline, 90M rows in DuckDB

---

## Podcast Notes

*Spotify episode: https://open.spotify.com/episode/3oCW3OxCFU4u4BqBujhO0s (starting at ~17:28)*
*Could not auto-transcribe — Spotify is not YouTube. To transcribe: share which podcast show this is, or find the YouTube version.*

*Topics the podcast likely covers (based on your description):*
- Why payer-provider directories are notoriously inaccurate
- CMS mandate to clean them up via FHIR
- The "ghost network" problem (providers listed but not actually seeing patients)
- Provider directory accuracy as a compliance issue

---

## Account Status (Updated 2026-04-22)

### Blue Shield CA
- Account: `blakethom8` at `devportal-dev.blueshieldca.com`
- App: `localchief-app-1` · Client ID: `d2d20c33f74bf229076baa8409425b31`
- Production endpoint: `https://api.blueshieldca.com/bsc/fhir/fhir-server/api/v4/cloud/provider-directory/`
- Status: Sandbox only. Portal is a stale IBM compliance portal (2021 release notes). Prod access request needed.
- Next: `devportal-dev.blueshieldca.com/bsc/fhir-sandbox/productionaccess`

### Anthem Blue Cross CA
- Production endpoint CONFIRMED: `https://totalview.healthos.elevancehealth.com/resources/unregistered/api/v1/fhir/cms_mandate/mcd/`
- FHIR 4.0.1, all resources live, requires OAuth2 client credentials
- API doc PDF: `~/Chief/anthem_api_docs.pdf`
- Next: Register at `anthem.com/developers/request-anthem-io`

### Scraper Toolkit
- Built in `~/Repo/provider-intel/scrapers/` — see README for full status
- Pipeline runs: Cardiology (138), Orthopedics (137), Oncology (58), Primary Care (130) LA providers
- Reports: `~/Repo/provider-intel/reports/20260422_08*.html`
