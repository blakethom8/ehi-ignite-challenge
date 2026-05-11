// Atlas Agentic Shell — main app
const { useState: aUS, useEffect: aUE, useCallback: aUC } = React;

const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "accent": "clinical-blue",
  "density": "comfortable",
  "showStatusStrip": true
}/*EDITMODE-END*/;

const ACCENTS = {
  "clinical-blue": { action: "#1d4ed8", hover: "#1e40af", press: "#1e3a8a", tint: "#e8eefe", tint2: "#dbe5fd", line: "#b9c9f7" },
  "graphite":     { action: "#1f2937", hover: "#111827", press: "#0b1220", tint: "#eef2f6", tint2: "#dde3ea", line: "#c7cfdb" },
  "violet":       { action: "#5b3df2", hover: "#4928d2", press: "#3a1eb0", tint: "#ede9fe", tint2: "#ddd6fe", line: "#c4b5fd" },
  "teal":         { action: "#0d9488", hover: "#0f766e", press: "#115e59", tint: "#e6f5f3", tint2: "#ccebe7", line: "#99d6cf" },
};

const INITIAL_CHAT = {
  "clinical-insights": [
    { id: "u1", role: "user", content: "Open M. Hollister's chart. She's on the OR schedule for 5/12 for an inguinal hernia repair. Where do we stand on pre-op?" },
    { id: "a1", role: "assistant", time: "11:42",
      trace: { tool: "fhir.search", target: "MedicationStatement?patient=8.4127.881&status=active" },
      blocks: [
        "Hollister, 68F, scheduled 2025-05-12 for open inguinal hernia repair (CPT 49505). Active list confirms chronic atrial fibrillation on apixaban 5 mg BID [c_1042]. Bleed risk for the planned procedure is moderate.",
        "I have drafted a clearance briefing in [pre-op-packet-v2.md]. The disposition is REVIEW — the apixaban hold interval needs explicit attending sign-off and we are still waiting on the repeat INR [c_1091].",
      ],
      actions: [
        { label: "Open packet", icon: "FileText", target: "open-packet" },
        { label: "View anticoag note", icon: "FileText", target: "open-anticoag" },
        { label: "Cite c_1042 in inspector", icon: "Quote", target: "cite-c_1042" },
      ]
    },
    { id: "u2", role: "user", content: "What's the recommended hold for the apixaban — and is bridging needed?" },
    { id: "a2", role: "assistant", time: "11:43",
      blocks: [
        "Per institutional protocol and the patient's profile: hold apixaban ≥ 48 h before incision and restart 24 h after hemostasis is confirmed [c_1042]. Bridging with LMWH is not indicated — CHA2DS2-VASc is 3 and there is no mechanical valve history on the chart.",
        "Hematologic baseline is acceptable: Hgb 12.4 g/dL and platelets 218 × 10⁹/L on 2025-04-22 [c_1078]. The repeat INR is pending — surgical team to confirm < 1.4 morning-of [c_1091].",
      ],
      approval: {
        body: "Apply the apixaban 48 h pre-op hold and mark the packet ready for attending review? This is a controlled action and will be logged.",
        primary: "Approve hold",
        secondary: "Hold for attending",
      }
    }
  ],
  "trial-finder": [
    { id: "u1", role: "user", content: "Run a trial shortlist for Hollister. She's stable post-CML diagnosis, BCR-ABL+, prior imatinib intolerance. Caregiver radius 50 mi from home." },
    { id: "a1", role: "assistant", time: "12:08",
      trace: { tool: "marketplace.run", target: "trial-finder@2.4.1 / shortlist" },
      blocks: [
        "Pulled patient anchors from the Clinical Insights workspace under a consented, read-only handle. No patient identifiers leave this run [manifest.json]. Searching ClinicalTrials.gov against: chronic myeloid leukemia, BCR-ABL+, post-imatinib intolerance, ECOG 1, 50 mi radius.",
        "14 candidates returned. Ranking by clinical fit × operational fit × consent posture. Top three are queued in [ranked-shortlist.md] and the full board is open in the Workbench.",
      ],
      actions: [
        { label: "Open candidate board", icon: "Beaker", target: "open-board" },
        { label: "Open shortlist", icon: "FileText", target: "open-shortlist" },
        { label: "Inspect package manifest", icon: "Boxes", target: "open-manifest" },
      ]
    },
    { id: "u2", role: "user", content: "Walk me through NCT-0421187 first — and what would need approval before we reach out to the site?" },
    { id: "a2", role: "assistant", time: "12:10",
      blocks: [
        "NCT-0421187 is a Phase III ABL-tyrosine kinase inhibitor trial for post-imatinib intolerance patients at MSKCC. Clinical fit is 0.92 — biomarker, line of therapy, and performance status all match. Travel is ~38 mi; caregiver support is documented.",
        "Outreach is gated. Before I draft and send the outreach packet I will request a single approval card in this thread covering: (1) explicit consent to contact an external registry on the patient's behalf, and (2) the de-identification preset to apply.",
      ],
      approval: {
        body: "Draft the outreach packet for NCT-0421187 under preset de-id-v3, ready to send pending consent confirmation. Nothing leaves the workspace until the consent step is signed.",
        primary: "Draft packet",
        secondary: "Review consent first",
      }
    }
  ]
};

