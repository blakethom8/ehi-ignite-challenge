// PipelineDiagram — inline SVG visualization of the Atlas 4-stage pipeline.
// Resolution-independent, on-palette, no asset management.

interface StageProps {
  index: number;
  label: string;
  caption: string;
  icon: "ingest" | "adapt" | "harmonize" | "bundle";
}

const STAGES: StageProps[] = [
  { index: 1, label: "Ingest", caption: "Sources arrive", icon: "ingest" },
  { index: 2, label: "Adapt", caption: "Per-source parsers", icon: "adapt" },
  { index: 3, label: "Harmonize", caption: "Merge + provenance", icon: "harmonize" },
  { index: 4, label: "Bundle", caption: "Secure + portable", icon: "bundle" },
];

// Layout constants (units = SVG user units)
const VIEW_W = 720;
const VIEW_H = 240;
const BOX_W = 156;
const BOX_H = 168;
const BOX_R = 14;
const GAP = 32;
const ROW_W = 4 * BOX_W + 3 * GAP; // = 720
const X_OFFSET = (VIEW_W - ROW_W) / 2;
const Y_OFFSET = 36;

function boxX(i: number) {
  return X_OFFSET + i * (BOX_W + GAP);
}

// Stage icons — simple geometric, all on a 28x28 canvas centered at (0,0)
function StageIcon({ kind }: { kind: StageProps["icon"] }) {
  const stroke = "#5b76fe";
  const sw = 1.6;
  switch (kind) {
    case "ingest":
      // Stacked document pages flowing down
      return (
        <g stroke={stroke} strokeWidth={sw} fill="none" strokeLinejoin="round" strokeLinecap="round">
          <rect x={-11} y={-9} width={18} height={22} rx={2} />
          <rect x={-7} y={-13} width={18} height={22} rx={2} fill="#fdfdff" />
          <line x1={-3} y1={-7} x2={7} y2={-7} />
          <line x1={-3} y1={-2} x2={7} y2={-2} />
          <line x1={-3} y1={3} x2={3} y2={3} />
        </g>
      );
    case "adapt":
      // Two arrows converging to one — transformation
      return (
        <g stroke={stroke} strokeWidth={sw} fill="none" strokeLinejoin="round" strokeLinecap="round">
          <path d="M -12 -8 L -2 0 L -12 8" />
          <path d="M -2 0 L 12 0" />
          <circle cx={12} cy={0} r={3} fill={stroke} stroke="none" />
        </g>
      );
    case "harmonize":
      // Three lines merging into one — dedup/merge
      return (
        <g stroke={stroke} strokeWidth={sw} fill="none" strokeLinejoin="round" strokeLinecap="round">
          <path d="M -12 -10 Q -2 -10 0 0" />
          <path d="M -12 0 L 0 0" />
          <path d="M -12 10 Q -2 10 0 0" />
          <path d="M 0 0 L 12 0" />
          <circle cx={12} cy={0} r={3} fill={stroke} stroke="none" />
        </g>
      );
    case "bundle":
      // Wrapped/sealed package — box with binding strap and a center seal mark
      return (
        <g stroke={stroke} strokeWidth={sw} fill="none" strokeLinejoin="round" strokeLinecap="round">
          {/* Box outline */}
          <rect x={-12} y={-9} width={24} height={20} rx={2.5} />
          {/* Horizontal binding strap */}
          <line x1={-12} y1={1} x2={12} y2={1} />
          {/* Vertical binding (perpendicular through center) */}
          <line x1={0} y1={-9} x2={0} y2={11} />
          {/* Centered seal */}
          <circle cx={0} cy={1} r={2.5} fill={stroke} stroke="none" />
        </g>
      );
  }
}

// Single stage card
function StageCard({ index, label, caption, icon, x }: StageProps & { x: number }) {
  const cx = x + BOX_W / 2;
  return (
    <g>
      {/* Card */}
      <rect
        x={x}
        y={Y_OFFSET}
        width={BOX_W}
        height={BOX_H}
        rx={BOX_R}
        ry={BOX_R}
        fill="url(#stage-fill)"
        stroke="#cfd7ff"
        strokeWidth={1.25}
      />

      {/* Index badge */}
      <g transform={`translate(${x + 16}, ${Y_OFFSET + 16})`}>
        <circle r={11} fill="#5b76fe" />
        <text
          x={0}
          y={0}
          fontSize={10}
          fontWeight={700}
          fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
          textAnchor="middle"
          dominantBaseline="central"
          fill="white"
        >
          0{index}
        </text>
      </g>

      {/* Icon */}
      <g transform={`translate(${cx}, ${Y_OFFSET + 70})`}>
        <StageIcon kind={icon} />
      </g>

      {/* Label */}
      <text
        x={cx}
        y={Y_OFFSET + 118}
        fontSize={15}
        fontWeight={700}
        textAnchor="middle"
        fill="#1d2433"
        fontFamily="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif"
      >
        {label}
      </text>

      {/* Caption */}
      <text
        x={cx}
        y={Y_OFFSET + 138}
        fontSize={11}
        textAnchor="middle"
        fill="#6b7390"
        fontFamily="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif"
      >
        {caption}
      </text>
    </g>
  );
}

// Arrow between two stages
function StageArrow({ fromX }: { fromX: number }) {
  const startX = fromX + BOX_W + 6;
  const endX = fromX + BOX_W + GAP - 6;
  const y = Y_OFFSET + BOX_H / 2;
  return (
    <g stroke="#9aa5c0" strokeWidth={1.4} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <line x1={startX} y1={y} x2={endX - 4} y2={y} />
      <polyline points={`${endX - 8},${y - 4} ${endX},${y} ${endX - 8},${y + 4}`} />
    </g>
  );
}

export function PipelineDiagram() {
  return (
    <div className="overflow-hidden rounded-xl border border-[#e7eaf2] bg-white p-3">
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="Atlas pipeline diagram: ingest, adapt, harmonize, reason"
        className="block w-full h-auto"
      >
        <defs>
          <linearGradient id="stage-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#f7f9ff" />
            <stop offset="100%" stopColor="#fdfdff" />
          </linearGradient>
        </defs>

        {/* Top label strip — micro caption */}
        <text
          x={VIEW_W / 2}
          y={20}
          fontSize={10}
          fontWeight={700}
          letterSpacing="1.5"
          textAnchor="middle"
          fill="#9aa5c0"
          fontFamily="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif"
        >
          DATA · COMPILED · INTEGRATED · PORTABLE
        </text>

        {/* Arrows (drawn first so cards render on top) */}
        {STAGES.slice(0, -1).map((_, i) => (
          <StageArrow key={`arrow-${i}`} fromX={boxX(i)} />
        ))}

        {/* Stage cards */}
        {STAGES.map((stage, i) => (
          <StageCard key={stage.label} {...stage} x={boxX(i)} />
        ))}

        {/* Bottom annotation line */}
        <text
          x={X_OFFSET}
          y={Y_OFFSET + BOX_H + 28}
          fontSize={11}
          fill="#6b7390"
          fontFamily="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif"
        >
          Source files
        </text>
        <text
          x={X_OFFSET + ROW_W}
          y={Y_OFFSET + BOX_H + 28}
          fontSize={11}
          textAnchor="end"
          fill="#6b7390"
          fontFamily="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif"
        >
          Portable clinical bundle
        </text>
        <line
          x1={X_OFFSET + 76}
          y1={Y_OFFSET + BOX_H + 24}
          x2={X_OFFSET + ROW_W - 110}
          y2={Y_OFFSET + BOX_H + 24}
          stroke="#e7eaf2"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      </svg>
    </div>
  );
}
