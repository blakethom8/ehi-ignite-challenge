// Atlas Agentic Shell — main React app
const { useState, useEffect, useRef, useMemo, useCallback, Fragment } = React;

/* ============== TITLEBAR ============== */
function Titlebar({ workspace, panes, setPanes, density, onCommand, sessionTitle }) {
  return (
    <div className="titlebar">
      <div className="traffic"><span></span><span></span><span></span></div>
      <div className="crumbs">
        <div className="brand-mark">A</div>
        <strong>Atlas</strong>
        <span className="sep">/</span>
        <span className="crumb">{workspace.title}</span>
        <span className="sep">/</span>
        <span className="crumb-active">{sessionTitle}</span>
      </div>
      <div className="titlebar-spacer"></div>
      <WorkflowTriggerButton workspace={workspace} />
      <button className="tb-btn" onClick={onCommand} title="Command palette ⌘K">
        <Icon name="Command" size={14} />
      </button>
      <button className="tb-btn" title="Notifications"><Icon name="Bell" size={14} /></button>
      <div style={{ width: 8 }}></div>
      <div className="pane-toggles">
        <button className={"pane-tog " + (panes.sessions ? "on" : "")}
        onClick={() => setPanes((p) => ({ ...p, sessions: !p.sessions }))} title="Sessions">S</button>
        <button className={"pane-tog " + (panes.chat ? "on" : "")}
        onClick={() => setPanes((p) => ({ ...p, chat: !p.chat }))} title="Chat">C</button>
        <button className={"pane-tog " + (panes.preview ? "on" : "")}
        onClick={() => setPanes((p) => ({ ...p, preview: !p.preview }))} title="Workbench">P</button>
        <button className={"pane-tog " + (panes.files ? "on" : "")}
        onClick={() => setPanes((p) => ({ ...p, files: !p.files }))} title="Files">F</button>
        <button className={"pane-tog " + (panes.inspector ? "on" : "")}
        onClick={() => setPanes((p) => ({ ...p, inspector: !p.inspector }))} title="Inspector">I</button>
      </div>
    </div>);

}

function WorkflowTriggerButton({ workspace }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onClick = (e) => {if (ref.current && !ref.current.contains(e.target)) setOpen(false);};
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  const workflows = WORKFLOWS[workspace.id] || [];
  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button className="workflow-trigger" onClick={() => setOpen((o) => !o)}>
        <span className="dot"></span>
        Run workflow
        <Icon name="ChevronDown" size={11} className="caret" />
      </button>
      {open &&
      <div className="wf-menu fade-in" style={{ top: 32, right: 0 }}>
          <div className="wf-title">{workspace.title} workflows</div>
          {workflows.map((w) =>
        <div key={w.id} className="wf-item" onClick={() => setOpen(false)}>
              <div className="wf-t">{w.title}</div>
              <div className="wf-d">{w.desc}</div>
              <div className="wf-tags">{w.tags.map((t) => <span key={t} className="wf-tag">{t}</span>)}</div>
            </div>
        )}
        </div>
      }
    </div>);

}

/* ============== GLOBAL RAIL ============== */
function GlobalRail({ workspace, onSwitchWorkspace }) {
  const items = [
  { id: "home", icon: "Home", label: "Home" },
  { id: "library", icon: "Library", label: "Workspace library" },
  { id: "patients", icon: "Users", label: "Patients" },
  { id: "clinical", icon: "Stethoscope", label: "Clinical Insights", active: workspace.family === "clinical" },
  { id: "marketplace", icon: "Boxes", label: "Marketplace", active: workspace.family === "marketplace", badge: true },
  { id: "review", icon: "ScanSearch", label: "Review / Trace" }];

  return (
    <div className="rail">
      {items.map((i) =>
      <button key={i.id} className={"rail-btn " + (i.active ? "active" : "")}
      onClick={() => {
        if (i.id === "clinical") onSwitchWorkspace("clinical-insights");else
        if (i.id === "marketplace") onSwitchWorkspace("trial-finder");
      }}>
          <Icon name={i.icon} size={18} />
          {i.badge && <span className="badge"></span>}
          <span className="rail-tooltip">{i.label}</span>
        </button>
      )}
      <div className="rail-spacer"></div>
      <button className="rail-btn"><Icon name="Settings" size={18} /><span className="rail-tooltip">Settings</span></button>
    </div>);

}

