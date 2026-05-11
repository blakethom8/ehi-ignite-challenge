import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccountAccessPage } from "./AccountAccess";

const {
  navigateMock,
  signInMock,
  useAccessContextMock,
} = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  signInMock: vi.fn<(email: string, password: string) => Promise<void>>(),
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

function renderAccountAccess() {
  return render(
    <MemoryRouter>
      <AccountAccessPage />
    </MemoryRouter>,
  );
}

describe("AccountAccessPage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    signInMock.mockReset();
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      activePatientId: null,
      isLoading: false,
      isUnlocked: false,
      signIn: signInMock,
      user: null,
    });
  });

  it("logs in existing accounts without exposing seeded credentials", async () => {
    signInMock.mockResolvedValue();
    renderAccountAccess();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "private-password" },
    });
    const loginButtons = screen.getAllByRole("button", { name: "Log in" });
    fireEvent.click(loginButtons[loginButtons.length - 1]);

    await waitFor(() => {
      expect(signInMock).toHaveBeenCalledWith("person@example.com", "private-password");
    });
    expect(navigateMock).toHaveBeenCalledWith("/records-pool");
    expect(screen.queryByText(/clinician@atlas\.local|atlas-demo-password/i)).not.toBeInTheDocument();
  });

  it("shows an honest create-account placeholder", () => {
    renderAccountAccess();

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(screen.getByText("Create account coming soon")).toBeInTheDocument();
    expect(screen.getByText(/Public account creation is not wired to the backend/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create account now/i })).not.toBeInTheDocument();
  });
});
