import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoPatientSelection } from "./DemoPatientSelection";
import type { Capabilities } from "../types";

const {
  navigateMock,
  enterDemoPatientMock,
  useAccessContextMock,
} = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  enterDemoPatientMock: vi.fn<(patientId: string) => Promise<void>>(),
  useAccessContextMock: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

function renderDemoPatientSelection(initialEntry = "/demo") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <DemoPatientSelection />
    </MemoryRouter>,
  );
}

function capabilitiesForMode(mode: Capabilities["mode"]): Capabilities {
  return {
    mode,
    can_use_caspian: mode !== "anonymous" && mode !== "guest",
    can_edit_caspian_user_files: false,
    can_write_caspian_notes: false,
    can_run_workflows: false,
    can_use_aggregation_uploads: mode === "authenticated",
    can_use_aggregation_profiles: mode === "authenticated",
    can_use_harmonize: mode === "authenticated",
    can_use_guest_harmonization: mode === "guest",
    can_use_assistant_tools_write: false,
    show_caspian_seed_files: false,
    persistence_scope: mode === "authenticated" ? "browser-persistent" : mode === "demo" ? "browser-ephemeral" : "none",
  };
}

describe("DemoPatientSelection", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    enterDemoPatientMock.mockReset();
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      mode: "anonymous",
      capabilities: capabilitiesForMode("anonymous"),
      activePatientId: null,
      activePatientName: null,
      availableDemoPatients: [
        {
          id: "demo-high-risk",
          name: "Demo Patient - Surgical Review",
          description: "High-signal pre-op review demo.",
        },
        {
          id: "demo-trial-match",
          name: "Demo Patient - Trial Match",
          description: "Curated oncology-style demo.",
        },
      ],
      enterDemoPatient: enterDemoPatientMock,
      isDemo: false,
    });
  });

  it("routes a selected patient into Patient Record by default", async () => {
    enterDemoPatientMock.mockResolvedValue();
    renderDemoPatientSelection();

    fireEvent.click(screen.getByRole("button", { name: /demo patient - surgical review/i }));

    expect(enterDemoPatientMock).toHaveBeenCalledWith("demo-high-risk");

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/patient-record?patient=demo-high-risk");
    });
  });

  it("preserves an internal next route when present", async () => {
    enterDemoPatientMock.mockResolvedValue();
    renderDemoPatientSelection("/demo?next=%2Fworkspaces&patient=demo-trial-match");

    fireEvent.click(screen.getByRole("button", { name: /demo patient - trial match/i }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/workspaces?patient=demo-trial-match");
    });
  });

  it("shows the prioritized patient first in the picker when the route preselects one", () => {
    renderDemoPatientSelection("/demo?patient=demo-trial-match");

    const patientButtons = screen
      .getAllByRole("button")
      .filter((button) => button.textContent?.includes("Demo Patient -"));
    expect(patientButtons[0]).toHaveTextContent("Demo Patient - Trial Match");
  });

  it("redirects authenticated accounts away from demo selection", () => {
    useAccessContextMock.mockReturnValue({
      mode: "authenticated",
      capabilities: capabilitiesForMode("authenticated"),
      activePatientId: null,
      activePatientName: null,
      availableDemoPatients: [],
      enterDemoPatient: enterDemoPatientMock,
      isDemo: false,
    });

    render(
      <MemoryRouter initialEntries={["/demo"]}>
        <Routes>
          <Route path="/demo" element={<DemoPatientSelection />} />
          <Route path="/patient-record/sources" element={<div>Upload files</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Upload files")).toBeInTheDocument();
  });
});
