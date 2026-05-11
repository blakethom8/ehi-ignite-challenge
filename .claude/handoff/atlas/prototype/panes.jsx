// Preview / Files / Inspector panes
const { useState: uS, useEffect: uE, useRef: uR } = React;

/* ============== PREVIEW PANE ============== */
function PreviewPane({ tabs, activeTabId, onSelectTab, onCloseTab, workspace, onCitationClick, activeCitation }) {
  const tab = tabs.find(t => t.id === activeTabId);
  return (
    <section className="preview-pane">
      <div className="preview-head">
        <span className="ph-label">WORKBENCH</span>
        <div className="ph-spacer"></div>
        <button className="ph-btn" title="Split view"><Icon name="Columns" size={13}/></button>
        <button className="ph-btn" title="Diff"><Icon name="GitCompare" size={13}/></button>
        <button className="ph-btn" title="Export"><Icon name="Download" size={13}/></button>
        <button className="ph-btn" title="More"><Icon name="MoreH" size={13}/></button>
      </div>

      <div className="tabs-strip">
        {tabs.map(t => (
          <div key={t.id} className={"tab " + (t.id === activeTabId ? "active" : "")}
            onClick={() => onSelectTab(t.id)}>
            <span className="tab-icon"><Icon name={t.icon} size={12}/></span>
            <span>{t.label}</span>
            {t.dirty && <span className="tab-dirty"></span>}
            <button className="tab-close" onClick={(e) => { e.stopPropagation(); onCloseTab(t.id); }}>
              <Icon name="X" size={9}/>
            </button>
          </div>
        ))}
        <div className="tabs-trailing">
          <button className="tb-btn"><Icon name="Plus" size={13}/></button>
        </div>
      </div>

      <div className="preview-body fade-in" key={activeTabId}>
        {renderTab(tab, workspace, onCitationClick, activeCitation)}
      </div>

      <div className="status-strip">
        <span className="item state-running"><span className="session-state-dot state-running"></span>run/preop-2 · running</span>
        <span className="item"><Icon name="Sparkles" size={10}/>clinical-high · ctx 41k</span>
        <span className="item"><Icon name="Shield" size={10}/>{workspace.boundary.split(" ")[0]}</span>
        <span className="spacer"></span>
        <span className="item">{tab ? tab.id : ""}</span>
        <span className="item">ln 1, col 1</span>
        <span className="item">UTF-8</span>
      </div>
    </section>
  );
}

function renderTab(tab, workspace, onCitationClick, activeCitation) {
  if (!tab) return <div className="preview-doc"><p style={{color:"var(--ink-4)"}}>No tab open.</p></div>;
  switch (tab.kind) {
    case "preop-brief": return <PreopBrief onCitationClick={onCitationClick} activeCitation={activeCitation}/>;
    case "anticoag-note": return <AnticoagNote onCitationClick={onCitationClick}/>;
    case "summary-json": return <SummaryJson/>;
    case "diff": return <DiffView/>;
    case "trial-board": return <TrialBoard/>;
    case "packet-outline": return <PacketOutline/>;
    case "manifest-json": return <ManifestJson/>;
    default: return <div className="preview-doc"><p>Empty</p></div>;
  }
}