const INITIAL_TABS = {
  "clinical-insights": [
    { id: "tab_brief", label: "pre-op-packet-v2.md", icon: "FileText", kind: "preop-brief", dirty: true },
    { id: "tab_diff",  label: "v1 → v2 diff",       icon: "GitCompare", kind: "diff" },
    { id: "tab_sum",   label: "clearance-summary.json", icon: "Braces", kind: "summary-json" },
  ],
  "trial-finder": [
    { id: "tab_board", label: "candidate-board.json", icon: "Beaker",   kind: "trial-board" },
    { id: "tab_short", label: "ranked-shortlist.md",  icon: "FileText", kind: "packet-outline", dirty: true },
    { id: "tab_man",   label: "manifest.json",        icon: "Braces",   kind: "manifest-json" },
  ],
};

const FILE_TO_TAB = {
  f_brief:     { id: "tab_brief", label: "pre-op-packet-v2.md", icon: "FileText", kind: "preop-brief", dirty: true },
  f_packetv2:  { id: "tab_brief", label: "pre-op-packet-v2.md", icon: "FileText", kind: "preop-brief", dirty: true },
  f_packetv1:  { id: "tab_diff",  label: "v1 → v2 diff",        icon: "GitCompare", kind: "diff" },
  f_anticoag:  { id: "tab_anti",  label: "anticoagulation-note.txt", icon: "FileText", kind: "anticoag-note" },
  f_summary:   { id: "tab_sum",   label: "clearance-summary.json", icon: "Braces", kind: "summary-json" },
  f_board:     { id: "tab_board", label: "candidate-board.json", icon: "Beaker",   kind: "trial-board" },
  f_shortlist: { id: "tab_short", label: "ranked-shortlist.md",  icon: "FileText", kind: "packet-outline", dirty: true },
  f_packet:    { id: "tab_short", label: "ranked-shortlist.md",  icon: "FileText", kind: "packet-outline", dirty: true },
  f_manifest:  { id: "tab_man",   label: "manifest.json",        icon: "Braces",   kind: "manifest-json" },
  f_pkg:       { id: "tab_man",   label: "manifest.json",        icon: "Braces",   kind: "manifest-json" },
};

const ACTION_TO_TAB = {
  "open-packet":     FILE_TO_TAB.f_brief,
  "open-anticoag":   FILE_TO_TAB.f_anticoag,
  "open-board":      FILE_TO_TAB.f_board,
  "open-shortlist":  FILE_TO_TAB.f_shortlist,
  "open-manifest":   FILE_TO_TAB.f_manifest,
};

