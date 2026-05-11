import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessProvider } from "../../context/AccessContext";
import { ModuleBar } from "./ModuleBar";

describe("ModuleBar", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem(
      "atlas:access",
      JSON.stringify({ mode: "demo", activePatientId: "demo-high-risk" }),
    );
  });

  it("preserves the active patient context in top-bar module links", () => {
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
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  });
});
