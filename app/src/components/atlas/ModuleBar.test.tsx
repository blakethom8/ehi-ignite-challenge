import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthSessionResponse } from "../../types";
import { AccessProvider } from "../../context/AccessContext";
import { ModuleBar } from "./ModuleBar";

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
      ],
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
});