/* ============== SESSIONS PANE ============== */
function SessionsPane({ workspace, sessions, activeSessionId, onSelect, onSwitchWorkspace }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const wfList = WORKFLOWS[workspace.id] || [];
  return (
    <div className="sessions">
      <div className="workspace-switcher"
      onClick={() => setMenuOpen((o) => !o)}
      style={{ "--workspace-tint": workspace.tint, "--workspace-color": workspace.color }}>
        <div className="ws-icon"><Icon name={workspace.icon} size={14} /></div>
        <div className="ws-meta">
          <div className="ws-title">{workspace.title}</div>
          <div className="ws-sub">{workspace.subtitle}</div>
        </div>
        <Icon name="ChevronDown" size={12} className="ws-caret" />
      </div>

      {menuOpen &&
      <>
          <div className="scrim" onClick={() => setMenuOpen(false)} style={{ background: "transparent" }}></div>
          <div className="ws-menu fade-in">
            <div className="ws-section">
              <div className="ws-section-title">Active workspaces</div>
              {Object.values(WORKSPACES).map((w) =>
            <div key={w.id}
            className={"ws-item " + (w.id === workspace.id ? "active" : "")}
            onClick={() => {onSwitchWorkspace(w.id);setMenuOpen(false);}}>
                  <div className="ws-i" style={{ background: w.tint, color: w.color }}><Icon name={w.icon} size={14} /></div>
                  <div>
                    <div className="ws-t">{w.title}</div>
                    <div className="ws-s">{w.subtitle}</div>
                  </div>
                  {w.id === workspace.id && <div className="ws-check"><Icon name="CheckCircle2" size={14} /></div>}
                </div>
            )}
            </div>
            <div className="ws-divider"></div>
            <div className="ws-section">
              <div className="ws-section-title">Browse</div>
              <div className="ws-item">
                <div className="ws-i" style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}><Icon name="Library" size={14} /></div>
                <div><div className="ws-t">Open workspace library</div><div className="ws-s">Browse marketplace + first-party</div></div>
              </div>
            </div>
          </div>
        </>
      }

      <div className="sessions-search">
        <Icon name="Search" size={12} />
        <input placeholder="Search sessions, files, citations" />
        <span className="kbd shortcut">⌘K</span>
      </div>

      <div className="session-scroll">
        {workspace.family === "marketplace" && (
          <div className="session-group">
            <div className="session-group-head"><span>Package</span></div>
            <div className={"session-row " + (activeSessionId === "__home__" ? "active" : "")}
              onClick={() => onSelect("__home__")}>
              <div className="session-icon"><Icon name="Home" size={12}/></div>
              <div className="session-body">
                <div className="session-title">Package home</div>
                <div className="session-meta"><span>About · Workflows · Recent runs</span></div>
              </div>
            </div>
          </div>
        )}
        <div className="session-group">
          <div className="session-group-head"><span>Recent sessions</span><span className="count">{sessions.length}</span></div>
          {sessions.map((s) =>
          <div key={s.id}
          className={"session-row " + (s.id === activeSessionId ? "active" : "")}
          onClick={() => onSelect(s.id)}>
              <div className="session-icon">
                <Icon name={s.workflow === "preop" ? "Activity" : s.workflow === "shortlist" ? "Telescope" : "MessageSquareText"} size={12} />
              </div>
              <div className="session-body">
                <div className="session-title">{s.title}</div>
                <div className="session-meta">
                  <span className={"session-state-dot state-" + s.state}></span>
                  <span>{s.meta}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="session-group">
          <div className="session-group-head"><span>Workflow library</span><a href="#" onClick={(e) => e.preventDefault()} style={{ color: "var(--action)", fontWeight: 500, fontSize: 10 }}>BROWSE</a></div>
          {wfList.slice(0, 3).map((w) =>
          <div key={w.id} className="session-pin">
              <Icon name="Workflow" size={12} />{w.title}
            </div>
          )}
        </div>

        <div className="session-group">
          <div className="session-group-head"><span>Pinned artifacts</span></div>
          <div className="session-pin"><Icon name="Pin" size={12} />pre-op-packet-v2.md</div>
          <div className="session-pin"><Icon name="Pin" size={12} />clearance-summary.json</div>
        </div>
      </div>

      <button className="new-session"><Icon name="Plus" size={12} />New session</button>
    </div>);

}

/* ============== CHAT PANE ============== */
function ChatPane({ workspace, messages, onSend, onCitationClick, activeCitation, onAction }) {
  const [text, setText] = useState("");
  const scrollRef = useRef(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length]);

  const submit = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <section className="chat-pane">
      <div className="chat-head">
        <div className="label">
          {workspace.family === "clinical" ? "Clinical chat" : "Workspace thread"}
          <small>{workspace.title} agent</small>
        </div>
        <div className="right">
          <div className={"boundary-pill " + (workspace.boundaryTone === "warn" ? "warn" : "")}>
            <Icon name={workspace.boundaryTone === "warn" ? "Globe" : "Lock"} size={10} />
            {workspace.boundary}
          </div>
        </div>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-meta">
          <span>Session opened 12 min ago</span>
          <span className="dot-sep"></span>
          <span>{messages.length} messages</span>
          <span className="dot-sep"></span>
          <span>5 citations · 3 tabs · 1 approval pending</span>
        </div>

        {messages.map((m, i) =>
        <Message key={m.id} msg={m} workspace={workspace}
        onCitationClick={onCitationClick} activeCitation={activeCitation}
        onAction={onAction} />
        )}
      </div>

      <div className="composer">
        <div className="composer-inner">
          <textarea
            className="composer-input"
            placeholder={workspace.family === "clinical" ?
            "Ask about the chart, hold a workflow, or open another tab…" :
            "Steer the run, approve a step, or open another tab…"}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {e.preventDefault();submit();}
            }}
            rows={2} />
          
          <div className="composer-bar">
            <button className="composer-btn"><Icon name="Paperclip" size={12} />Attach</button>
            <button className="composer-btn"><Icon name="Pin" size={12} />Pin context</button>
            <button className="composer-btn outline"><Icon name="Sparkles" size={12} />{workspace.family === "clinical" ? "clinical-high" : "marketplace-act"}</button>
            <div className="spacer"></div>
            <span className="kbd">↵ to send</span>
            <button className="composer-send" onClick={submit} disabled={!text.trim()}><Icon name="ArrowUp" size={13} /></button>
          </div>
        </div>
      </div>
    </section>);

}

