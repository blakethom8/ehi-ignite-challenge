import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Landing } from "./Landing";

const {
  enterDemoPatientMock,
  navigateMock,
  useAccessContextMock,
} = vi.hoisted(() => ({
  enterDemoPatientMock: vi.fn<(patientId: string) => Promise<void>>(),
  navigateMock: vi.fn(),
  useAccessContextMock: vi.fn(),
}));

vi.mock("../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

function renderLanding() {
  return render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  );
}

describe("Landing", () => {
  beforeEach(() => {
    enterDemoPatientMock.mockReset();
    navigateMock.mockReset();
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      activePatientId: null,
      activePatientName: null,
      enterDemoPatient: enterDemoPatientMock,
      isDemo: false,
      isLoading: false,
      isUnlocked: false,
      user: null,
    });
  });

  it("presents demo as the primary path and keeps account access secondary", () => {
    renderLanding();

    expect(screen.getAllByText("Try demo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Log in / Sign up").length).toBeGreaterThan(0);
    expect(screen.getByText("Start with a prepared sample chart.")).toBeInTheDocument();
    expect(screen.getByText("These are synthetic records. No real patient data is used.")).toBeInTheDocument();
    expect(screen.queryByText(/clinician/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/atlas-demo-password|clinician@atlas\.local/i)).not.toBeInTheDocument();
  });

  it("starts the selected sample workspace before navigating", async () => {
    enterDemoPatientMock.mockResolvedValue();
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: /surgical review sample/i }));

    expect(enterDemoPatientMock).toHaveBeenCalledWith("demo-high-risk");

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/patient-record?patient=demo-high-risk");
    });
  });
});