/* ---- App / artifact bodies ---- */
function PreopBrief({ onCitationClick, activeCitation }) {
  const cite = (id) => (
    <span className={"citation-chip " + (activeCitation === id ? "active" : "")}
      onClick={() => onCitationClick(id)}>
      <Icon name="Quote" size={9}/>{id}
    </span>
  );
  return (
    <div className="preview-doc">
      <h1>Pre-op clearance briefing</h1>
      <div className="doc-sub">artifact:pre-op-packet-v2.md · 2025-05-08 · draft · curated by Pre-op agent</div>

      <div className="disposition-banner">
        <div className="db-icon"><Icon name="AlertTriangle" size={20}/></div>
        <div>
          <span className="db-flag">REVIEW · ANTICOAGULATION</span>
          <div className="db-text">Surgery is operable pending confirmation of apixaban hold interval and a refreshed INR.</div>
        </div>
        <button className="db-action">Approve hold</button>
      </div>

      <div className="fact-rail">
        <div className="fr-cell"><div className="fr-label">Patient</div><div className="fr-value" style={{fontFamily:"var(--font-sans)"}}>{PATIENT.name}</div></div>
        <div className="fr-cell"><div className="fr-label">Age · Sex</div><div className="fr-value">{PATIENT.ageSex}</div></div>
        <div className="fr-cell"><div className="fr-label">Complexity</div><div className="fr-value fr-tier"><span className="tier-pill">Tier C</span></div></div>
        <div className="fr-cell"><div className="fr-label">FHIR resources</div><div className="fr-value">1,184</div></div>
        <div className="fr-cell"><div className="fr-label">OR date</div><div className="fr-value">2025-05-12</div></div>
      </div>

      <p className="lede">
        The patient is a 68-year-old female scheduled for an open inguinal hernia repair on 2025-05-12.
        Chronic atrial fibrillation is managed on apixaban {cite("c_1042")}. Hematologic baseline {cite("c_1078")} is acceptable;
        INR repeat is pending {cite("c_1091")}.
      </p>

      <h2>Critical medications</h2>
      <table className="dense-table">
        <thead><tr><th>Drug</th><th>Dose · since</th><th>Hold rule</th><th>Source</th></tr></thead>
        <tbody>
          <tr><td className="col-name">Apixaban</td><td className="mono">5 mg BID · 2023-06-14</td><td className="risk-high">Hold ≥ 48 h pre-op</td><td><span className="col-source" onClick={() => onCitationClick("c_1042")}>c_1042</span></td></tr>
          <tr><td className="col-name">Metformin</td><td className="mono">1000 mg BID · 2019-11-02</td><td className="risk-mod">Hold AM of surgery</td><td className="col-source">c_1056</td></tr>
          <tr><td className="col-name">Lisinopril</td><td className="mono">10 mg QD · 2018-03-08</td><td className="risk-mod">Hold AM of surgery</td><td className="col-source">c_1061</td></tr>
          <tr><td className="col-name">Atorvastatin</td><td className="mono">40 mg QHS · 2017-09-14</td><td className="risk-low">Continue</td><td className="col-source">c_1068</td></tr>
        </tbody>
      </table>

      <h2>Recent labs</h2>
      <table className="dense-table">
        <thead><tr><th>Test</th><th>Value</th><th>Date</th><th>Flag</th><th>Source</th></tr></thead>
        <tbody>
          <tr><td className="col-name">Hgb</td><td className="mono">12.4 g/dL</td><td className="mono">2025-04-22</td><td className="risk-low">In range</td><td><span className="col-source" onClick={() => onCitationClick("c_1078")}>c_1078</span></td></tr>
          <tr><td className="col-name">Platelets</td><td className="mono">218 × 10⁹/L</td><td className="mono">2025-04-22</td><td className="risk-low">In range</td><td className="col-source">c_1078</td></tr>
          <tr><td className="col-name">INR</td><td className="mono">—</td><td className="mono">pending</td><td className="risk-mod">Order placed</td><td><span className="col-source" onClick={() => onCitationClick("c_1091")}>c_1091</span></td></tr>
          <tr><td className="col-name">eGFR</td><td className="mono">62 mL/min/1.73 m²</td><td className="mono">2025-04-22</td><td className="risk-mod">Mild reduction</td><td className="col-source">c_1080</td></tr>
        </tbody>
      </table>

      <h2>Active comorbidities</h2>
      <table className="dense-table">
        <thead><tr><th>Condition</th><th>Onset</th><th>Risk band</th><th>Source</th></tr></thead>
        <tbody>
          <tr><td className="col-name">Atrial fibrillation (paroxysmal)</td><td className="mono">2023-05</td><td className="risk-high">Surgical bleed</td><td className="col-source">c_1041</td></tr>
          <tr><td className="col-name">Type 2 diabetes mellitus</td><td className="mono">2019-11</td><td className="risk-mod">Glycemic</td><td className="col-source">c_1055</td></tr>
          <tr><td className="col-name">HTN, controlled</td><td className="mono">2018-03</td><td className="risk-low">Baseline</td><td className="col-source">c_1060</td></tr>
        </tbody>
      </table>

      <h2>Anesthesia handoff</h2>
      <p>No documented airway complication on prior anesthesia notes {cite("c_1094")}. Anesthesia consult cleared 2025-04-18, contingent on the hematologic recheck.</p>

      <h3>Next action</h3>
      <p><strong>Pause for clinician approval</strong> on the apixaban hold interval. The packet will not export until the approval card in chat is acknowledged.</p>
    </div>
  );
}

