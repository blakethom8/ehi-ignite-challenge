import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAccessContext } from "../context/AccessContext";

type SessionNavigationOptions = {
  onBeforeNavigate?: () => void;
};

type LeaveSessionOptions = SessionNavigationOptions;

export function useSessionActions() {
  const navigate = useNavigate();
  const { clearAccess, exitDemo, mode, user } = useAccessContext();
  const [sessionActionError, setSessionActionError] = useState<string | null>(null);
  const [isSessionActionPending, setIsSessionActionPending] = useState(false);

  const accountSettingsPath = mode === "authenticated" && user ? "/account/settings" : "/account";
  const sessionActionLabel = mode === "demo" ? "Exit demo" : "Sign out";
  const sessionActionPendingLabel = mode === "demo" ? "Leaving demo..." : "Signing out...";

  const clearSessionActionError = useCallback(() => {
    setSessionActionError(null);
  }, []);

  const navigateToAccountSettings = useCallback(
    (options?: SessionNavigationOptions) => {
      options?.onBeforeNavigate?.();
      navigate(accountSettingsPath);
    },
    [accountSettingsPath, navigate],
  );

  const leaveSessionToHome = useCallback(
    async (options?: LeaveSessionOptions) => {
      setSessionActionError(null);
      setIsSessionActionPending(true);
      try {
        if (mode === "demo") {
          await exitDemo();
        } else {
          await clearAccess();
        }
        options?.onBeforeNavigate?.();
        navigate("/", { replace: true });
        return true;
      } catch (error) {
        setSessionActionError(extractErrorMessage(error));
        return false;
      } finally {
        setIsSessionActionPending(false);
      }
    },
    [clearAccess, exitDemo, mode, navigate],
  );

  return useMemo(
    () => ({
      accountSettingsPath,
      clearSessionActionError,
      isSessionActionPending,
      leaveSessionToHome,
      navigateToAccountSettings,
      sessionActionError,
      sessionActionLabel,
      sessionActionPendingLabel,
    }),
    [
      accountSettingsPath,
      clearSessionActionError,
      isSessionActionPending,
      leaveSessionToHome,
      navigateToAccountSettings,
      sessionActionError,
      sessionActionLabel,
      sessionActionPendingLabel,
    ],
  );
}

function extractErrorMessage(error: unknown): string {
  if (!error) return "Something went wrong.";
  if (typeof error === "object" && error !== null) {
    const maybeAxios = error as {
      response?: { data?: { detail?: unknown } };
      message?: string;
    };
    const detail = maybeAxios.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    if (typeof maybeAxios.message === "string" && maybeAxios.message) return maybeAxios.message;
  }
  return "Session action failed.";
}
