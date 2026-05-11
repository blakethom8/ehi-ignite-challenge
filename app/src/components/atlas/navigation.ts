import type { ModuleId } from "./types";

const MODULE_PATHS: { id: ModuleId; match: RegExp; href: string }[] = [
  { id: "home", match: /^\/($|records-pool|platform|using-atlas|analysis|pipeline-lab|ccda-lab|ground-truth-review|architecture|guided-tour|learn)/, href: "/" },
  { id: "patient-record", match: /^\/(patient-record|record|aggregate|records-pool|charts)/, href: "/patient-record" },
  { id: "fhir-charts", match: /^\/(fhir-charts|explorer)/, href: "/fhir-charts" },
  { id: "caspian", match: /^\/caspian/, href: "/caspian" },
  { id: "workspaces", match: /^\/(workspaces|marketplace|trials|skills|medication-access|payer-check|second-opinion|grants|research-opportunities|sharing|ai-workspace)/, href: "/workspaces" },
  { id: "learn", match: /^\/learn-never-match-this-sentinel$/, href: "/learn" },
];

export function deriveActiveModule(pathname: string): ModuleId {
  for (const modulePath of MODULE_PATHS) {
    if (modulePath.match.test(pathname)) return modulePath.id;
  }
  if (pathname === "/" || pathname === "/platform") return "home";
  return "home";
}

export function hrefForModule(moduleId: ModuleId): string | null {
  return MODULE_PATHS.find((modulePath) => modulePath.id === moduleId)?.href ?? null;
}