function App() {
  const t = useTweaks(TWEAK_DEFAULS);
  const [workspaceId, setWorkspaceId] = aUS("clinical-insights");
  const workspace = WORKSPACES[workspaceId];
  const [activeSession, setActiveSession] = aUS({ "clinical-insights": "s1", "trial-finder": "__home__" });
  const [chats, setChats] = aUS(INITIAL_CHAT);
  const [tabsByWs, setTabsByWs] = aUS(INITIAL_TABS);
  const [activeTabByWs, setActiveTabByWs] = aUS({ "clinical-insights": "tab_brief", "trial-finder": "tab_board" });
  const [citation, setCitation] = aUS(null);
  const [panes, setPanes] = aUS({ sessions: true, chat: true, preview: true, files: true, inspector: true });
  const [sizes, setSizes] = aUS({ sessionsW: 248, chatW: 480, rightW: 300, filesH: 50 });
  const appRef = React.useRef(null);
  const stageRef = React.useRef(null);
  const rightStackRef = React.useRef(null);

  const startDrag = aUC((axis, key) => (e) => {
    e.preventDefault();
    const startX = e.clientX, startY = e.clientY;
    const start = sizes[key];
    document.body.classList.add(axis === "v" ? "resizing-v" : "resizing-h");
    const onMove = (ev) => {
      if (axis === "v") {
        let delta = ev.clientX - startX;
        if (key === "rightW") delta = -delta;
        const next = Math.max(180, Math.min(900, start + delta));
        setSizes((s) => ({ ...s, [key]: next }));
      } else {
        const rect = rightStackRef.current?.getBoundingClientRect();
        if (!rect) return;
        const pct = Math.max(15, Math.min(85, ((ev.clientY - rect.top) / rect.height) * 100));
        setSizes((s) => ({ ...s, filesH: pct }));
      }
    };
    const onUp = () => {
      document.body.classList.remove("resizing-v", "resizing-h");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [sizes]);

  // apply theme tweaks
  aUE(() => {
    document.documentElement.setAttribute("data-theme", t.theme);
    const acc = ACCENTS[t.accent] || ACCENTS["clinical-blue"];
    const r = document.documentElement.style;
    r.setProperty("--action", acc.action);
    r.setProperty("--action-hover", acc.hover);
    r.setProperty("--action-press", acc.press);
    r.setProperty("--action-tint", acc.tint);
    r.setProperty("--action-tint-2", acc.tint2);
    r.setProperty("--action-line", acc.line);
  }, [t.theme, t.accent]);

  // shortcuts
  aUE(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); /* command */ }
      if (e.altKey) {
        if (e.key.toLowerCase() === "s") setPanes(p => ({...p, sessions: !p.sessions}));
        if (e.key.toLowerCase() === "c") setPanes(p => ({...p, chat: !p.chat}));
        if (e.key.toLowerCase() === "p") setPanes(p => ({...p, preview: !p.preview}));
        if (e.key.toLowerCase() === "f") setPanes(p => ({...p, files: !p.files}));
        if (e.key.toLowerCase() === "i") setPanes(p => ({...p, inspector: !p.inspector}));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const [activeModule, setActiveModule] = aUS("caspian");
  const sessions = SESSIONS[workspaceId];
  const messages = chats[workspaceId];
  const tabs = tabsByWs[workspaceId];
  const activeTabId = activeTabByWs[workspaceId];
  const isHome = activeSession[workspaceId] === "__home__";
  const sessionTitle = isHome
    ? "Package home"
    : sessions.find(s => s.id === activeSession[workspaceId])?.title || "Session";
  const startNewRun = aUC(() => {
    setActiveSession(p => ({ ...p, [workspaceId]: sessions[0]?.id }));
  }, [workspaceId, sessions]);
  const openRun = aUC((id) => {
    setActiveSession(p => ({ ...p, [workspaceId]: sessions[0]?.id }));
  }, [workspaceId, sessions]);

  const handleCite = aUC((id) => {
    setCitation(id);
    setPanes(p => p.inspector ? p : { ...p, inspector: true });
  }, []);

  const handleOpenFile = aUC((c) => {
    if (c.kind === "citation") { handleCite(c.id); return; }
    const t2 = FILE_TO_TAB[c.id];
    if (!t2) return;
    setTabsByWs(prev => {
      const ws = prev[workspaceId];
      if (ws.some(x => x.id === t2.id)) return prev;
      return { ...prev, [workspaceId]: [...ws, t2] };
    });
    setActiveTabByWs(prev => ({ ...prev, [workspaceId]: t2.id }));
  }, [workspaceId, handleCite]);

  const handleAction = aUC((a) => {
    if (a.target && a.target.startsWith("cite-")) {
      handleCite(a.target.slice(5));
      return;
    }
    const tab = ACTION_TO_TAB[a.target];
    if (!tab) return;
    setTabsByWs(prev => {
      const ws = prev[workspaceId];
      if (ws.some(x => x.id === tab.id)) return prev;
      return { ...prev, [workspaceId]: [...ws, tab] };
    });
    setActiveTabByWs(prev => ({ ...prev, [workspaceId]: tab.id }));
  }, [workspaceId, handleCite]);

  const handleSend = aUC((text) => {
    const userMsg = { id: "u" + Date.now(), role: "user", content: text };
    const tool = workspace.family === "clinical" ? "fhir.search" : "marketplace.run";
    const target = workspace.family === "clinical" ? "Observation?patient=8.4127.881" : "trial-finder@2.4.1 / re-rank";
    const reply = {
      id: "a" + Date.now(),
      role: "assistant",
      time: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      trace: { tool, target },
      blocks: workspace.family === "clinical"
        ? ["Acknowledged. I'll fold that into the briefing — citations will keep flowing into [pre-op-packet-v2.md] and the inspector will track every pinned source. Drop a citation chip to open the underlying FHIR resource."]
        : ["Acknowledged. I'll re-rank the shortlist and surface anything that crosses the consent boundary in this thread. The package keeps a clean read-only handle on the Clinical Insights workspace — no PHI leaves the run."],
    };
    setChats(prev => ({ ...prev, [workspaceId]: [...prev[workspaceId], userMsg, reply] }));
  }, [workspaceId, workspace]);

  const handleSelectTab = aUC((id) => setActiveTabByWs(prev => ({ ...prev, [workspaceId]: id })), [workspaceId]);
  const handleCloseTab = aUC((id) => {
    setTabsByWs(prev => {
      const ws = prev[workspaceId].filter(x => x.id !== id);
      return { ...prev, [workspaceId]: ws };
    });
    setActiveTabByWs(prev => {
      if (prev[workspaceId] !== id) return prev;
      const remaining = tabsByWs[workspaceId].filter(x => x.id !== id);
      return { ...prev, [workspaceId]: remaining[0]?.id || null };
    });
  }, [workspaceId, tabsByWs]);

  const tree = FILE_TREES[workspaceId];

  return (
    <div className="app"
      ref={appRef}
      data-density={t.density}
      data-sessions-hidden={!panes.sessions}
      style={{ "--sessions-w": sizes.sessionsW + "px" }}>
      <ModuleBar activeModule={activeModule} onSelect={setActiveModule}
        workspaceId={workspaceId} onSwitchWorkspace={setWorkspaceId}/>
      <Titlebar workspace={workspace} panes={panes} setPanes={setPanes} density={t.density} sessionTitle={sessionTitle}/>
      <GlobalRail workspace={workspace} onSwitchWorkspace={setWorkspaceId} hidden/>
      {panes.sessions && (
        <SessionsPane workspace={workspace}
          sessions={sessions}
          activeSessionId={activeSession[workspaceId]}
          onSelect={(id) => setActiveSession(p => ({ ...p, [workspaceId]: id }))}
          onSwitchWorkspace={setWorkspaceId}/>
      )}
      {panes.sessions && (
        <div className="resizer-v resizer-sessions"
          style={{ position: "absolute", left: "var(--sessions-w)", top: 80, bottom: 0, marginLeft: -2 }}
          onMouseDown={startDrag("v", "sessionsW")}/>
      )}
      <div className="stage"
        ref={stageRef}
        data-chat={panes.chat}
        data-preview={panes.preview}
        data-right={panes.files || panes.inspector}
        style={{ "--chat-w": sizes.chatW + "px", "--right-w": sizes.rightW + "px" }}>
        <ContextStrip workspace={workspace} sessionTitle={sessionTitle}/>
        {isHome && workspace.family === "marketplace" ? (
          <div className="stage-row">
            <PackageHome workspace={workspace} onStartRun={startNewRun} onOpenRun={openRun}/>
          </div>
        ) : (
        <div className="stage-row">
        {panes.chat && (
          <ChatPane workspace={workspace} messages={messages}
            onSend={handleSend}
            onCitationClick={handleCite}
            activeCitation={citation}
            onAction={handleAction}/>
        )}
        {panes.chat && panes.preview && (
          <div className="resizer-v resizer-chat" onMouseDown={startDrag("v", "chatW")}/>
        )}
        {panes.preview && (
          <PreviewPane tabs={tabs} activeTabId={activeTabId}
            onSelectTab={handleSelectTab} onCloseTab={handleCloseTab}
            workspace={workspace}
            onCitationClick={handleCite} activeCitation={citation}/>
        )}
        {(panes.files || panes.inspector) && (panes.chat || panes.preview) && (
          <div className="resizer-v resizer-right" onMouseDown={startDrag("v", "rightW")}/>
        )}
        {(panes.files || panes.inspector) && (
          <div className="right-stack"
            ref={rightStackRef}
            data-only={!panes.files ? "inspector" : !panes.inspector ? "files" : "both"}
            style={panes.files && panes.inspector ? { "--files-h": sizes.filesH + "%", "--insp-h": (100 - sizes.filesH) + "%" } : {}}>
            {panes.files && <FilesPane tree={tree} openFile={handleOpenFile} activeFileId={null}/>}
            {panes.files && panes.inspector && (
              <div className="resizer-h resizer-files-insp" onMouseDown={startDrag("h", "filesH")}/>
            )}
            {panes.inspector && <InspectorPane citationId={citation} onClose={() => setCitation(null)}/>}
          </div>
        )}
        </div>
        )}
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection title="Appearance">
          <TweakRadio label="Theme" value={t.theme} options={[
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ]} onChange={v => t.setTweak("theme", v)}/>
          <TweakColor label="Accent" value={t.accent} options={[
            { value: "clinical-blue", color: "#1d4ed8" },
            { value: "graphite", color: "#1f2937" },
            { value: "violet", color: "#5b3df2" },
            { value: "teal", color: "#0d9488" },
          ]} onChange={v => t.setTweak("accent", v)}/>
          <TweakRadio label="Density" value={t.density} options={[
            { value: "comfortable", label: "Comfortable" },
            { value: "compact", label: "Compact" },
          ]} onChange={v => t.setTweak("density", v)}/>
        </TweakSection>
        <TweakSection title="Workspace">
          <TweakRadio label="Active workspace"
            value={workspaceId}
            options={[
              { value: "clinical-insights", label: "Clinical" },
              { value: "trial-finder", label: "Marketplace" },
            ]}
            onChange={setWorkspaceId}/>
          <TweakToggle label="Sessions pane" value={panes.sessions} onChange={v => setPanes(p => ({...p, sessions: v}))}/>
          <TweakToggle label="Chat pane" value={panes.chat} onChange={v => setPanes(p => ({...p, chat: v}))}/>
          <TweakToggle label="Workbench" value={panes.preview} onChange={v => setPanes(p => ({...p, preview: v}))}/>
          <TweakToggle label="Files pane" value={panes.files} onChange={v => setPanes(p => ({...p, files: v}))}/>
          <TweakToggle label="Inspector" value={panes.inspector} onChange={v => setPanes(p => ({...p, inspector: v}))}/>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
