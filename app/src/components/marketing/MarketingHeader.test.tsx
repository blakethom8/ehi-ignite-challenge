import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MarketingHeader } from "./MarketingHeader";

const {
  useAccessContextMock,
} = vi.hoisted(() => ({
  useAccessContextMock: vi.fn(),
}));

vi.mock("../../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

describe("MarketingHeader", () => {
  beforeEach(() => {
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      mode: "anonymous",
      activePatientId: null,
      activePatientName: null,
      isDemo: false,
      user: null,
    });
  });

  it("keeps the home link available on the about page", () => {
    render(
      <MemoryRouter>
        <MarketingHeader activeNav="about" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /health-record workspace/i })).toHaveAttribute("href", "/");
    expect(screen.getByText("About Atlas")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /try demo/i })).toHaveAttribute("href", "/demo");
  });

  it("shows the resume workspace link when a patient is active", () => {
    useAccessContextMock.mockReturnValue({
      mode: "demo",
      activePatientId: "demo-trial-match",
      activePatientName: "Demo Patient - Trial Match",
      isDemo: true,
      user: null,
    });

    render(
      <MemoryRouter>
        <MarketingHeader />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /resume.*demo patient - trial match demo/i })).toHaveAttribute(
      "href",
      "/patient-record?patient=demo-trial-match",
    );
    expect(screen.getByRole("link", { name: /health-record workspace/i })).toHaveAttribute(
      "href",
      "/patient-record?patient=demo-trial-match",
    );
  });

  it("switches to an in-app about header when opened from an active workspace", () => {
    useAccessContextMock.mockReturnValue({
      mode: "demo",
      activePatientId: "demo-trial-match",
      activePatientName: "Demo Patient - Trial Match",
      isDemo: true,
      user: null,
    });

    render(
      <MemoryRouter>
        <MarketingHeader activeNav="about" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /health-record workspace/i })).toHaveAttribute(
      "href",
      "/patient-record?patient=demo-trial-match",
    );
    expect(screen.getByRole("link", { name: /back to app/i })).toHaveAttribute(
      "href",
      "/patient-record?patient=demo-trial-match",
    );
    expect(screen.queryByRole("link", { name: /try demo/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /log in \/ sign up/i })).not.toBeInTheDocument();
  });

  it("shows signed-in state for authenticated users instead of anonymous CTas", () => {
    useAccessContextMock.mockReturnValue({
      mode: "authenticated",
      activePatientId: null,
      activePatientName: null,
      isDemo: false,
      user: {
        id: "user-1",
        email: "test@example.com",
        display_name: "Dr. Test",
        role: "consumer",
      },
    });

    render(
      <MemoryRouter>
        <MarketingHeader />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /health-record workspace/i })).toHaveAttribute(
      "href",
      "/patient-record/sources",
    );
    expect(screen.getByText("Signed in as Dr. Test")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /account settings/i })).toHaveAttribute(
      "href",
      "/account/settings",
    );
    expect(screen.getByRole("link", { name: /open workspace/i })).toHaveAttribute(
      "href",
      "/patient-record/sources",
    );
    expect(screen.queryByRole("link", { name: /log in \/ sign up/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /try demo/i })).not.toBeInTheDocument();
  });
});
