import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type {
  CaspianFileKind,
  CaspianFileReadResponse,
  CaspianFileTreeNode,
} from "../../types";
import type { FileTreeNode } from "./data";

export type CaspianFileBlob = {
  path: string;
  content: string;
  mtime: string | null;
  editable: boolean;
  /** Content format — markdown/json/text. Drives the renderer. */
  kind: "markdown" | "json" | "text";
  /** File-kind taxonomy — system/user/generated/demo-seed. Drives the
   *  provenance pill + the "Save as note" affordance. */
  fileKind?: CaspianFileKind;
};

/**
 * useCaspianFiles
 *
 * Owns the live state of the Caspian Files pane: the tree (via React Query)
 * and an in-memory cache of opened file contents (so workbench tabs don't
 * refetch on every tab switch).
 *
 * Exposed verbs:
 *  - `tree`             — array suitable to pass straight to FilesPane.
 *  - `openFile(path)`   — fetches + caches; returns blob.
 *  - `saveFile(path, c)`— writes; updates cache + refreshes tree.
 *  - `refetchTree()`    — call after workflow runs / chat-tool writes.
 *  - `getCachedBlob(p)` — synchronous lookup for the workbench canvas.
 */
export function useCaspianFiles(patientId: string | null) {
  const queryClient = useQueryClient();
  const treeKey = useMemo(() => ["caspian-files", patientId] as const, [patientId]);

  const treeQuery = useQuery({
    queryKey: treeKey,
    enabled: Boolean(patientId),
    queryFn: async () => api.listCaspianFiles(patientId!),
    staleTime: 30_000,
  });

  const [openContent, setOpenContent] = useState<Record<string, CaspianFileBlob>>({});
  // Mirror state into a ref so openFile() doesn't have to depend on the cache
  // state (which would cause its identity to change on every fetch, causing
  // downstream renderer effects to re-fire and re-fetch in a loop).
  const cacheRef = useRef<Record<string, CaspianFileBlob>>({});
  const inflightRef = useRef<Record<string, Promise<CaspianFileBlob | null>>>({});
  useEffect(() => {
    cacheRef.current = openContent;
  }, [openContent]);

  // Reset cache when switching patients.
  useEffect(() => {
    cacheRef.current = {};
    inflightRef.current = {};
    setOpenContent({});
  }, [patientId]);

  const openFile = useCallback(
    async (path: string): Promise<CaspianFileBlob | null> => {
      if (!patientId) return null;
      const cached = cacheRef.current[path];
      if (cached) return cached;
      const inflight = inflightRef.current[path];
      if (inflight) return inflight;
      const promise: Promise<CaspianFileBlob | null> = (async () => {
        try {
          const res: CaspianFileReadResponse = await api.readCaspianFile(patientId, path);
          const blob: CaspianFileBlob = {
            path: res.path,
            content: res.content,
            mtime: res.mtime,
            editable: res.editable,
            kind: res.kind,
            fileKind: res.file_kind,
          };
          setOpenContent((current) => ({ ...current, [path]: blob }));
          return blob;
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          const blob: CaspianFileBlob = {
            path,
            content: `# Could not load ${path}\n\n${message}`,
            mtime: null,
            editable: false,
            kind: "markdown",
          };
          setOpenContent((current) => ({ ...current, [path]: blob }));
          return blob;
        } finally {
          delete inflightRef.current[path];
        }
      })();
      inflightRef.current[path] = promise;
      return promise;
    },
    [patientId],
  );

  const refreshFile = useCallback(
    async (path: string): Promise<CaspianFileBlob | null> => {
      if (!patientId) return null;
      delete cacheRef.current[path];
      delete inflightRef.current[path];
      setOpenContent((current) => {
        const next = { ...current };
        delete next[path];
        return next;
      });
      return openFile(path);
    },
    [openFile, patientId],
  );

  const saveMutation = useMutation({
    mutationFn: async (vars: { path: string; content: string }) => {
      if (!patientId) throw new Error("No patient selected.");
      return api.writeCaspianFile({
        patient_id: patientId,
        path: vars.path,
        content: vars.content,
      });
    },
    onSuccess: (res, vars) => {
      setOpenContent((current) => ({
        ...current,
        [res.path]: {
          path: res.path,
          content: vars.content,
          mtime: res.mtime,
          editable: true,
          kind: current[res.path]?.kind ?? "markdown",
          fileKind: current[res.path]?.fileKind ?? "user",
        },
      }));
      queryClient.invalidateQueries({ queryKey: treeKey });
    },
  });

  const saveFile = useCallback(
    (path: string, content: string) => saveMutation.mutateAsync({ path, content }),
    [saveMutation],
  );

  const saveAsNoteMutation = useMutation({
    mutationFn: async (sourcePath: string) => {
      if (!patientId) throw new Error("No patient selected.");
      return api.saveCaspianFileAsNote(patientId, sourcePath);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: treeKey });
    },
  });

  /**
   * Copy a generated workflow-run artifact into the user's notes/ folder.
   * Returns the new note path so the caller can open the resulting tab.
   * The tree is invalidated on success so the new note appears in FilesPane.
   */
  const saveAsNote = useCallback(
    async (sourcePath: string): Promise<string> => {
      const res = await saveAsNoteMutation.mutateAsync(sourcePath);
      return res.path;
    },
    [saveAsNoteMutation],
  );

  const refetchTree = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: treeKey });
  }, [queryClient, treeKey]);

  const getCachedBlob = useCallback(
    (path: string): CaspianFileBlob | null => openContent[path] ?? null,
    [openContent],
  );

  const tree: FileTreeNode[] = useMemo(
    () => (treeQuery.data?.tree as unknown as FileTreeNode[]) ?? [],
    [treeQuery.data],
  );

  return {
    tree,
    treeQuery,
    openFile,
    refreshFile,
    saveFile,
    saveAsNote,
    refetchTree,
    getCachedBlob,
    /** Raw blob cache — exposed so consumers can use it as a memo dep. */
    openContent,
    isSaving: saveMutation.isPending,
    saveError: saveMutation.error,
    isSavingAsNote: saveAsNoteMutation.isPending,
    saveAsNoteError: saveAsNoteMutation.error,
  };
}

export type CaspianFilesHook = ReturnType<typeof useCaspianFiles>;

// Re-export the raw API type so callers can introspect node shapes if needed.
export type { CaspianFileTreeNode };