function AnticoagNote({ onCitationClick }) {
  return (
    <div className="preview-doc">
      <h1>Anticoagulation note</h1>
      <div className="doc-sub">context/anticoagulation-note.txt · curated 2025-05-06</div>
      <p style={{fontFamily:"var(--font-mono)", fontSize:12.5, background:"var(--surface-1)", padding:"14px 16px", borderRadius:6, border:"1px solid var(--line-1)", whiteSpace:"pre-wrap", lineHeight:1.7}}>{`Patient: M. Hollister (MRN 8.4127.881)
Indication: chronic atrial fibrillation, CHA2DS2-VASc 3
Agent: apixaban 5 mg BID since 2023-06-14
Last dose: 2025-05-07 evening

Pre-op timing (open inguinal hernia repair, CPT 49505):
  - Bleed risk:        moderate
  - Recommended hold:  >= 48 h before incision
  - Restart:           24 h after hemostasis confirmed
  - Bridge:            not indicated (CHA2DS2-VASc 3, non-MV AF)

Pending: INR recheck ordered 2025-05-06 (ServiceRequest/req-9981).
Goal: INR < 1.4 morning of surgery.`}</p>
      <h3>Sources</h3>
      <p>
        Apixaban active list <span className="citation-chip" onClick={() => onCitationClick("c_1042")}><Icon name="Quote" size={9}/>c_1042</span>{" "}
        recent CBC <span className="citation-chip" onClick={() => onCitationClick("c_1078")}><Icon name="Quote" size={9}/>c_1078</span>{" "}
        INR order <span className="citation-chip" onClick={() => onCitationClick("c_1091")}><Icon name="Quote" size={9}/>c_1091</span>
      </p>
    </div>
  );
}

function SummaryJson() {
  return (
    <div className="json-view">
      <div><span className="gutter">1</span>{"{"}</div>
      <div className="indent-1"><span className="gutter">2</span><span className="jk">"artifact"</span>: <span className="js">"clearance-summary"</span>,</div>
      <div className="indent-1"><span className="gutter">3</span><span className="jk">"version"</span>: <span className="js">"v2"</span>,</div>
      <div className="indent-1"><span className="gutter">4</span><span className="jk">"patient_ref"</span>: <span className="js">"Patient/8.4127.881"</span>,</div>
      <div className="indent-1"><span className="gutter">5</span><span className="jk">"or_date"</span>: <span className="js">"2025-05-12"</span>,</div>
      <div className="indent-1"><span className="gutter">6</span><span className="jk">"procedure"</span>: <span className="js">"CPT 49505 — inguinal hernia repair, open"</span>,</div>
      <div className="indent-1"><span className="gutter">7</span><span className="jk">"disposition"</span>: <span className="js">"REVIEW"</span>,</div>
      <div className="indent-1"><span className="gutter">8</span><span className="jk">"rationale"</span>: <span className="js">"Apixaban hold interval pending clinician approval"</span>,</div>
      <div className="indent-1"><span className="gutter">9</span><span className="jk">"holds"</span>: [</div>
      <div className="indent-2"><span className="gutter">10</span>{"{"} <span className="jk">"drug"</span>: <span className="js">"apixaban"</span>, <span className="jk">"hours"</span>: <span className="jn">48</span>, <span className="jk">"basis"</span>: <span className="js">"c_1042"</span> {"}"},</div>
      <div className="indent-2"><span className="gutter">11</span>{"{"} <span className="jk">"drug"</span>: <span className="js">"metformin"</span>, <span className="jk">"hours"</span>: <span className="jn">12</span>, <span className="jk">"basis"</span>: <span className="js">"c_1056"</span> {"}"},</div>
      <div className="indent-1"><span className="gutter">12</span>],</div>
      <div className="indent-1"><span className="gutter">13</span><span className="jk">"approval_required"</span>: <span className="jb">true</span>,</div>
      <div className="indent-1"><span className="gutter">14</span><span className="jk">"approver_role"</span>: <span className="js">"attending"</span>,</div>
      <div className="indent-1"><span className="gutter">15</span><span className="jk">"export_blocked_until"</span>: <span className="js">"approval-anticoag-1"</span>,</div>
      <div className="indent-1"><span className="gutter">16</span><span className="jk">"citations"</span>: [<span className="js">"c_1042"</span>, <span className="js">"c_1078"</span>, <span className="js">"c_1091"</span>, <span className="js">"c_1094"</span>],</div>
      <div><span className="gutter">17</span>{"}"}</div>
    </div>
  );
}

