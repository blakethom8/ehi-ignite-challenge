import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AxiosError } from "axios";
import { PluginsIndex } from "./Index";

const {
  useAccessContextMock,
  useInstalledManifestsMock,
} = vi.hoisted(() => ({
  useAccessContextMock: vi.fn(),
  useInstalledManifestsMock: vi.fn(),
}));

vi.mock("../../context/AccessContext", () => ({
  useAccessContext: useAccessContextMock,
}));

vi.mock("../../components/atlas/manifests", () => ({
  useInstalledManifests: useInstalledManifestsMock,
}));

vi.mock("../../components/atlas/DemoPatientPicker", () => ({
  DemoPatientPicker: () => <div data-testid="demo-picker">demo picker</div>,
}));

function renderPluginsIndex() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PluginsIndex />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PluginsIndex", () => {
  beforeEach(() => {
    useAccessContextMock.mockReset();
    useInstalledManifestsMock.mockReset();
  });

  it("shows a sample-first start state before loading plugins when the session is locked", () => {
    useAccessContextMock.mockReturnValue({ isUnlocked: false });
    useInstalledManifestsMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
      refetch: vi.fn(),
    });

    renderPluginsIndex();

    expect(
      screen.getByText("Start a sample or account workspace before opening plugins."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("demo-picker")).toBeInTheDocument();
  });

  it("renders a truthful unauthorized state instead of an empty marketplace", () => {
    useAccessContextMock.mockReturnValue({ isUnlocked: true });
    useInstalledManifestsMock.mockReturnValue({
      data: undefined,
      error: {
        isAxiosError: true,
        response: {
          data: {},
          status: 401,
          statusText: "Unauthorized",
          headers: {},
          config: { headers: {} },
        },
      } as AxiosError,
      isError: true,
      isLoading: false,
      refetch: vi.fn(),
    });

    renderPluginsIndex();

    expect(
      screen.getByText("Refresh access before opening plugin tools."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/No plugins installed|build_example_plugins/i),
    ).not.toBeInTheDocument();
  });

  it("uses a neutral empty state when the backend returns no installed plugins", () => {
    useAccessContextMock.mockReturnValue({ isUnlocked: true });
    useInstalledManifestsMock.mockReturnValue({
      data: [],
      error: null,
      isError: false,
      isLoading: false,
      refetch: vi.fn(),
    });

    renderPluginsIndex();

    expect(
      screen.getByText("No plugin workflows are available right now."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/build_example_plugins|uv run python/i),
    ).not.toBeInTheDocument();
  });
});
