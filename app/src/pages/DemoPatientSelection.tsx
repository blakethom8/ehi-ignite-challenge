import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { DemoPatientPicker } from "../components/atlas/DemoPatientPicker";
import { useAccessContext } from "../context/AccessContext";
import { canManageOwnAccount, useCapabilities } from "../hooks/useCapabilities";
import { resolveDemoDestination, withPatientContext } from "../routing";

export function DemoPatientSelection() {
  const [searchParams] = useSearchParams();
  const { activePatientId, activePatientName, isDemo, mode } = useAccessContext();
  const capabilities = useCapabilities();
  const prioritizedPatientId = searchParams.get("patient");
  const destination = resolveDemoDestination(searchParams.get("next"));

  if (canManageOwnAccount(capabilities)) {
    const authenticatedDestination = activePatientId
      ? withPatientContext("/patient-record", activePatientId, { mode })
      : "/patient-record/sources";
    return <Navigate replace to={authenticatedDestination} />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f9ff_0%,#eef3f8_42%,#e9eef4_100%)] text-[#18202b]">
      <header className="border-b border-[#dde5ef] bg-[rgba(255,255,255,0.88)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7f8aa0]">
              Atlas
            </p>
            <p className="mt-1 text-lg font-semibold text-[#18202b]">
              Choose a demo patient
            </p>
          </div>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
          >
            <ArrowLeft size={16} />
            Back to home
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-10">
        <section className="mx-auto max-w-4xl rounded-[32px] border border-[#cad6ff] bg-[rgba(255,255,255,0.84)] p-7 shadow-[0_22px_70px_rgba(77,104,255,0.08)] sm:p-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
            Synthetic demo patients
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-[-0.04em] text-[#18202b] sm:text-5xl">
            Select one patient to open in Atlas.
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-[#5f6f89]">
            Each option opens the main Atlas chart workspace first, then you can move into FHIR Charts,
            Caspian, or plugins with the same patient context.
          </p>

          {isDemo && activePatientId && (
            <div className="mt-6 rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.82)] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4d68ff]">
                Current sample
              </p>
              <p className="mt-2 text-lg font-semibold text-[#18202b]">
                {activePatientName ?? activePatientId}
              </p>
              <div className="mt-4">
                <Link
                  to={withPatientContext(destination, activePatientId, { mode: "demo" })}
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#eef2ff] px-4 py-2.5 text-sm font-semibold text-[#3657ff]"
                >
                  Continue current sample
                  <ArrowRight size={15} />
                </Link>
              </div>
            </div>
          )}

          <div className="mt-8">
            <DemoPatientPicker
              destination={(patientId) => withPatientContext(destination, patientId, { mode: "demo" })}
              prioritizedPatientId={prioritizedPatientId}
              title="Select a synthetic patient"
              body="Choose one of the curated demo patients below."
            />
          </div>
        </section>
      </main>
    </div>
  );
}