function DiffView() {
  return (
    <div className="diff-view">
      <div className="diff-hunk-head">@@ pre-op-packet · v1 → v2 · disposition block @@</div>
      <div className="diff-row del"><span className="gutter">12</span><span className="marker">-</span><span>"disposition": "CLEAR"</span></div>
      <div className="diff-row add"><span className="gutter">12</span><span className="marker">+</span><span>"disposition": "REVIEW"</span></div>
      <div className="diff-row del"><span className="gutter">13</span><span className="marker">-</span><span>"rationale": "All hold rules satisfied"</span></div>
      <div className="diff-row add"><span className="gutter">13</span><span className="marker">+</span><span>"rationale": "Apixaban hold interval pending clinician approval"</span></div>
      <div className="diff-hunk-head">@@ holds @@</div>
      <div className="diff-row"><span className="gutter">17</span><span className="marker"> </span><span>{`{ "drug": "metformin", "hours": 12, "basis": "c_1056" },`}</span></div>
      <div className="diff-row add"><span className="gutter">18</span><span className="marker">+</span><span>{`{ "drug": "apixaban",  "hours": 48, "basis": "c_1042" },`}</span></div>
      <div className="diff-row"><span className="gutter">19</span><span className="marker"> </span><span>{`{ "drug": "lisinopril","hours": 12, "basis": "c_1061" },`}</span></div>
    </div>
  );
}

