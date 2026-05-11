import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessProvider } from "../../context/AccessContext";
import type { AuthSessionResponse } from "../../types";
import type { Workspace } from "./types";
import { ContextStrip } from "./ContextStrip";

const { getAuthSessionMock } = vi.hoisted(() => ({
  getAuthSessionMock: vi.fn<() => Promise<AuthSessionResponse>>(),
}));

vi.mock("../../api/client", () => ({
  api: {
    getAuthSession: getAuthSessionMock,
    login: vi.fn(),
    logout: vi.fn(),
    enterDemo: vi.fn(),
    selectActivePatient: vi.fn(),
  },
}));

const clinicalWorkspace: Workspace = {
  id: "caspian",
  family: "clinical",
  title: "Caspian",
  subtitle: "First-party clinical workspace",
  icon: "Stethoscope",
  color: "#1d4ed8",
  tint: "rgba(29, 78, 216, 0.10)",
  boundary: "Private patient boundary",
  boundaryTone: "ok",
};

const pluginWorkspace: Workspace = {
  id: "trial-finder",
  family: "plugin",
  title: "Trial Finder",
  subtitle: "Plugin",
  icon: "Telescope",
  color: "#4338ca",
  tint: "rgba(67, 56, 202, 0.10)",
  boundary: "Consented external",
  boundaryTone: "warn",
  vendor: "Helix Clinical",
  version: "2.4.1",
  permissions: ["read patient anchors"],
  runState: "running",
  runStep: "trial.search",
  runElapsed: "2m 10s",
};

describe("ContextStrip", () => {
  beforeEach(() => {
    getAuthSessionMock.mockReset();
  });

  it("renders access-backed Caspian patient chrome instead of fixture patient identity", async () => {
    getAuthSessionMock.mockResolvedValue({
      mode: "authenticated",
      user: {
        id: "user_1",
        email: "clinician@atlas.local",
        display_name: "Atlas Clinician",
        role: "clinician",
      },
      active_patient_id: "patient-123",
      active_patient_name: "Patient 123",
      expires_at: null,
      available_demo_patients: [],
    });

    render(
      <MemoryRouter>
        <AccessProvider>
          <ContextStrip workspace={clinicalWorkspace} />
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Patient 123")).toBeInTheDocument();
      expect(screen.getByText("Signed in as Atlas Clinician")).toBeInTheDocument();
      expect(screen.queryByText("M. Hollister")).not.toBeInTheDocument();
    });
  });

  it("anchors plugin chrome to the active patient context", async () => {
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
      ],
    });

    render(
      <MemoryRouter>
        <AccessProvider>
          <ContextStrip workspace={pluginWorkspace} />
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Demo anchor · Demo Patient - Surgical Review")).toBeInTheDocument();
      expect(screen.queryByText(/Hollister/)).not.toBeInTheDocument();
    });
  });
});
