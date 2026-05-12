import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformDrawer } from "./PlatformDrawer";

const {
  clearAccessMock,
  navigateMock,
  useAccessContextMock,
} = vi.hoisted(() => ({
  clearAccessMock: vi.fn(),
  navigateMock: vi.fn(),
  useAccessContextMock: vi.fn(),
}));

vi.mock("../../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("PlatformDrawer", () => {
  beforeEach(() => {
    clearAccessMock.mockReset();
    navigateMock.mockReset();
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      activePatientId: null,
      clearAccess: clearAccessMock,
      isUnlocked: true,
      mode: "authenticated",
      user: {
        id: "user-1",
        email: "test@example.com",
        display_name: "Dr. Test",
        role: "consumer",
      },
    });
  });

  it("routes Home to the signed-in home destination", () => {
    render(
      <PlatformDrawer
        open
        onClose={vi.fn()}
        user={{ initials: "DT", name: "Dr. Test", org: "test@example.com" }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Home" }));

    expect(navigateMock).toHaveBeenCalledWith("/patient-record/sources");
  });

  it("awaits sign out before redirecting", async () => {
    const logout = deferred<void>();
    clearAccessMock.mockReturnValue(logout.promise);

    render(
      <PlatformDrawer
        open
        onClose={vi.fn()}
        user={{ initials: "DT", name: "Dr. Test", org: "test@example.com" }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(clearAccessMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).not.toHaveBeenCalledWith("/", { replace: true });

    logout.resolve();

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/", { replace: true });
    });
  });

  it("uses demo-specific exit copy for demo sessions", () => {
    useAccessContextMock.mockReturnValue({
      activePatientId: "demo-high-risk",
      clearAccess: clearAccessMock,
      isUnlocked: true,
      mode: "demo",
      user: null,
    });

    render(
      <PlatformDrawer
        open
        onClose={vi.fn()}
        user={{ initials: "SP", name: "Sample chart", org: "Synthetic Atlas workspace" }}
      />,
    );

    expect(screen.getByRole("button", { name: "Exit demo" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });
});
