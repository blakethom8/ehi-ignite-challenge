import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessProvider } from "../context/AccessContext";
import { GuestHarmonization } from "./GuestHarmonization";

const {
  createGuestHarmonizationRunMock,
  deleteGuestHarmonizationRunMock,
  getGuestHarmonizationOutputMock,
  getGuestHarmonizationRunMock,
  uploadGuestHarmonizationFileMock,
  processGuestHarmonizationRunMock,
  setGuestHarmonizationContextMock,
  exportGuestHarmonizationBundleMock,
  getAuthSessionMock,
  getCapabilitiesMock,
} = vi.hoisted(() => ({
  createGuestHarmonizationRunMock: vi.fn(),
  deleteGuestHarmonizationRunMock: vi.fn(),
  getGuestHarmonizationOutputMock: vi.fn(),
  getGuestHarmonizationRunMock: vi.fn(),
  uploadGuestHarmonizationFileMock: vi.fn(),
  processGuestHarmonizationRunMock: vi.fn(),
  setGuestHarmonizationContextMock: vi.fn(),
  exportGuestHarmonizationBundleMock: vi.fn(),
  getAuthSessionMock: vi.fn(),
  getCapabilitiesMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    createGuestHarmonizationRun: createGuestHarmonizationRunMock,
    deleteGuestHarmonizationRun: deleteGuestHarmonizationRunMock,
    getGuestHarmonizationOutput: getGuestHarmonizationOutputMock,
    getGuestHarmonizationRun: getGuestHarmonizationRunMock,
    uploadGuestHarmonizationFile: uploadGuestHarmonizationFileMock,
    processGuestHarmonizationRun: processGuestHarmonizationRunMock,
    setGuestHarmonizationContext: setGuestHarmonizationContextMock,
    exportGuestHarmonizationBundle: exportGuestHarmonizationBundleMock,
    getAuthSession: getAuthSessionMock,
    getCapabilities: getCapabilitiesMock,
  },
}));

function renderGuestHarmonization(initialEntry = "/guest-harmonization") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AccessProvider>
        <GuestHarmonization />
      </AccessProvider>
    </MemoryRouter>,
  );
}

const READY_DISCLOSURE =
  "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.";

