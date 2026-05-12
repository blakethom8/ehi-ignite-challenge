import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCaspianFiles } from "./useCaspianFiles";

const {
  listCaspianFiles,
  readCaspianFile,
  writeCaspianFile,
  saveCaspianFileAsNote,
} = vi.hoisted(() => ({
  listCaspianFiles: vi.fn(),
  readCaspianFile: vi.fn(),
  writeCaspianFile: vi.fn(),
  saveCaspianFileAsNote: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: {
    listCaspianFiles: (...args: unknown[]) => listCaspianFiles(...args),
    readCaspianFile: (...args: unknown[]) => readCaspianFile(...args),
    writeCaspianFile: (...args: unknown[]) => writeCaspianFile(...args),
    saveCaspianFileAsNote: (...args: unknown[]) => saveCaspianFileAsNote(...args),
  },
}));

function makeWrapper(): (props: { children: ReactNode }) => JSX.Element {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useCaspianFiles", () => {
  beforeEach(() => {
    listCaspianFiles.mockReset();
    readCaspianFile.mockReset();
    writeCaspianFile.mockReset();
    saveCaspianFileAsNote.mockReset();
  });

  it("opens a file and surfaces fileKind on the blob", async () => {
    listCaspianFiles.mockResolvedValue({
      workspace_key: "auth-user_1--patient-1",
      tree: [
        {
          type: "folder",
          name: "notes",
          children: [
            {
              type: "file",
              name: "scratch.md",
              id: "notes/scratch.md",
              ext: "md",
              icon: "FileText",
              dirty: false,
              editable: true,
              kind: "user",
            },
          ],
        },
      ],
      capabilities: null,
    });
    readCaspianFile.mockResolvedValue({
      path: "notes/scratch.md",
      content: "hello",
      mtime: null,
      editable: true,
      kind: "markdown",
      file_kind: "user",
    });

    const { result } = renderHook(() => useCaspianFiles("patient-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(listCaspianFiles).toHaveBeenCalledTimes(1));

    let blob: Awaited<ReturnType<typeof result.current.openFile>> = null;
    await act(async () => {
      blob = await result.current.openFile("notes/scratch.md");
    });
    expect(blob?.fileKind).toBe("user");
    expect(blob?.content).toBe("hello");
  });

  it("caches the blob across repeated openFile calls", async () => {
    listCaspianFiles.mockResolvedValue({ workspace_key: "k", tree: [], capabilities: null });
    readCaspianFile.mockResolvedValue({
      path: "notes/a.md",
      content: "a",
      mtime: null,
      editable: true,
      kind: "markdown",
      file_kind: "user",
    });

    const { result } = renderHook(() => useCaspianFiles("patient-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(listCaspianFiles).toHaveBeenCalled());

    await act(async () => {
      await result.current.openFile("notes/a.md");
    });
    await act(async () => {
      await result.current.openFile("notes/a.md");
    });
    expect(readCaspianFile).toHaveBeenCalledTimes(1);
  });

  it("invalidates the tree after saveFile", async () => {
    listCaspianFiles.mockResolvedValue({ workspace_key: "k", tree: [], capabilities: null });
    writeCaspianFile.mockResolvedValue({
      path: "notes/scratch.md",
      bytes: 5,
      mtime: "2026-05-12T12:00:00Z",
    });

    const { result } = renderHook(() => useCaspianFiles("patient-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(listCaspianFiles).toHaveBeenCalledTimes(1));

    await act(async () => {
      await result.current.saveFile("notes/scratch.md", "hello world");
    });

    // First call on mount; invalidation triggers a refetch (call 2).
    await waitFor(() => expect(listCaspianFiles).toHaveBeenCalledTimes(2));
    expect(writeCaspianFile).toHaveBeenCalledWith({
      patient_id: "patient-1",
      path: "notes/scratch.md",
      content: "hello world",
    });
  });

  it("invokes saveAsNote and refreshes the tree", async () => {
    listCaspianFiles.mockResolvedValue({ workspace_key: "k", tree: [], capabilities: null });
    saveCaspianFileAsNote.mockResolvedValue({
      path: "notes/2026-05-12-preop.md",
      bytes: 12,
      mtime: "2026-05-12T12:00:00Z",
    });

    const { result } = renderHook(() => useCaspianFiles("patient-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(listCaspianFiles).toHaveBeenCalledTimes(1));

    let newPath = "";
    await act(async () => {
      newPath = await result.current.saveAsNote("workflow-runs/2026-05-12-preop.md");
    });
    expect(newPath).toBe("notes/2026-05-12-preop.md");
    expect(saveCaspianFileAsNote).toHaveBeenCalledWith(
      "patient-1",
      "workflow-runs/2026-05-12-preop.md",
    );
    await waitFor(() => expect(listCaspianFiles).toHaveBeenCalledTimes(2));
  });
});