function Message({ msg, workspace, onCitationClick, activeCitation, onAction }) {
  if (msg.role === "user") {
    return (
      <div className="msg user fade-in">
        <div className="bubble">{msg.content}</div>
      </div>);

  }
  return (
    <div className="msg assistant fade-in">
      <div className={"avatar " + (workspace.family === "clinical" ? "preop" : "trials")}>
        {workspace.family === "clinical" ? "Px" : "Tf"}
      </div>
      <div>
        <div className="from">
          {workspace.family === "clinical" ? "Pre-op agent" : "Trial Finder agent"}
          <span className="timestamp">· {msg.time || "just now"}</span>
        </div>

        {msg.trace &&
        <div className="tool-trace">
            <Icon name="Workflow" size={12} />
            <span className="tt-name">{msg.trace.tool}</span>
            <span className="tt-arrow">→</span>
            <span className="tt-target">{msg.trace.target}</span>
          </div>
        }

        <div className="bubble">
          {msg.blocks.map((b, i) =>
          <p key={i}>{renderInline(b, onCitationClick, activeCitation)}</p>
          )}
        </div>

        {msg.approval &&
        <div className="approval-card">
            <div className="ac-icon"><Icon name="AlertTriangle" size={16} /></div>
            <div>
              <div className="ac-title">APPROVAL REQUESTED</div>
              <div className="ac-body">{msg.approval.body}</div>
              <div className="ac-actions">
                <button className="ac-btn primary">{msg.approval.primary}</button>
                <button className="ac-btn">{msg.approval.secondary}</button>
              </div>
            </div>
          </div>
        }

        {msg.actions &&
        <div className="action-row">
            {msg.actions.map((a, i) =>
          <button key={i} className="chip" onClick={() => onAction(a)}>
                <Icon name={a.icon || "ArrowRight"} size={11} />{a.label}
              </button>
          )}
          </div>
        }
      </div>
    </div>);

}

