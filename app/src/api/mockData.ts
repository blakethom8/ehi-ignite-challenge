import type { PatientListItem } from "../types";

/*
 * Frontend mock data boundary
 *
 * We keep this file intentionally small and explicit so the design/build loop can
 * continue when FastAPI is not running. The API client may use these records only
 * for UI shell work; integration checks should still run against the real
 * Synthea-backed FastAPI endpoints before we commit or demo behavior that depends
 * on patient data.
 */
export const mockPatients: PatientListItem[] = [
  {
    id: "demo-high-risk",
    name: "Demo Patient - Surgical Review",
    age_years: 67,
    gender: "female",
    complexity_tier: "complex",
    complexity_score: 82,
    total_resources: 4812,
    encounter_count: 44,
    active_condition_count: 9,
    active_med_count: 11,
  },
  {
    id: "demo-trial-match",
    name: "Demo Patient - Trial Match",
    age_years: 54,
    gender: "male",
    complexity_tier: "moderate",
    complexity_score: 61,
    total_resources: 3180,
    encounter_count: 28,
    active_condition_count: 6,
    active_med_count: 7,
  },
  {
    id: "demo-med-access",
    name: "Demo Patient - Medication Access",
    age_years: 72,
    gender: "female",
    complexity_tier: "highly_complex",
    complexity_score: 91,
    total_resources: 5364,
    encounter_count: 51,
    active_condition_count: 12,
    active_med_count: 15,
  },
];
