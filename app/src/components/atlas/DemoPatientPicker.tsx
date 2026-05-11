import { Activity, ArrowRight, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { mockPatients } from "../../api/mockData";
import { useAccessContext } from "../../context/AccessContext";

type DemoPatientPickerProps = {
  destination: (patientId: string) => string;
  title?: string;
  body?: string;
};

export function DemoPatientPicker({
  destination,
  title = "Continue with a demo patient",
  body = "Use an explicit demo patient to unlock the product without exposing non-demo chart data.",
}: DemoPatientPickerProps) {
  const navigate = useNavigate();
  const { enterDemoPatient, activePatientId } = useAccessContext();

  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-semibold text-[#1c1c1e]">
        <ShieldCheck size={16} className="text-[#0f766e]" />
        {title}
      </div>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
      <div className="mt-4 space-y-3">
        {mockPatients.map((patient) => (
          <button
            key={patient.id}
            onClick={() => {
              enterDemoPatient(patient.id);
              navigate(destination(patient.id));
            }}
            className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
              activePatientId === patient.id
                ? "border-[#4d68ff] bg-[#eef2ff]"
                : "border-[#dfe4ea] bg-white hover:border-[#4d68ff]"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-[#1c1c1e]">{patient.name}</div>
                <div className="mt-1 text-xs text-[#667085]">
                  {Math.round(patient.age_years)}y {patient.gender} · {patient.total_resources.toLocaleString()} resources · {patient.encounter_count} encounters
                </div>
                <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-[#f7f8fb] px-2 py-1 text-[11px] font-medium text-[#52627f]">
                  <Activity size={12} />
                  Demo {patient.complexity_tier.replace(/_/g, " ")}
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-sm font-semibold text-[#3657ff]">
                Open
                <ArrowRight size={14} />
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