describe("GuestHarmonization", () => {
  beforeEach(() => {
    createGuestHarmonizationRunMock.mockReset();
    deleteGuestHarmonizationRunMock.mockReset();
    getGuestHarmonizationOutputMock.mockReset();
    getGuestHarmonizationRunMock.mockReset();
    uploadGuestHarmonizationFileMock.mockReset();
    processGuestHarmonizationRunMock.mockReset();
    setGuestHarmonizationContextMock.mockReset();
    exportGuestHarmonizationBundleMock.mockReset();
    getAuthSessionMock.mockReset();
    getCapabilitiesMock.mockReset();
    getAuthSessionMock.mockResolvedValue({
      mode: "anonymous",
      user: null,
      active_patient_id: null,
      active_patient_name: null,
      active_demo_patient: null,
      expires_at: null,
      available_demo_patients: [],
    });
    getCapabilitiesMock.mockResolvedValue({
      mode: "anonymous",
      can_use_caspian: false,
      can_edit_caspian_user_files: false,
      can_write_caspian_notes: false,
      can_run_workflows: false,
      can_use_aggregation_uploads: false,
      can_use_aggregation_profiles: false,
      can_use_harmonize: false,
      can_use_guest_harmonization: true,
      can_use_assistant_tools_write: false,
      show_caspian_seed_files: false,
      persistence_scope: "none",
    });

    createGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [],
      outputs: [],
      status: "ready",
      disclosure: READY_DISCLOSURE,
    });

    uploadGuestHarmonizationFileMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [
        {
          file_id: "file_1",
          file_name: "lab-report.pdf",
          content_type: "application/pdf",
          size_bytes: 2048,
          uploaded_at: "2026-05-11T18:01:00Z",
          storage_path: "uploads/file_1-lab-report.pdf",
          status: "uploaded",
        },
      ],
      outputs: [],
      status: "ready",
      disclosure: READY_DISCLOSURE,
    });

    processGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [
        {
          file_id: "file_1",
          file_name: "lab-report.pdf",
          content_type: "application/pdf",
          size_bytes: 2048,
          uploaded_at: "2026-05-11T18:01:00Z",
          storage_path: "uploads/file_1-lab-report.pdf",
          status: "uploaded",
        },
      ],
      outputs: [
        {
          output_id: "harmonized-record",
          file_name: "harmonized-record.json",
          content_type: "application/json",
          size_bytes: 1024,
          created_at: "2026-05-11T18:02:00Z",
          storage_path: "outputs/harmonized-record.json",
        },
      ],
      status: "completed",
      disclosure: READY_DISCLOSURE,
    });

    getGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [],
      outputs: [],
      status: "ready",
      disclosure: READY_DISCLOSURE,
    });

    deleteGuestHarmonizationRunMock.mockResolvedValue({
      deleted: true,
      run_id: "guest_test_run",
    });

    setGuestHarmonizationContextMock.mockImplementation((_runId, payload) =>
      Promise.resolve({
        run_id: "guest_test_run",
        mode: "guest",
        created_at: "2026-05-11T18:00:00Z",
        expires_at: "2026-05-12T18:00:00Z",
        uploaded_files: [],
        outputs: [],
        status: "ready",
        disclosure: READY_DISCLOSURE,
        patient_voice: payload?.patient_voice ?? null,
        audience: payload?.audience ?? null,
      }),
    );

    exportGuestHarmonizationBundleMock.mockResolvedValue(
      new Blob(["zipped-bytes"], { type: "application/zip" }),
    );
  });

  it("creates the run lazily when the user drops a file and shows it in the list", async () => {
    renderGuestHarmonization();

    // No "Start workspace" button — run is created on first file drop.
    expect(screen.queryByRole("button", { name: /start temporary workspace/i })).toBeNull();

    const file = new File(["pdf-bytes"], "lab-report.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).not.toBeNull();
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(createGuestHarmonizationRunMock).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(uploadGuestHarmonizationFileMock).toHaveBeenCalledWith("guest_test_run", file);
    });

    // File row appears with PDF badge.
    expect(screen.getByText("lab-report.pdf")).toBeInTheDocument();
    expect(screen.getByText(/extraction pending/i)).toBeInTheDocument();
  });

  it("harmonizes after files are uploaded and reveals Download bundle", async () => {
    renderGuestHarmonization();

    // Upload a file first (lazy run creation).
    const file = new File(["{}"], "bundle.json", { type: "application/json" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() =>
      expect(uploadGuestHarmonizationFileMock).toHaveBeenCalled(),
    );

    fireEvent.click(screen.getByRole("button", { name: /harmonize my files/i }));

    await waitFor(() => {
      expect(processGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    // Once completed, Step 4's download button becomes enabled.
    expect(screen.getByRole("button", { name: /download bundle/i })).toBeEnabled();
  });

  it("saves patient context (voice + audience) via the new endpoint", async () => {
    // Hydrate an existing completed run.
    getGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [
        {
          file_id: "file_1",
          file_name: "bundle.json",
          content_type: "application/json",
          size_bytes: 1024,
          uploaded_at: "2026-05-11T18:01:00Z",
          storage_path: "uploads/file_1-bundle.json",
          status: "uploaded",
        },
      ],
      outputs: [
        {
          output_id: "harmonized-record",
          file_name: "harmonized-record.json",
          content_type: "application/json",
          size_bytes: 1024,
          created_at: "2026-05-11T18:02:00Z",
          storage_path: "outputs/harmonized-record.json",
        },
      ],
      status: "completed",
      disclosure: READY_DISCLOSURE,
    });

    renderGuestHarmonization("/guest-harmonization?run=guest_test_run");

    await waitFor(() => {
      expect(getGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    const textarea = await screen.findByPlaceholderText(/scheduled for hernia repair/i);
    fireEvent.change(textarea, { target: { value: "Worried about my anticoagulants." } });
    fireEvent.click(screen.getByRole("button", { name: /pre-op review/i }));
    fireEvent.click(screen.getByRole("button", { name: /save context/i }));

    await waitFor(() => {
      expect(setGuestHarmonizationContextMock).toHaveBeenCalledWith("guest_test_run", {
        patient_voice: "Worried about my anticoagulants.",
        audience: "preop-review",
      });
    });
  });

  it("does not refetch a run immediately after that run is deleted", async () => {
    getGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [],
      outputs: [],
      status: "ready",
      disclosure: READY_DISCLOSURE,
    });

    renderGuestHarmonization("/guest-harmonization?run=guest_test_run");

    await waitFor(() => {
      expect(getGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    getGuestHarmonizationRunMock.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /delete now/i }));

    await waitFor(() => {
      expect(deleteGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    // The footer (and its delete button) only renders when a run exists, so
    // after delete the page returns to its initial empty state.
    expect(screen.queryByRole("button", { name: /delete now/i })).toBeNull();
    expect(getGuestHarmonizationRunMock).not.toHaveBeenCalled();
  });
});
