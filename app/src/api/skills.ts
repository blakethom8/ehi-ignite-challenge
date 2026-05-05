/**
 * API client for the /api/skills surface.
 *
 * Thin wrappers over a private axios instance (mirrors `client.ts`'s
 * convention). Each function is small enough that React Query hooks can
 * pass them as `queryFn`/`mutationFn` directly.
 */

import axios from "axios";
import type {
  Citation,
  PatientMemoryResponse,
  RunListItem,
  RunStartResponse,
  RunStateResponse,
  SaveRequest,
  SkillDetail,
  SkillSummary,
  TranscriptResponse,
  WorkspaceResponse,
} from "../types/skills";

const http = axios.create({
  baseURL: "/api/skills",
  headers: { "Content-Type": "application/json" },
});

export const skillsApi = {
  listSkills: (): Promise<SkillSummary[]> =>
    http.get<SkillSummary[]>("").then((r) => r.data),

  getSkill: (name: string): Promise<SkillDetail> =>
    http.get<SkillDetail>(`/${encodeURIComponent(name)}`).then((r) => r.data),

  startRun: (
    skillName: string,
    payload: { patient_id: string; brief: Record<string, unknown> }
  ): Promise<RunStartResponse> =>
    http
      .post<RunStartResponse>(
        `/${encodeURIComponent(skillName)}/runs`,
        payload
      )
      .then((r) => r.data),

  getRunState: (
    skillName: string,
    runId: string,
    patientId: string
  ): Promise<RunStateResponse> =>
    http
      .get<RunStateResponse>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(runId)}`,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  getWorkspace: (
    skillName: string,
    runId: string,
    patientId: string
  ): Promise<WorkspaceResponse> =>
    http
      .get<WorkspaceResponse>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(
          runId
        )}/workspace`,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  getCitations: (
    skillName: string,
    runId: string,
    patientId: string
  ): Promise<{ run_id: string; citations: Citation[] }> =>
    http
      .get<{ run_id: string; citations: Citation[] }>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(
          runId
        )}/citations`,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  getTranscript: (
    skillName: string,
    runId: string,
    patientId: string
  ): Promise<TranscriptResponse> =>
    http
      .get<TranscriptResponse>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(
          runId
        )}/transcript`,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  getOutput: (
    skillName: string,
    runId: string,
    patientId: string
  ): Promise<Record<string, unknown>> =>
    http
      .get<Record<string, unknown>>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(
          runId
        )}/output`,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  resolveEscalation: (
    skillName: string,
    runId: string,
    approvalId: string,
    patientId: string,
    payload: { choice: string; notes?: string; actor?: string }
  ): Promise<RunStateResponse> =>
    http
      .post<RunStateResponse>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(
          runId
        )}/escalations/${encodeURIComponent(approvalId)}`,
        payload,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  saveRun: (
    skillName: string,
    runId: string,
    patientId: string,
    payload: SaveRequest
  ): Promise<{ destination: string; written_path: string }> =>
    http
      .post<{ destination: string; written_path: string }>(
        `/${encodeURIComponent(skillName)}/runs/${encodeURIComponent(
          runId
        )}/save`,
        payload,
        { params: { patient_id: patientId } }
      )
      .then((r) => r.data),

  listPatientRuns: (
    patientId: string,
    skillName?: string
  ): Promise<RunListItem[]> =>
    http
      .get<RunListItem[]>(`/patients/${encodeURIComponent(patientId)}/runs`, {
        params: skillName ? { skill_name: skillName } : undefined,
      })
      .then((r) => r.data),

  getPatientMemory: (patientId: string): Promise<PatientMemoryResponse> =>
    http
      .get<PatientMemoryResponse>(
        `/patients/${encodeURIComponent(patientId)}/memory`
      )
      .then((r) => r.data),
};
