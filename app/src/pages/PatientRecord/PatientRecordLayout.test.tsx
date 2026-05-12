import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PatientRecordLayout } from "./PatientRecordLayout";

describe("PatientRecordLayout", () => {
  it("uses a single overview step instead of a separate workspace library step", () => {
    render(
      <MemoryRouter initialEntries={["/patient-record?patient=demo-trial-match"]}>
        <PatientRecordLayout>
          <div>Body</div>
        </PatientRecordLayout>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /Overview/i })).toBeInTheDocument();
    expect(screen.getAllByText("Current state and history")).toHaveLength(1);
    expect(screen.queryByText("Workspace Library")).not.toBeInTheDocument();
  });

  it("exposes a Snapshots nav item that links to the snapshots route", () => {
    render(
      <MemoryRouter initialEntries={["/patient-record?patient=demo-trial-match"]}>
        <PatientRecordLayout>
          <div>Body</div>
        </PatientRecordLayout>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: /Snapshots/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute(
      "href",
      "/patient-record/snapshots?patient=demo-trial-match",
    );
  });
});
