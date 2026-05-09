#!/usr/bin/env bash
set -euo pipefail

FHIR_CONVERTER_URL="${FHIR_CONVERTER_URL:-http://127.0.0.1:18080}"
FHIR_CONVERTER_API_VERSION="${FHIR_CONVERTER_API_VERSION:-2024-05-01-preview}"

python3 - <<'PY'
from __future__ import annotations

import json
import os
import urllib.request

base_url = os.environ.get("FHIR_CONVERTER_URL", "http://127.0.0.1:18080").rstrip("/")
api_version = os.environ.get("FHIR_CONVERTER_API_VERSION", "2024-05-01-preview")
ccda = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <patient>
        <name><given>Smoke</given><family>Test</family></name>
        <administrativeGenderCode code="F"/>
        <birthTime value="19800102"/>
      </patient>
    </patientRole>
  </recordTarget>
  <title>Continuity of Care Document</title>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11450-4"/>
          <title>Problems</title>
          <entry>
            <act>
              <entryRelationship>
                <observation>
                  <value code="38341003" displayName="Hypertension" codeSystemName="SNOMED CT"/>
                </observation>
              </entryRelationship>
            </act>
          </entry>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
"""
payload = {
    "InputDataFormat": "Ccda",
    "RootTemplateName": "CCD",
    "InputDataString": ccda,
}
request = urllib.request.Request(
    f"{base_url}/convertToFhir?api-version={api_version}",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=45) as response:
    body = json.loads(response.read().decode("utf-8"))

bundle = body.get("result", {})
resources = [
    entry.get("resource", {}).get("resourceType")
    for entry in bundle.get("entry", [])
    if isinstance(entry, dict)
]
print(json.dumps({"ok": bundle.get("resourceType") == "Bundle", "resourceTypes": resources[:20], "resourceCount": len(resources)}, indent=2))
PY