function renderInline(text, onCitationClick, activeCitation) {
  // Replace [c_xxxx] or [filename.ext] with chips
  const parts = [];
  const regex = /\[(c_\d+|[a-z0-9_.\-]+\.(md|json|txt|csv))\]/gi;
  let last = 0;let m;let i = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const ref = m[1];
    const isCite = ref.startsWith("c_");
    parts.push(
      <span key={i++}
      className={"citation-chip " + (activeCitation === ref ? "active" : "")}
      onClick={() => onCitationClick(ref)}>
        {isCite ? <Icon name="Quote" size={9} /> : <Icon name="FileText" size={9} />}
        {ref}
      </span>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

Object.assign(window, { Titlebar, GlobalRail, SessionsPane, ChatPane, ContextStrip, ModuleBar });

/* ============== MODULE BAR (top-level EHI Ignite product nav) ============== */
function ModuleBar({ activeModule, onSelect, workspaceId, onSwitchWorkspace }) {
  const [wsOpen, setWsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const wsRef = useRef(null);
  useEffect(() => {
    const onClick = (e) => { if (wsRef.current && !wsRef.current.contains(e.target)) setWsOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  const modules = [
    { id: "patient-record", label: "Patient Record" },
    { id: "fhir-charts", label: "FHIR Charts" },
    { id: "caspian", label: "Caspian" },
    { id: "workspaces", label: "Workspaces", hasMenu: true },
    { id: "learn", label: "Learn" },
  ];
  const recentWorkspaces = [
    { id: "trial-finder", label: "Trial Finder", vendor: "Helix Clinical", icon: "Telescope" },
    { id: "med-access",   label: "Medication Access", vendor: "RxBridge",     icon: "Pill" },
    { id: "site-coord",   label: "Site Coordination", vendor: "TrialOps",     icon: "Send" },
  ];
  return (
    <>
    <div className="module-bar">
      <button className="mb-menu" onClick={() => setDrawerOpen(true)} title="Open menu"><Icon name="Menu" size={14}/></button>
      <div className="mb-brand">
        <div className="mb-logo">EI</div>
        <span className="mb-product">EHI Ignite</span>
      </div>
      <div className="mb-tabs">
        {modules.map((m) => {
          const active = m.id === activeModule || (m.id === "caspian" && workspaceId === "clinical-insights" && activeModule === "caspian") || (m.id === "workspaces" && workspaceId !== "clinical-insights" && activeModule === "workspaces");
          if (m.hasMenu) {
            return (
              <div key={m.id} ref={wsRef} className="mb-tab-wrap">
                <button className={"mb-tab " + (active ? "active" : "")}
                  onClick={() => { onSelect(m.id); setWsOpen(o => !o); }}>
                  {m.label}<Icon name="ChevronDown" size={10} className="mb-caret"/>
                </button>
                {wsOpen && (
                  <div className="mb-dropdown fade-in">
                    <div className="mb-dd-item primary" onClick={() => { setWsOpen(false); onSelect("workspaces"); }}>
                      <Icon name="Compass" size={13}/>
                      <div><div className="mb-dd-t">Explore workspaces</div><div className="mb-dd-s">Marketplace · install new packages</div></div>
                    </div>
                    <div className="mb-dd-divider"></div>
                    <div className="mb-dd-section">RECENTLY VIEWED</div>
                    {recentWorkspaces.map(w => (
                      <div key={w.id} className="mb-dd-item"
                        onClick={() => { setWsOpen(false); onSelect("workspaces"); onSwitchWorkspace && w.id === "trial-finder" && onSwitchWorkspace("trial-finder"); }}>
                        <Icon name={w.icon} size={13}/>
                        <div><div className="mb-dd-t">{w.label}</div><div className="mb-dd-s">{w.vendor}</div></div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          }
          return (
            <button key={m.id}
              className={"mb-tab " + (active ? "active" : "")}
              onClick={() => { onSelect(m.id); if (m.id === "caspian" && onSwitchWorkspace) onSwitchWorkspace("clinical-insights"); }}>
              {m.label}
            </button>
          );
        })}
      </div>
      <div className="mb-spacer"></div>
      <div className="mb-right">
        <button className="mb-icon"><Icon name="Search" size={13}/></button>
        <button className="mb-icon"><Icon name="HelpCircle" size={13}/></button>
        <div className="mb-user">RP</div>
      </div>
    </div>
    {drawerOpen && (
      <>
        <div className="platform-scrim" onClick={() => setDrawerOpen(false)}></div>
        <div className="platform-drawer slide-in-left">
          <div className="pd-head">
            <div className="pd-brand"><div className="mb-logo">EI</div><strong>EHI Ignite</strong></div>
            <button className="pd-close" onClick={() => setDrawerOpen(false)}><Icon name="X" size={14}/></button>
          </div>
          <div className="pd-user">
            <div className="pd-avatar">RP</div>
            <div><div className="pd-name">R. Patel</div><div className="pd-org">Mercy Medical Group · Clinician</div></div>
          </div>
          <div className="pd-section">
            <div className="pd-item"><Icon name="Settings" size={14}/>Settings</div>
            <div className="pd-item"><Icon name="UserRound" size={14}/>Account</div>
            <div className="pd-item"><Icon name="CreditCard" size={14}/>Billing & usage</div>
            <div className="pd-item"><Icon name="Boxes" size={14}/>Organization</div>
            <div className="pd-item"><Icon name="ShieldCheck" size={14}/>Permissions & audit</div>
          </div>
          <div className="pd-divider"></div>
          <div className="pd-section">
            <div className="pd-item"><Icon name="HelpCircle" size={14}/>Help & support</div>
            <div className="pd-item"><Icon name="FileText" size={14}/>What's new</div>
            <div className="pd-item"><Icon name="MessageSquareText" size={14}/>Send feedback</div>
          </div>
          <div className="pd-spacer"></div>
          <div className="pd-foot">
            <div className="pd-item muted"><Icon name="LogOut" size={14}/>Sign out</div>
          </div>
        </div>
      </>
    )}
    </>
  );
}

/* ============== CONTEXT STRIP (workspace identity below titlebar) ============== */
function ContextStrip({ workspace, sessionTitle }) {
  if (workspace.family === "clinical") return <CaspianPatientStrip workspace={workspace}/>;
  return <PackageRunStrip workspace={workspace} sessionTitle={sessionTitle}/>;
}

function CaspianPatientStrip({ workspace }) {
  const p = window.AtlasData?.PATIENT || {};
  return (
    <div className="context-strip caspian">
      <div className="cs-icon caspian"><Icon name="UserRound" size={14}/></div>
      <div className="cs-name">{p.name}</div>
      <span className="cs-sep">·</span>
      <span className="cs-mono">{p.mrn}</span>
      <span className="cs-sep">·</span>
      <span className="cs-meta">{p.ageSex}</span>
      <span className="cs-sep">·</span>
      <span className="cs-tier"><span className="tier-dot"></span>{p.tier}</span>
      <span className="cs-sep">·</span>
      <span className="cs-meta"><Icon name="Database" size={11}/>{p.fhirCount}</span>
      <span className="cs-sep">·</span>
      <span className="cs-meta">{p.encounters} encounters</span>
      <div className="cs-spacer"></div>
      <div className="cs-pill"><Icon name="Pin" size={10}/>Pinned to session</div>
      <div className="cs-pill green"><Icon name="Lock" size={10}/>Private patient boundary</div>
    </div>
  );
}

function PackageRunStrip({ workspace, sessionTitle }) {
  const runIcon = workspace.runState === "running" ? "Loader" : workspace.runState === "complete" ? "CheckCircle2" : "Pause";
  return (
    <div className="context-strip package">
      <div className="cs-icon package"><Icon name={workspace.icon} size={14}/></div>
      <div className="cs-name">{workspace.title}</div>
      <span className="cs-mono cs-version">@{workspace.version}</span>
      <span className="cs-sep">·</span>
      <span className="cs-meta">{workspace.vendor}</span>
      <span className="cs-sep">·</span>
      <div className="cs-perms">
        {workspace.permissions?.map((p,i) => (
          <span key={i} className="perm"><Icon name={i===0?"Database":i===1?"Globe":"Send"} size={10}/>{p}</span>
        ))}
      </div>
      <div className="cs-spacer"></div>
      <div className="run-state">
        <span className={"run-dot " + workspace.runState}></span>
        <span className="rs-label">{workspace.runState?.toUpperCase()}</span>
        <span className="cs-sep">·</span>
        <span className="cs-meta">step {workspace.runStep}</span>
        <span className="cs-sep">·</span>
        <span className="cs-mono">{workspace.runElapsed}</span>
      </div>
      <button className="run-ctrl"><Icon name="Pause" size={11}/>Pause</button>
      <div className="cs-pill warn"><Icon name="Link2" size={10}/>{workspace.anchoredFrom}</div>
    </div>
  );
}