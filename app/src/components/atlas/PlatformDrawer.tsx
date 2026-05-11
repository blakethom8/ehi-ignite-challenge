import { useEffect } from "react";
import {
  FileText,
  HelpCircle,
  LogOut,
  MessageSquareText,
  UserRound,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { User } from "./types";
import { useAccessContext } from "../../context/AccessContext";

type PlatformDrawerProps = {
  open: boolean;
  onClose: () => void;
  user: User;
};

export function PlatformDrawer({ open, onClose, user }: PlatformDrawerProps) {
  const navigate = useNavigate();
  const { clearAccess } = useAccessContext();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-[200] animate-[fade-in_120ms_ease]"
        style={{ background: "rgba(15,23,42,0.32)" }}
      />
      <aside
        className="fixed bottom-0 left-0 top-0 z-[201] flex w-[296px] flex-col"
        style={{
          background: "var(--surface-1)",
          borderRight: "1px solid var(--line-1)",
          boxShadow: "0 12px 32px rgb(15 23 42 / 0.18)",
          animation: "slide-in-left 160ms ease-out",
        }}
      >
        <div className="flex items-center justify-between px-3.5 pb-2.5 pt-3.5">
          <div
            className="flex items-center gap-2 text-[13px]"
            style={{ color: "var(--ink-1)" }}
          >
            <div
              className="grid h-[22px] w-[22px] place-items-center rounded-[5px] text-[10px] font-bold tracking-wide text-white"
              style={{
                background:
                  "linear-gradient(135deg, var(--action) 0%, var(--action-press) 100%)",
              }}
            >
              EI
            </div>
            <strong>EHI Ignite</strong>
          </div>
          <button
            onClick={onClose}
            className="grid h-[26px] w-[26px] place-items-center rounded-[5px] hover:bg-[var(--surface-2)]"
            style={{ color: "var(--ink-3)" }}
            title="Close"
          >
            <X className="h-3.5 w-3.5" strokeWidth={1.5} />
          </button>
        </div>
        <div
          className="mb-1.5 flex items-center gap-2.5 border-b px-3.5 pb-4 pt-2.5"
          style={{ borderColor: "var(--line-1)" }}
        >
          <div
            className="grid h-9 w-9 place-items-center rounded-full text-[13px] font-semibold text-white"
            style={{ background: "var(--action)" }}
          >
            {user.initials}
          </div>
          <div>
            <div
              className="text-[13px] font-semibold"
              style={{ color: "var(--ink-1)" }}
            >
              {user.name}
            </div>
            <div
              className="mt-px text-[11.5px]"
              style={{ color: "var(--ink-3)" }}
            >
              {user.org}
            </div>
          </div>
        </div>
        <DrawerSection>
          <DrawerItem
            icon={<UserRound className="h-3.5 w-3.5" strokeWidth={1.5} />}
            onClick={() => {
              onClose();
              navigate("/");
            }}
          >
            Home
          </DrawerItem>
          <DrawerItem
            icon={<FileText className="h-3.5 w-3.5" strokeWidth={1.5} />}
            onClick={() => {
              onClose();
              navigate("/records-pool");
            }}
          >
            Switch patient
          </DrawerItem>
        </DrawerSection>
        <div
          className="mx-3.5 my-1.5 h-px"
          style={{ background: "var(--line-1)" }}
        />
        <DrawerSection>
          <DrawerItem
            icon={<HelpCircle className="h-3.5 w-3.5" strokeWidth={1.5} />}
            onClick={() => {
              onClose();
              navigate("/using-atlas");
            }}
          >
            About Atlas
          </DrawerItem>
          <DrawerItem
            icon={<FileText className="h-3.5 w-3.5" strokeWidth={1.5} />}
            onClick={() => {
              onClose();
              navigate("/architecture");
            }}
          >
            System architecture
          </DrawerItem>
          <DrawerItem
            icon={<MessageSquareText className="h-3.5 w-3.5" strokeWidth={1.5} />}
            onClick={() => {
              onClose();
              navigate("/learn");
            }}
          >
            Technical labs
          </DrawerItem>
        </DrawerSection>
        <div className="flex-1" />
        <div
          className="border-t px-1.5 pb-3 pt-1.5"
          style={{ borderColor: "var(--line-1)" }}
        >
          <DrawerItem
            icon={<LogOut className="h-3.5 w-3.5" strokeWidth={1.5} />}
            muted
            onClick={() => {
              clearAccess();
              onClose();
              navigate("/");
            }}
          >
            Exit demo / sign out
          </DrawerItem>
        </div>
      </aside>
      <style>{`
        @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slide-in-left { from { transform: translateX(-12px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
      `}</style>
    </>
  );
}

function DrawerSection({ children }: { children: React.ReactNode }) {
  return <div className="px-1.5 py-1">{children}</div>;
}

function DrawerItem({
  icon,
  children,
  muted = false,
  onClick,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  muted?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full cursor-pointer items-center gap-2.5 rounded-[5px] px-2.5 py-2 text-[12.5px] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--ink-1)]"
      style={{ color: muted ? "var(--ink-3)" : "var(--ink-2)" }}
    >
      {icon}
      {children}
    </button>
  );
}
