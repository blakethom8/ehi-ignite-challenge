import { ArrowLeft, ArrowRight, Clock3 } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useAccessContext } from "../../context/AccessContext";
import { useCanManageOwnAccount, useCapabilities } from "../../hooks/useCapabilities";
import { buildAccountAccessPath, buildDemoSelectionPath } from "../../routing";
import { resolveSessionHomePath } from "../../sessionRouting";

type MarketingHeaderProps = {
  activeNav?: "about" | null;
};

export function MarketingHeader({ activeNav = null }: MarketingHeaderProps) {
  const location = useLocation();
  const { activePatientId, activePatientName, isDemo, mode, user } = useAccessContext();
  const capabilities = useCapabilities();
  const canManageAccount = useCanManageOwnAccount();
  const isInAppAbout = activeNav === "about" && Boolean(activePatientId);
  const resumeHref = resolveSessionHomePath(mode, activePatientId);
  const accountHref = canManageAccount && user
    ? "/account/settings"
    : buildAccountAccessPath(`${location.pathname}${location.search}`);
  const isAuthenticated = capabilities.mode === "authenticated" && Boolean(user);

  return (
    <header className="border-b border-[#dde5ef] bg-[rgba(255,255,255,0.88)] backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-5">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7f8aa0]">
            Atlas
          </p>
          <div className="mt-1 flex min-w-0 items-center gap-2 text-lg font-semibold text-[#18202b]">
            <Link to={resumeHref} className="truncate transition-colors hover:text-[#3657ff]">
              Health-record workspace
            </Link>
            {activePatientId && !isInAppAbout ? (
              <Link
                to={resumeHref}
                className="hidden min-w-0 items-center gap-2 text-sm font-medium text-[#62728d] transition-colors hover:text-[#3657ff] lg:inline-flex"
              >
                <span className="text-[#a6b1c4]">/</span>
                <Clock3 size={14} className="text-[#4d68ff]" />
                <span className="font-semibold text-[#33415b]">Resume</span>
                <span className="truncate">
                  {activePatientName ?? activePatientId}
                  {isDemo ? " demo" : ""}
                </span>
              </Link>
            ) : null}
            {isInAppAbout ? (
              <span className="hidden min-w-0 items-center gap-2 text-sm font-medium text-[#62728d] lg:inline-flex">
                <span className="text-[#a6b1c4]">/</span>
                <span className="font-semibold text-[#33415b]">About Atlas</span>
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isInAppAbout ? (
            <Link
              to={resumeHref}
              className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
            >
              <ArrowLeft size={16} />
              Back to app
            </Link>
          ) : null}
          {activeNav === "about" ? (
            <span className="hidden rounded-2xl border border-[#cdd8ff] bg-[#eef2ff] px-4 py-2.5 text-sm font-semibold text-[#3657ff] sm:inline-flex">
              About Atlas
            </span>
          ) : (
            <Link
              to="/using-atlas"
              className="hidden rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] sm:inline-flex"
            >
              About Atlas
            </Link>
          )}
          {!isInAppAbout ? (
            <>
              {isAuthenticated ? (
                <>
                  <div className="hidden rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] lg:inline-flex">
                    Signed in as {user?.display_name}
                  </div>
                  <Link
                    to={accountHref}
                    className="hidden rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] sm:inline-flex"
                  >
                    Account settings
                  </Link>
                  <Link
                    to={resumeHref}
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(77,104,255,0.22)] transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    Open workspace
                    <ArrowRight size={16} />
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    to={accountHref}
                    className="hidden rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] sm:inline-flex"
                  >
                    Log in / Sign up
                  </Link>
                  <Link
                    to={buildDemoSelectionPath()}
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(77,104,255,0.22)] transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    Try demo
                    <ArrowRight size={16} />
                  </Link>
                </>
              )}
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