function TrialBoard() {
  const trials = [
    { id: "NCT-0421187", title: "Phase III ABL-tyrosine kinase inhibitor in chronic myeloid leukemia (post-imatinib intolerance)", fit: 0.92, fitLabel: "High clinical fit", risk: "Moderate travel burden", site: "MSKCC — New York, NY", enroll: "2/40", primary: "Open packet" },
    { id: "NCT-0387714", title: "Open-label study of bcl-2 inhibitor in relapsed AML — biomarker-stratified", fit: 0.68, fitLabel: "Requires biomarker verification", risk: "Exclusion criteria uncertain", site: "Mayo Clinic — Rochester, MN", enroll: "12/30", primary: "Pause for review" },
    { id: "NCT-0294512", title: "Maintenance therapy in MDS — community oncology arm", fit: 0.41, fitLabel: "Low operational fit", risk: "Site responsiveness unknown", site: "Community Network — multi-site", enroll: "—", primary: "Keep in backlog" },
  ];
  return (
    <div className="trial-board">
      <h1>Candidate board · Hollister</h1>
      <div className="doc-sub">working/candidate-board.json · 14 candidates ranked · last refresh 2 min ago</div>
      {trials.map(t => (
        <div key={t.id} className="trial-card">
          <div>
            <div className="tc-id">trial:{t.id}</div>
            <div className="tc-title">{t.title}</div>
            <div className="tc-meta">
              <span className="item"><Icon name="MapPin" size={11}/>{t.site}</span>
              <span className="item"><Icon name="Users2" size={11}/>{t.enroll}</span>
              <span className="item"><Icon name="AlertTriangle" size={11}/>{t.risk}</span>
            </div>
          </div>
          <div style={{display:"grid", gap:8, justifyItems:"end"}}>
            <div className="tc-fit">
              <div className="fit-bar"><span style={{width: (t.fit*100)+"%"}}></span></div>
              <span className="fit-text">{Math.round(t.fit*100)}%</span>
            </div>
            <div className="tc-actions">
              <button className="tc-btn">Compare</button>
              <button className="tc-btn primary">{t.primary}</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function PacketOutline() {
  return (
    <div className="preview-doc">
      <h1>Outreach packet outline</h1>
      <div className="doc-sub">working/packet-outline.md · drafted by Trial Finder agent</div>
      <h2>1. Patient anchors (de-identified)</h2>
      <p>Age band, primary diagnosis with onset year, biomarker profile (BCR-ABL+, complete), prior lines of therapy, performance status (ECOG 1).</p>
      <h2>2. Eligibility match summary</h2>
      <p>Inclusion criteria addressed line-by-line against patient evidence. Exclusion gaps flagged with FHIR references.</p>
      <h2>3. Travel and logistics</h2>
      <p>Distance to MSKCC site is 38 mi. Caregiver support documented. No identified financial blocker.</p>
      <h2>4. Pending approvals</h2>
      <p>Outbound contact requires explicit consent for external registry communication. Approval card surfaces in chat before packet is sent.</p>
    </div>
  );
}

function ManifestJson() {
  return (
    <div className="json-view">
      <div><span className="gutter">1</span>{"{"}</div>
      <div className="indent-1"><span className="gutter">2</span><span className="jk">"package"</span>: <span className="js">"trial-finder"</span>,</div>
      <div className="indent-1"><span className="gutter">3</span><span className="jk">"version"</span>: <span className="js">"2.4.1"</span>,</div>
      <div className="indent-1"><span className="gutter">4</span><span className="jk">"boundary"</span>: <span className="js">"consented-external"</span>,</div>
      <div className="indent-1"><span className="gutter">5</span><span className="jk">"connectors"</span>: [<span className="js">"clinicaltrials.gov"</span>, <span className="js">"patient-workspace"</span>, <span className="js">"web-search"</span>],</div>
      <div className="indent-1"><span className="gutter">6</span><span className="jk">"requires_consent"</span>: <span className="jb">true</span>,</div>
      <div className="indent-1"><span className="gutter">7</span><span className="jk">"exports"</span>: [<span className="js">"markdown"</span>, <span className="js">"json"</span>, <span className="js">"shareable-bundle"</span>],</div>
      <div><span className="gutter">8</span>{"}"}</div>
    </div>
  );
}

/* ============== FILES PANE ============== */
function FilesPane({ tree, openFile, activeFileId }) {
  const [filter, setFilter] = uS("");
  const [expanded, setExpanded] = uS(() => {
    const e = {};
    tree.forEach(n => { if (n.type === "folder" && n.expanded) e[n.name] = true; });
    return e;
  });
  return (
    <div className="files-pane">
      <div className="files-head">
        <span className="fh-title">FILES</span>
        <div className="spacer"></div>
        <button className="fh-btn" title="New file"><Icon name="Plus" size={12}/></button>
        <button className="fh-btn" title="Collapse all"><Icon name="ChevronDown" size={12}/></button>
        <button className="fh-btn" title="More"><Icon name="MoreH" size={12}/></button>
      </div>
      <div className="files-filter">
        <Icon name="Search" size={11}/>
        <input placeholder="Filter…" value={filter} onChange={e => setFilter(e.target.value)}/>
      </div>
      <div className="tree">
        {tree.map((n, i) => renderTreeNode(n, i, expanded, setExpanded, openFile, activeFileId, filter))}
      </div>
    </div>
  );
}

function renderTreeNode(n, key, expanded, setExpanded, openFile, activeFileId, filter) {
  if (n.type === "group") return <div key={key} className="tree-group-label">{n.label}</div>;
  if (n.type === "folder") {
    const open = expanded[n.name];
    const rows = [
      <div key={key + "-h"} className={"tree-row folder " + (open ? "expanded" : "")}
        onClick={() => setExpanded(e => ({...e, [n.name]: !e[n.name]}))}
        style={{"--indent": "6px"}}>
        <span className="chev"><Icon name="ChevronRight" size={9}/></span>
        <span className="ti"><Icon name="Folder" size={12}/></span>
        <span className="name">{n.name}</span>
      </div>
    ];
    if (open) {
      n.children.filter(c => !filter || c.name.toLowerCase().includes(filter.toLowerCase())).forEach((c, i) => {
        rows.push(
          <div key={key + "-c" + i}
            className={"tree-row " + (c.id === activeFileId ? "active" : "")}
            onClick={() => openFile(c)}
            style={{"--indent": "26px"}}>
            <span className="chev"></span>
            <span className="ti"><Icon name={c.icon || "FileText"} size={12}/></span>
            <span className="name mono">{c.name}</span>
            {c.dirty && <span className="tab-dirty"></span>}
          </div>
        );
      });
    }
    return rows;
  }
  if (n.type === "ref") {
    return (
      <div key={key} className="tree-row" style={{"--indent": "10px"}}
        onClick={() => n.id.startsWith("c_") && openFile({ kind: "citation", id: n.id })}>
        <span className="chev"></span>
        <span className="ti"><Icon name="Hash" size={12}/></span>
        <span className="name mono" style={{color:"var(--ink-3)"}}>{n.label}</span>
      </div>
    );
  }
  return null;
}

/* ============== INSPECTOR PANE ============== */
function InspectorPane({ citationId, onClose }) {
  const [tab, setTab] = uS("evidence");
  const cite = citationId ? CITATIONS[citationId] : null;

  return (
    <div className="inspector">
      <div className="inspector-head">
        <span className="ih-title">INSPECTOR</span>
        <div className="spacer"></div>
        <div className="inspector-tabs">
          <button className={"itab " + (tab === "evidence" ? "active" : "")} onClick={() => setTab("evidence")}>Evidence</button>
          <button className={"itab " + (tab === "trace" ? "active" : "")} onClick={() => setTab("trace")}>Trace</button>
          <button className={"itab " + (tab === "context" ? "active" : "")} onClick={() => setTab("context")}>Context</button>
        </div>
      </div>
      <div className="inspector-body">
        {tab === "evidence" && (cite ? <EvidenceView cite={cite}/> : <InspectorEmpty/>)}
        {tab === "trace" && <TraceView/>}
        {tab === "context" && <ContextView/>}
      </div>
    </div>
  );
}

function InspectorEmpty() {
  return (
    <div className="inspector-empty">
      <div className="icon"><Icon name="Quote" size={18}/></div>
      <div className="title">No citation selected</div>
      <div className="body">Click a citation chip in chat or a source ID in a table to pull evidence here.</div>
    </div>
  );
}

function EvidenceView({ cite }) {
  return (
    <div className="slide-in" key={cite.id}>
      <div className="evidence-card">
        <div className="ec-head">
          <div className="ec-id">{cite.id}</div>
          <div className="ec-type">{cite.type}</div>
        </div>
        <div className="ec-body">
          <div style={{fontWeight:600, marginBottom:8, fontSize:13, color:"var(--ink-1)"}}>{cite.title}</div>
          <div>{cite.snippet}</div>
        </div>
        <dl className="ec-meta">
          <dt>FHIR ref</dt><dd>{cite.source}</dd>
          <dt>Encounter</dt><dd>{cite.encounter}</dd>
          <dt>Author</dt><dd style={{fontFamily:"var(--font-sans)", color:"var(--ink-2)"}}>{cite.author}</dd>
          <dt>Date</dt><dd>{cite.date}</dd>
        </dl>
        <div className="ec-actions">
          <button className="ec-btn"><Icon name="Eye" size={11} style={{marginRight:4, verticalAlign:"middle"}}/>Open in FHIR</button>
          <button className="ec-btn"><Icon name="Pin" size={11} style={{marginRight:4, verticalAlign:"middle"}}/>Pin to run</button>
        </div>
      </div>

      <div className="related-list">
        <div className="rl-label">Related evidence</div>
        {cite.related.map(r => (
          <div key={r.id} className="rl-item">
            <Icon name="Quote" size={11} style={{color:"var(--ink-4)"}}/>
            <span className="rl-id">{r.id}</span>
            <span className="rl-text">{r.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TraceView() {
  return (
    <div>
      <div className="rl-label" style={{fontSize:10.5, fontWeight:600, color:"var(--ink-4)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:8}}>Recent tool calls</div>
      {[
        { tool: "fhir.search", arg: "MedicationStatement?patient=8.4127.881&status=active", t: "00:24" },
        { tool: "fhir.read", arg: "Observation/obs-21477", t: "00:48" },
        { tool: "workspace.pin", arg: "citation:c_1042", t: "01:02" },
        { tool: "artifact.draft", arg: "pre-op-packet-v2.md", t: "01:18" },
        { tool: "approval.request", arg: "anticoag-hold-1", t: "01:30" },
      ].map((tt, i) => (
        <div key={i} className="tool-trace" style={{marginTop:6}}>
          <Icon name="GitBranch" size={12}/>
          <span className="tt-name">{tt.tool}</span>
          <span className="tt-arrow">→</span>
          <span className="tt-target" style={{flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{tt.arg}</span>
          <span style={{fontFamily:"var(--font-mono)", fontSize:10.5, color:"var(--ink-4)"}}>{tt.t}</span>
        </div>
      ))}
    </div>
  );
}

function ContextView() {
  return (
    <div>
      <div className="rl-label" style={{fontSize:10.5, fontWeight:600, color:"var(--ink-4)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:8}}>Pinned to this run</div>
      {[
        { type: "artifact", label: "pre-op-packet-v2.md" },
        { type: "citation", label: "c_1042 · apixaban" },
        { type: "file", label: "anticoagulation-note.txt" },
        { type: "task", label: "approval-anticoag-1" },
      ].map((p, i) => (
        <div key={i} className="rl-item" style={{marginBottom:6}}>
          <Icon name="Pin" size={11} style={{color:"var(--ink-4)"}}/>
          <span className="rl-id">{p.type}:</span>
          <span className="rl-text">{p.label}</span>
        </div>
      ))}
      <div className="rl-label" style={{marginTop:18, fontSize:10.5, fontWeight:600, color:"var(--ink-4)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:8}}>Source coverage</div>
      <div style={{display:"grid", gap:4, fontSize:11.5, fontFamily:"var(--font-mono)", color:"var(--ink-3)"}}>
        <div style={{display:"flex", justifyContent:"space-between"}}><span>MedicationStatement</span><span style={{color:"var(--ink-1)"}}>14</span></div>
        <div style={{display:"flex", justifyContent:"space-between"}}><span>Observation</span><span style={{color:"var(--ink-1)"}}>208</span></div>
        <div style={{display:"flex", justifyContent:"space-between"}}><span>Condition</span><span style={{color:"var(--ink-1)"}}>17</span></div>
        <div style={{display:"flex", justifyContent:"space-between"}}><span>Encounter</span><span style={{color:"var(--ink-1)"}}>47</span></div>
        <div style={{display:"flex", justifyContent:"space-between"}}><span>DocumentReference</span><span style={{color:"var(--ink-1)"}}>96</span></div>
      </div>
    </div>
  );
}

/* ============== PACKAGE HOME (market workspace entry view) ============== */
function PackageHome({ workspace, onStartRun, onOpenRun }) {
  const workflows = (window.WORKFLOWS && window.WORKFLOWS[workspace.id]) || [];
  const recentRuns = [
    { id: "r_4128", patient: "M. Hollister", workflow: "Shortlist trials", started: "2025-05-10 11:54", status: "running", outcome: "8 of 14 candidates ranked", anchor: "Caspian session s1" },
    { id: "r_4118", patient: "R. Aoki", workflow: "Eligibility check", started: "2025-05-09 14:20", status: "complete", outcome: "3 eligible · 2 pending consent", anchor: "Caspian session s7" },
    { id: "r_4102", patient: "D. Cabrera", workflow: "Draft outreach packet", started: "2025-05-08 09:11", status: "waiting", outcome: "Approval pending · site coordinator", anchor: "Caspian session s5" },
    { id: "r_4087", patient: "M. Hollister", workflow: "Site coordination follow-up", started: "2025-05-06 16:02", status: "complete", outcome: "Closed · site declined enrollment", anchor: "Caspian session s1" },
  ];
  const perms = [
    { icon: "Database", label: "Reads patient anchors", detail: "Read-only handle from Caspian. No PHI leaves the run.", tone: "neutral" },
    { icon: "Globe", label: "Calls external registries", detail: "ClinicalTrials.gov, NCI Trial Connect, NIH ClinicalTrials API.", tone: "neutral" },
    { icon: "Send", label: "Sends outbound packets", detail: "Gated by explicit per-run approval. De-identification preset required.", tone: "warn" },
  ];
  return (
    <div className="package-home">
      <div className="ph-scroll">
        <div className="ph-hero">
          <div className="ph-mark"><Icon name={workspace.icon} size={28}/></div>
          <div className="ph-hero-meta">
            <div className="ph-eyebrow">MARKETPLACE PACKAGE · INSTALLED</div>
            <div className="ph-title">
              {workspace.title}
              <span className="ph-version">@{workspace.version}</span>
            </div>
            <div className="ph-sub">
              by {workspace.vendor} · auto-update on · last refresh {workspace.lastRefresh}
            </div>
            <p className="ph-desc">
              Pulls a consented patient anchor from Caspian and runs a clinical-trial discovery loop against
              external registries. Produces ranked candidate boards, eligibility checks, and outreach packets —
              every outbound action gated by per-run approval in the active session thread.
            </p>
          </div>
          <div className="ph-hero-actions">
            <button className="ph-cta primary"><Icon name="Play" size={13}/>Start new run</button>
            <button className="ph-cta"><Icon name="Settings" size={12}/>Configure</button>
          </div>
        </div>

        <div className="ph-section">
          <div className="ph-section-head">
            <div className="ph-section-title">Permissions ledger</div>
            <div className="ph-section-note">What this package is allowed to do, scoped to your workspace.</div>
          </div>
          <div className="ph-perms-grid">
            {perms.map((p, i) => (
              <div key={i} className={"ph-perm " + (p.tone || "")}>
                <div className="ph-perm-icon"><Icon name={p.icon} size={14}/></div>
                <div>
                  <div className="ph-perm-label">{p.label}</div>
                  <div className="ph-perm-detail">{p.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="ph-section">
          <div className="ph-section-head">
            <div className="ph-section-title">Workflows</div>
            <div className="ph-section-note">Pick a workflow to start a new run. The run becomes a session in this workspace.</div>
          </div>
          <div className="ph-wf-grid">
            {workflows.map((w) => (
              <button key={w.id} className="ph-wf" onClick={onStartRun}>
                <div className="ph-wf-head">
                  <Icon name="Workflow" size={14}/>
                  <div className="ph-wf-title">{w.title}</div>
                </div>
                <div className="ph-wf-desc">{w.desc}</div>
                <div className="ph-wf-tags">
                  {w.tags.map((t) => <span key={t} className="ph-wf-tag">{t}</span>)}
                </div>
                <div className="ph-wf-foot">
                  <span className="ph-wf-needs">Needs: patient anchor</span>
                  <span className="ph-wf-go">Start <Icon name="ArrowRight" size={11}/></span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="ph-section">
          <div className="ph-section-head">
            <div className="ph-section-title">Recent runs</div>
            <div className="ph-section-note">Re-enter a session or audit a completed run.</div>
          </div>
          <div className="ph-runs">
            <div className="ph-runs-head">
              <div>Run</div><div>Patient</div><div>Workflow</div><div>Started</div><div>Status</div><div>Outcome</div><div></div>
            </div>
            {recentRuns.map((r) => (
              <div key={r.id} className="ph-run-row" onClick={() => onOpenRun && onOpenRun(r.id)}>
                <div className="ph-run-id">{r.id}</div>
                <div className="ph-run-patient"><Icon name="UserRound" size={11}/>{r.patient}</div>
                <div>{r.workflow}</div>
                <div className="ph-run-time">{r.started}</div>
                <div><span className={"ph-run-status " + r.status}><span className="rs-dot"></span>{r.status}</span></div>
                <div className="ph-run-outcome">{r.outcome}</div>
                <div className="ph-run-open"><Icon name="ArrowRight" size={12}/></div>
              </div>
            ))}
          </div>
        </div>

        <div className="ph-section">
          <div className="ph-section-head">
            <div className="ph-section-title">About this package</div>
          </div>
          <div className="ph-about">
            <div className="ph-about-row"><span>Vendor</span><strong>{workspace.vendor}</strong></div>
            <div className="ph-about-row"><span>Version</span><strong>@{workspace.version}</strong></div>
            <div className="ph-about-row"><span>Installed by</span><strong>R. Patel · 2025-04-02</strong></div>
            <div className="ph-about-row"><span>Update channel</span><strong>Stable · auto</strong></div>
            <div className="ph-about-row"><span>Trust posture</span><strong>Consented external · per-run approval</strong></div>
            <div className="ph-about-row"><span>Audit log</span><a href="#" onClick={(e)=>e.preventDefault()}>Open in Review →</a></div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PreviewPane, FilesPane, InspectorPane, PackageHome });
