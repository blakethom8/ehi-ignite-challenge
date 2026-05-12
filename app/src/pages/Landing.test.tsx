import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Landing } from "./Landing";

const {
  useAccessContextMock,
} = vi.hoisted(() => ({
  useAccessContextMock: vi.fn(),
}));

vi.mock("../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

function renderLanding() {
  return render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  );
}

describe("Landing", () => {
  beforeEach(() => {
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      activePatientId: null,
      activePatientName: null,
      isDemo: false,
      isUnlocked: false,
      user: null,
    });
  });

  it("presents demo as the primary path and keeps account access secondary", () => {
    renderLanding();

    expect(screen.getAllByText("Try demo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Log in / Sign up").length).toBeGreaterThan(0);
    expect(screen.getByText("Atlas data flow")).toBeInTheDocument();
    expect(screen.getAllByText("Harmonize + prepare").length).toBeGreaterThan(0);
    expect(screen.getByText("One patient record. Multiple downstream environments.")).toBeInTheDocument();
    expect(screen.queryByText("Choose a curated patient journey first.")).not.toBeInTheDocument();
    expect(screen.queryByText(/distinct review stories, not a giant browseable sample corpus/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/clinician/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/atlas-demo-password|clinician@atlas\.local/i)).not.toBeInTheDocument();
  });

  it("routes the primary try demo CTAs through the dedicated chooser", () => {
    renderLanding();

    const tryDemoLinks = screen.getAllByRole("link", { name: /try demo/i });
    expect(tryDemoLinks.length).toBeGreaterThan(0);
    for (const link of tryDemoLinks) {
      expect(link).toHaveAttribute("href", "/demo");
    }
  });

  it("does not expose curated patient cards directly on the home page", () => {
    renderLanding();

    expect(screen.queryByRole("link", { name: /surgical review sample/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /trial match sample/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /medication access sample/i })).not.toBeInTheDocument();
  });
});
