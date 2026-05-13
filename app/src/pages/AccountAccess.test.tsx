import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccountAccessPage } from "./AccountAccess";

const {
  navigateMock,
  signInMock,
  signUpMock,
  useAccessContextMock,
} = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  signInMock: vi.fn(),
  signUpMock: vi.fn(),
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

const authSession = {
  mode: "authenticated" as const,
  user: {
    id: "user-1",
    email: "test@example.com",
    display_name: "Dr. Test",
    role: "consumer" as const,
  },
  active_patient_id: null,
  active_patient_name: null,
  active_demo_patient: null,
  expires_at: null,
  available_demo_patients: [],
};

function renderAccountAccess(initialEntry = "/account") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AccountAccessPage />
    </MemoryRouter>,
  );
}

describe("AccountAccessPage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    signInMock.mockReset();
    signUpMock.mockReset();
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      activePatientId: null,
      isLoading: false,
      isUnlocked: false,
      mode: "anonymous",
      signIn: signInMock,
      signUp: signUpMock,
      user: null,
    });
  });

  it("logs in existing accounts without exposing seeded credentials", async () => {
    signInMock.mockResolvedValue(authSession);
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
    expect(navigateMock).toHaveBeenCalledWith("/patient-record/sources", { replace: true });
    expect(screen.queryByText(/clinician@atlas\.local|atlas-demo-password/i)).not.toBeInTheDocument();
  });

  it("creates a new account from the signup tab", async () => {
    signUpMock.mockResolvedValue(authSession);
    renderAccountAccess();

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Dr. Test" },
    });
    fireEvent.change(screen.getByLabelText("Signup email"), {
      target: { value: "newuser@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Signup password"), {
      target: { value: "longenoughpw" },
    });

    const submitButtons = screen.getAllByRole("button", { name: /create account/i });
    fireEvent.click(submitButtons[submitButtons.length - 1]);

    await waitFor(() => {
      expect(signUpMock).toHaveBeenCalledWith(
        "newuser@example.com",
        "longenoughpw",
        "Dr. Test",
      );
    });
    expect(navigateMock).toHaveBeenCalledWith("/patient-record/sources", { replace: true });
  });

  it("keeps an active patient context when a signed-in account logs in again", async () => {
    signInMock.mockResolvedValue({
      ...authSession,
      active_patient_id: "patient-123",
    });
    useAccessContextMock.mockReturnValue({
      activePatientId: "patient-123",
      isLoading: false,
      isUnlocked: false,
      mode: "authenticated",
      signIn: signInMock,
      signUp: signUpMock,
      user: null,
    });
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
    expect(navigateMock).toHaveBeenCalledWith("/patient-record?patient=patient-123", { replace: true });
  });

  it("does not carry demo patient context into an authenticated login", async () => {
    signInMock.mockResolvedValue(authSession);
    useAccessContextMock.mockReturnValue({
      activePatientId: "demo-high-risk",
      isLoading: false,
      isUnlocked: true,
      mode: "demo",
      signIn: signInMock,
      signUp: signUpMock,
      user: null,
    });
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
    expect(navigateMock).toHaveBeenCalledWith("/patient-record/sources", { replace: true });
  });

  it("resumes the requested destination after login when next is present", async () => {
    signInMock.mockResolvedValue(authSession);
    renderAccountAccess("/account?next=%2Fcaspian%3Fpatient%3Dpatient-123");

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "private-password" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Log in" }).at(-1)!);

    await waitFor(() => {
      expect(signInMock).toHaveBeenCalledWith("person@example.com", "private-password");
    });
    expect(navigateMock).toHaveBeenCalledWith("/caspian?patient=patient-123", { replace: true });
  });

  it("disables the signup submit button while required fields are incomplete", () => {
    renderAccountAccess();

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    const submitButtons = screen.getAllByRole("button", { name: /create account/i });
    const submit = submitButtons[submitButtons.length - 1];
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Dr. Test" },
    });
    fireEvent.change(screen.getByLabelText("Signup email"), {
      target: { value: "newuser@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Signup password"), {
      target: { value: "short" },
    });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Signup password"), {
      target: { value: "longenough" },
    });
    expect(submit).not.toBeDisabled();
  });

  it("redirects authenticated users away from the login/signup form", () => {
    useAccessContextMock.mockReturnValue({
      activePatientId: null,
      isLoading: false,
      isUnlocked: true,
      mode: "authenticated",
      signIn: signInMock,
      signUp: signUpMock,
      user: {
        id: "user-1",
        email: "test@example.com",
        display_name: "Dr. Test",
        role: "consumer",
      },
    });

    render(
      <MemoryRouter initialEntries={["/account"]}>
        <Routes>
          <Route path="/account" element={<AccountAccessPage />} />
          <Route path="/account/settings" element={<div>Account settings</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Account settings")).toBeInTheDocument();
  });
});
