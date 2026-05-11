import { Activity, ArrowRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAccessContext } from "../../context/AccessContext";

type DemoPatientPickerProps = {
  destination: (patientId: string) => string;
  title?: string;
  body?: string;
};

export function DemoPatientPicker({
  destination,
  title = "Continue with a sample chart",
  body = "Open a prepared synthetic record. No real patient data is used.",
}: DemoPatientPickerProps) {
  const navigate = useNavigate();
  const { availableDemoPatients, enterDemoPatient, activePatientId } = useAccessContext();
  const [pendingPatientId, setPendingPatientId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-semibold text-[#1c1c1e]">
        <ShieldCheck size={16} className="text-[#0f766e]" />
        {title}
      </div>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
      {error && (
        <p className="mt-3 text-sm text-[#b42318]">{error}</p>
      )}
      <div className="mt-4 space-y-3">
        {availableDemoPatients.map((patient) => (
          <button
            key={patient.id}
            type="button"
            disabled={pendingPatientId !== null}
            onClick={async (event) => {
              event.preventDefault();
              event.stopPropagation();
              setError(null);
              setPendingPatientId(patient.id);
              try {
                await enterDemoPatient(patient.id);
                navigate(destination(patient.id));
              } catch (cause) {
                setError(
                  cause instanceof Error && cause.message.trim()
                    ? cause.message
                    : "Could not open the sample chart. Try again.",
                );
              } finally {
                setPendingPatientId(null);
              }
            }}
            className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
              activePatientId === patient.id
                ? "border-[#4d68ff] bg-[#eef2ff]"
                : "border-[#dfe4ea] bg-white hover:border-[#4d68ff]"
            } disabled:cursor-not-allowed disabled:opacity-70`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-[#1c1c1e]">{patient.name}</div>
                <div className="mt-1 text-xs text-[#667085]">{patient.description}</div>
                <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-[#f7f8fb] px-2 py-1 text-[11px] font-medium text-[#52627f]">
                  <Activity size={12} />
                  Sample chart
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-sm font-semibold text-[#3657ff]">
                {pendingPatientId === patient.id ? "Opening..." : "Open"}
                <ArrowRight size={14} />
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
