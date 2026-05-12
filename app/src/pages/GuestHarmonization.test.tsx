import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GuestHarmonization } from "./GuestHarmonization";

const {
  createGuestHarmonizationRunMock,
  deleteGuestHarmonizationRunMock,
  getGuestHarmonizationOutputMock,
  getGuestHarmonizationRunMock,
  uploadGuestHarmonizationFileMock,
} = vi.hoisted(() => ({
  createGuestHarmonizationRunMock: vi.fn(),
  deleteGuestHarmonizationRunMock: vi.fn(),
  getGuestHarmonizationOutputMock: vi.fn(),
  getGuestHarmonizationRunMock: vi.fn(),
  uploadGuestHarmonizationFileMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    createGuestHarmonizationRun: createGuestHarmonizationRunMock,
    deleteGuestHarmonizationRun: deleteGuestHarmonizationRunMock,
    getGuestHarmonizationOutput: getGuestHarmonizationOutputMock,
    getGuestHarmonizationRun: getGuestHarmonizationRunMock,
    uploadGuestHarmonizationFile: uploadGuestHarmonizationFileMock,
  },
}));

function renderGuestHarmonization(initialEntry = "/guest-harmonization") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <GuestHarmonization />
    </MemoryRouter>,
  );
}

describe("GuestHarmonization", () => {
  beforeEach(() => {
    createGuestHarmonizationRunMock.mockReset();
    deleteGuestHarmonizationRunMock.mockReset();
    getGuestHarmonizationOutputMock.mockReset();
    getGuestHarmonizationRunMock.mockReset();
    uploadGuestHarmonizationFileMock.mockReset();

    createGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [],
      outputs: [],
      status: "ready",
      disclosure:
        "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.",
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
      disclosure:
        "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.",
    });

    getGuestHarmonizationRunMock.mockResolvedValue({
      run_id: "guest_test_run",
      mode: "guest",
      created_at: "2026-05-11T18:00:00Z",
      expires_at: "2026-05-12T18:00:00Z",
      uploaded_files: [],
      outputs: [],
      status: "ready",
      disclosure:
        "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.",
    });

    getGuestHarmonizationOutputMock.mockResolvedValue({
      schema_version: "atlas.harmonized_record.v1",
      created_at: "2026-05-11T18:02:00Z",
      source_files: [{ file_name: "lab-report.pdf" }],
      patient: {},
      facts: [{ fact_id: "fact_1" }],
      provenance: [],
      quality_issues: [{ code: "format_not_deeply_parsed" }],
    });

    deleteGuestHarmonizationRunMock.mockResolvedValue({
      deleted: true,
      run_id: "guest_test_run",
    });
  });

  it("explains when a file is only selected and clears that hint after upload", async () => {
    renderGuestHarmonization();

    fireEvent.click(screen.getByRole("button", { name: /start temporary workspace/i }));

    await waitFor(() => {
      expect(createGuestHarmonizationRunMock).toHaveBeenCalled();
    });

    const input = screen.getByLabelText(/upload file/i);
    const file = new File(["pdf-bytes"], "lab-report.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(
      screen.getByText('Selected lab-report.pdf. Click "Upload selected file" to add it to this workspace.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Finish uploading the selected file before building output."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /upload selected file/i }));

    await waitFor(() => {
      expect(uploadGuestHarmonizationFileMock).toHaveBeenCalledWith("guest_test_run", file);
    });

    await waitFor(() => {
      expect(
        screen.getByText("Choose a JSON, PDF, XML, or TXT file, then upload it into this temporary workspace."),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("lab-report.pdf")).toBeInTheDocument();
  });

  it("restores completed output when reopening an existing run", async () => {
    getGuestHarmonizationRunMock.mockResolvedValue({
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
      disclosure:
        "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.",
    });

    renderGuestHarmonization("/guest-harmonization?run=guest_test_run");

    await waitFor(() => {
      expect(getGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    await waitFor(() => {
      expect(getGuestHarmonizationOutputMock).toHaveBeenCalledWith("guest_test_run");
    });

    expect(screen.getByText("Output ready")).toBeInTheDocument();
    expect(screen.getByText("Download JSON")).toBeInTheDocument();
    expect(screen.getByText("lab-report.pdf")).toBeInTheDocument();
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
      disclosure:
        "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.",
    });

    renderGuestHarmonization("/guest-harmonization?run=guest_test_run");

    await waitFor(() => {
      expect(getGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    getGuestHarmonizationRunMock.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /delete workspace/i }));

    await waitFor(() => {
      expect(deleteGuestHarmonizationRunMock).toHaveBeenCalledWith("guest_test_run");
    });

    expect(screen.getByRole("button", { name: /start temporary workspace/i })).toBeInTheDocument();
    expect(getGuestHarmonizationRunMock).not.toHaveBeenCalled();
  });
});
