import { useSearchParams } from "react-router-dom";
import { Heart, User } from "lucide-react";
import { EmptyState } from "../../components/EmptyState";

export function JourneyPlaceholder() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  if (!patientId) {
    return (
      <EmptyState
        icon={User}
        title="Choose a patient to begin"
        bullets={[
          "Surgical safety panel with allergy and med flags",
          "Longitudinal medication timeline",
          "Evidence-backed natural language Q&A",
        ]}
        stat="1,180 patients available"
        iconBg="#ffd8f4"
        iconColor="#600000"
      />
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="w-16 h-16 rounded-2xl bg-[#ffd8f4] flex items-center justify-center mb-4">
        <Heart size={28} className="text-[#600000]" />
      </div>
      <h2 className="text-lg font-semibold text-[#1c1c1e] mb-1">Patient Journey</h2>
      <p className="text-sm text-[#555a6a] max-w-xs">
        Clinician-facing surgical briefing view. Coming next — Safety Panel, Medication Timeline, and NL Search.
      </p>
    </div>
  );
}
