import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoPatientPicker } from "./DemoPatientPicker";

const {
  navigateMock,
  enterDemoPatientMock,
  useAccessContextMock,
} = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  enterDemoPatientMock: vi.fn<(patientId: string) => Promise<void>>(),
  useAccessContextMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("../../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

function deferredPromise<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("DemoPatientPicker", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    enterDemoPatientMock.mockReset();
    useAccessContextMock.mockReset();
    useAccessContextMock.mockReturnValue({
      availableDemoPatients: [
        {
          id: "demo-high-risk",
          name: "Demo Patient - Surgical Review",
          description: "High-signal pre-op review demo.",
        },
      ],
      enterDemoPatient: enterDemoPatientMock,
      activePatientId: null,
    });
  });

  it("waits for demo access to complete before navigating", async () => {
    const deferred = deferredPromise<void>();
    enterDemoPatientMock.mockReturnValue(deferred.promise);

    render(
      <DemoPatientPicker
        destination={(patientId) => `/patient-record?patient=${patientId}`}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /open/i }));

    expect(enterDemoPatientMock).toHaveBeenCalledWith("demo-high-risk");
    expect(navigateMock).not.toHaveBeenCalled();
    expect(screen.getByText("Opening...")).toBeInTheDocument();

    deferred.resolve();

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/patient-record?patient=demo-high-risk");
    });
  });

  it("surfaces an error instead of navigating on session failure", async () => {
    enterDemoPatientMock.mockRejectedValue(new Error("Session unavailable"));

    render(
      <DemoPatientPicker
        destination={(patientId) => `/patient-record?patient=${patientId}`}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /open/i }));

    await waitFor(() => {
      expect(screen.getByText("Session unavailable")).toBeInTheDocument();
    });
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
