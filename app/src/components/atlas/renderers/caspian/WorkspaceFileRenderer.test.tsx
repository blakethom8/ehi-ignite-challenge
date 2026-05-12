import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ANONYMOUS_CAPABILITIES } from "../../../../hooks/useCapabilities";
import type { Capabilities } from "../../../../types";
import { WorkspaceFileRenderer } from "./WorkspaceFileRenderer";

const { useCapabilitiesMock } = vi.hoisted(() => ({
  useCapabilitiesMock: vi.fn<() => Capabilities>(),
}));

vi.mock("../../../../hooks/useCapabilities", async () => {
  const real = await vi.importActual<typeof import("../../../../hooks/useCapabilities")>(
    "../../../../hooks/useCapabilities",
  );
  return {
    ...real,
    useCapabilities: () => useCapabilitiesMock(),
  };
});

const baseBlob = {
  path: "notes/scratch.md",
  content: "# Hello\n\nbody text",
  mtime: null,
  editable: false,
  kind: "markdown" as const,
};

function renderRenderer(args: {
  blob: Record<string, unknown>;
  filesApi?: Record<string, unknown>;
  capabilities?: Capabilities;
}) {
  useCapabilitiesMock.mockReturnValue(args.capabilities ?? ANONYMOUS_CAPABILITIES);
  const canvas: Record<string, unknown> = {
    "notes/scratch.md": args.blob,
  };
  if (args.filesApi) canvas.__files = args.filesApi;
  return render(
    <WorkspaceFileRenderer
      runId="r1"
      canvas={canvas}
      tabId="notes/scratch.md"
    />,
  );
}

describe("WorkspaceFileRenderer", () => {
  beforeEach(() => {
    useCapabilitiesMock.mockReset();
  });

  it("renders the system pill for kind=system", () => {
    renderRenderer({ blob: { ...baseBlob, fileKind: "system" } });
    expect(screen.getByText(/System · read-only/i)).toBeInTheDocument();
  });

  it("renders the user-authored pill for kind=user", () => {
    renderRenderer({ blob: { ...baseBlob, fileKind: "user" } });
    expect(screen.getByText(/User-authored/i)).toBeInTheDocument();
  });

  it("renders the generated pill for kind=generated", () => {
    renderRenderer({ blob: { ...baseBlob, fileKind: "generated" } });
    expect(screen.getByText(/Generated · read-only/i)).toBeInTheDocument();
  });

  it("renders the demo-seed pill for kind=demo-seed", () => {
    renderRenderer({ blob: { ...baseBlob, fileKind: "demo-seed" } });
    expect(screen.getByText(/Sample · read-only/i)).toBeInTheDocument();
  });

  it("hides the Edit button when the blob is not editable", () => {
    renderRenderer({
      blob: { ...baseBlob, fileKind: "user", editable: false },
      filesApi: { openFile: vi.fn(), saveFile: vi.fn(), refreshFile: vi.fn() },
    });
    expect(screen.queryByRole("button", { name: /^Edit$/i })).not.toBeInTheDocument();
  });

  it("shows the Edit button when editable=true and filesApi is wired", () => {
    renderRenderer({
      blob: { ...baseBlob, fileKind: "user", editable: true },
      filesApi: { openFile: vi.fn(), saveFile: vi.fn(), refreshFile: vi.fn() },
    });
    expect(screen.getByRole("button", { name: /^Edit$/i })).toBeInTheDocument();
  });

  it("shows Save as note when blob is generated, capability is granted, and saveAsNote is wired", async () => {
    const saveAsNote = vi.fn<(p: string) => Promise<string>>().mockResolvedValue(
      "notes/2026-05-12-preop.md",
    );
    const openFile = vi.fn();

    renderRenderer({
      blob: {
        ...baseBlob,
        path: "workflow-runs/2026-05-12-preop.md",
        fileKind: "generated",
        editable: false,
      },
      filesApi: { openFile, saveFile: vi.fn(), refreshFile: vi.fn(), saveAsNote },
      capabilities: {
        ...ANONYMOUS_CAPABILITIES,
        mode: "authenticated",
        can_write_caspian_notes: true,
      },
    });
    const button = screen.getByRole("button", { name: /Save as note/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    await waitFor(() => expect(saveAsNote).toHaveBeenCalledWith("workflow-runs/2026-05-12-preop.md"));
    await waitFor(() =>
      expect(openFile).toHaveBeenCalledWith("notes/2026-05-12-preop.md"),
    );
  });

  it("hides Save as note when can_write_caspian_notes is false (demo)", () => {
    renderRenderer({
      blob: {
        ...baseBlob,
        path: "workflow-runs/2026-05-12-preop.md",
        fileKind: "generated",
      },
      filesApi: { openFile: vi.fn(), saveFile: vi.fn(), refreshFile: vi.fn(), saveAsNote: vi.fn() },
      capabilities: {
        ...ANONYMOUS_CAPABILITIES,
        mode: "demo",
        can_write_caspian_notes: false,
      },
    });
    expect(screen.queryByRole("button", { name: /Save as note/i })).not.toBeInTheDocument();
  });
});
