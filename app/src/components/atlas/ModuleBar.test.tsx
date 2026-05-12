import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthSessionResponse } from "../../types";
import { AccessProvider } from "../../context/AccessContext";
import { ModuleBar } from "./ModuleBar";

const { enterDemoMock, exitDemoMock, getAuthSessionMock, logoutMock, getCapabilitiesMock } = vi.hoisted(() => ({
  enterDemoMock: vi.fn(),
  exitDemoMock: vi.fn(),
  getAuthSessionMock: vi.fn<() => Promise<AuthSessionResponse>>(),
  logoutMock: vi.fn(),
  getCapabilitiesMock: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: {
    getAuthSession: getAuthSessionMock,
    getCapabilities: getCapabilitiesMock,
    login: vi.fn(),
    logout: logoutMock,
    enterDemo: enterDemoMock,
    exitDemo: exitDemoMock,
    selectActivePatient: vi.fn(),
  },
}));

describe("ModuleBar", () => {
  beforeEach(() => {
    getAuthSessionMock.mockResolvedValue({
      mode: "demo",
      user: null,
      active_patient_id: "demo-high-risk",
      active_patient_name: "Demo Patient - Surgical Review",
      expires_at: null,
      available_demo_patients: [
        {
          id: "demo-high-risk",
          name: "Demo Patient - Surgical Review",
          description: "High-signal pre-op review demo.",
        },
        {
          id: "demo-trial-match",
          name: "Demo Patient - Trial Match",
          description: "Referral and oncology review demo.",
        },
      ],
    });
    enterDemoMock.mockResolvedValue({
      mode: "demo",
      user: null,
      active_patient_id: "demo-trial-match",
      active_patient_name: "Demo Patient - Trial Match",
      expires_at: null,
      available_demo_patients: [
        {
          id: "demo-high-risk",
          name: "Demo Patient - Surgical Review",
          description: "High-signal pre-op review demo.",
        },
        {
          id: "demo-trial-match",
          name: "Demo Patient - Trial Match",
          description: "Referral and oncology review demo.",
        },
      ],
    });
    exitDemoMock.mockResolvedValue({
      mode: "anonymous",
      user: null,
      active_patient_id: null,
      active_patient_name: null,
      expires_at: null,
      available_demo_patients: [],
    });
    logoutMock.mockResolvedValue({
      mode: "anonymous",
      user: null,
      active_patient_id: null,
      active_patient_name: null,
      expires_at: null,
      available_demo_patients: [],
    });
    getCapabilitiesMock.mockResolvedValue({
      mode: "demo",
      can_use_caspian: true,
      can_edit_caspian_user_files: false,
      can_write_caspian_notes: false,
      can_run_workflows: true,
      can_use_aggregation_uploads: true,
      can_use_aggregation_profiles: false,
      can_use_harmonize: false,
      can_use_guest_harmonization: true,
      can_use_assistant_tools_write: false,
      show_caspian_seed_files: true,
      persistence_scope: "browser-ephemeral",
    });
  });

  it("preserves the active patient context in top-bar module links", async () => {
    render(
      <MemoryRouter initialEntries={["/patient-record?patient=demo-high-risk"]}>
        <AccessProvider>
          <ModuleBar
            activeModule="patient-record"
            onSelect={vi.fn()}
            workspaceId="caspian"
            onSwitchWorkspace={vi.fn()}
            onOpenDrawer={vi.fn()}
            user={{ initials: "RP", name: "R. Patel", org: "Mercy Medical Group" }}
          />
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "FHIR Charts" })).toHaveAttribute(
        "href",
        "/fhir-charts?patient=demo-high-risk",
      );
      expect(screen.getByRole("link", { name: "Caspian" })).toHaveAttribute(
        "href",
        "/caspian?patient=demo-high-risk",
      );
      expect(screen.getByRole("link", { name: "Plugins" })).toHaveAttribute(
        "href",
        "/workspaces?patient=demo-high-risk",
      );
      expect(screen.queryByRole("link", { name: "Home" })).not.toBeInTheDocument();
    });
  });

  it("keeps the active demo chip concise", async () => {
    render(
      <MemoryRouter initialEntries={["/patient-record?patient=demo-high-risk"]}>
        <AccessProvider>
          <ModuleBar
            activeModule="patient-record"
            onSelect={vi.fn()}
            workspaceId="caspian"
            onSwitchWorkspace={vi.fn()}
            onOpenDrawer={vi.fn()}
            user={{ initials: "RP", name: "R. Patel", org: "Mercy Medical Group" }}
          />
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Demo Patient - Surgical Review")).toBeInTheDocument();
      expect(screen.getByText("Demo")).toBeInTheDocument();
      expect(screen.queryByText("Synthetic sample chart")).not.toBeInTheDocument();
    });
  });

  it("opens a demo switcher from the active demo chip", async () => {
    render(
      <MemoryRouter initialEntries={["/patient-record?patient=demo-high-risk"]}>
        <AccessProvider>
          <ModuleBar
            activeModule="patient-record"
            onSelect={vi.fn()}
            workspaceId="caspian"
            onSwitchWorkspace={vi.fn()}
            onOpenDrawer={vi.fn()}
            user={{ initials: "RP", name: "R. Patel", org: "Mercy Medical Group" }}
          />
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Demo Patient - Surgical Review")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Demo Patient - Surgical Review/i }));

    expect(screen.getByText("DEMO PATIENTS")).toBeInTheDocument();
    expect(screen.getByText("Demo Patient - Trial Match")).toBeInTheDocument();
    expect(screen.getByText("Exit demo space")).toBeInTheDocument();
  });

  it("routes the app title to the authenticated home destination and exposes sign out", async () => {
    getAuthSessionMock.mockResolvedValue({
      mode: "authenticated",
      user: {
        id: "user-1",
        email: "test@example.com",
        display_name: "Dr. Test",
        role: "consumer",
      },
      active_patient_id: null,
      active_patient_name: null,
      expires_at: null,
      available_demo_patients: [],
    });

    render(
      <MemoryRouter initialEntries={["/patient-record/sources"]}>
        <AccessProvider>
          <ModuleBar
            homeHref="/patient-record/sources"
            activeModule="patient-record"
            onSelect={vi.fn()}
            workspaceId="caspian"
            onSwitchWorkspace={vi.fn()}
            onOpenDrawer={vi.fn()}
            user={{ initials: "DT", name: "Dr. Test", org: "test@example.com" }}
          />
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /ehi atlas/i })).toHaveAttribute(
        "href",
        "/patient-record/sources",
      );
      expect(screen.getByRole("link", { name: "FHIR Charts" })).toHaveAttribute(
        "href",
        "/patient-record/sources",
      );
      expect(screen.getByRole("link", { name: "Caspian" })).toHaveAttribute(
        "href",
        "/patient-record/sources",
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => {
      expect(logoutMock).toHaveBeenCalledTimes(1);
    });
  });
});
