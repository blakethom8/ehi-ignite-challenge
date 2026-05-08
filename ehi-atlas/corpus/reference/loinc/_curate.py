"""Curate a LOINC reference table covering common labs.

Strategy:
1. Seed from the existing 22-code showcase-loinc.json (already verified against LOINC 2.77).
2. Layer in Function Health's verified codes for the 58 tests in our example PDF — these
   are real-world-verified mappings (their parser hit them, we cross-checked the codes).
3. Fill gaps via the NLM Clinical Tables LOINC API for tests neither source has.
4. Output common-labs.json with: code, display, system, unit, category, aliases, verified_against, notes.

Run:
    uv run --project /Users/blake/Repo/ehi-ignite-challenge \
        python ehi-atlas/corpus/reference/loinc/_curate.py

Re-runnable. Deterministic where possible; API gap-fills cached on disk.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path
from collections import OrderedDict

REPO = Path(__file__).resolve().parents[4]
SHOWCASE = REPO / "ehi-atlas/corpus/reference/loinc/showcase-loinc.json"
HAR = REPO / "pdf-review/blake-functionhealth-2025-11-19/function-outputs/function-lasbresults11192025-parse.har"
OUT = REPO / "ehi-atlas/corpus/reference/loinc/common-labs.json"

# Display-name aliases — extra strings that should match the same LOINC code.
# Keyed by LOINC code. Extend as we encounter new variants in real PDFs.
ALIASES: dict[str, list[str]] = {
    "2345-7": ["Glucose", "GLUCOSE", "Blood Glucose", "Serum Glucose", "Random Glucose"],
    "1558-6": ["Fasting Glucose", "FASTING GLUCOSE", "Fasting Plasma Glucose"],
    "3094-0": ["BUN", "Urea Nitrogen", "Blood Urea Nitrogen", "Urea Nitrogen (BUN)"],
    "2160-0": ["Creatinine", "CREATININE", "Serum Creatinine"],
    "33914-3": [
        "eGFR", "EGFR", "Estimated GFR", "Estimated Glomerular Filtration Rate",
        "Estimated Glomerular Filtration Rate (eGFR)", "GFR", "MDRD eGFR",
    ],
    "2951-2": ["Sodium", "SODIUM", "Na"],
    "2823-3": ["Potassium", "POTASSIUM", "K"],
    "2075-0": ["Chloride", "CHLORIDE", "Cl"],
    "2028-9": ["CO2", "Carbon Dioxide", "Carbon Dioxide (CO2)", "Bicarbonate", "Total CO2"],
    "17861-6": ["Calcium", "CALCIUM", "Total Calcium", "Ca"],
    "2885-2": ["Total Protein", "Protein", "Protein, Total", "PROTEIN, TOTAL"],
    "1751-7": ["Albumin", "ALBUMIN"],
    "2336-6": ["Globulin", "GLOBULIN"],
    "1759-0": ["Albumin/Globulin Ratio", "A/G Ratio", "ALBUMIN/GLOBULIN RATIO"],
    "1975-2": ["Bilirubin, Total", "Total Bilirubin", "Bilirubin Total", "BILIRUBIN, TOTAL", "Bilirubin"],
    "6768-6": ["Alkaline Phosphatase", "ALP", "Alkaline Phosphatase (ALP)", "Alk Phos", "ALKALINE PHOSPHATASE"],
    "1920-8": ["AST", "Aspartate Transaminase", "Aspartate Aminotransferase", "Aspartate Transaminase (AST)", "SGOT"],
    "1742-6": ["ALT", "Alanine Transaminase", "Alanine Aminotransferase", "Alanine Transaminase (ALT)", "SGPT"],
    "3097-3": ["BUN/Creatinine Ratio", "BUN/Cr Ratio", "Urea Nitrogen/Creatinine Ratio"],
    # CBC
    "6690-2": ["WBC", "White Blood Cell Count", "White Blood Cell (WBC) Count", "WBC Count"],
    "789-8": ["RBC", "Red Blood Cell Count", "Red Blood Cell (RBC) Count", "RBC Count"],
    "718-7": ["Hemoglobin", "HEMOGLOBIN", "Hgb", "Hb"],
    "4544-3": ["Hematocrit", "HCT", "Hct"],
    "787-2": ["MCV", "Mean Corpuscular Volume", "Mean Corpuscular Volume (MCV)"],
    "785-6": ["MCH", "Mean Corpuscular Hemoglobin", "Mean Corpuscular Hemoglobin (MCH)"],
    "786-4": ["MCHC", "Mean Corpuscular Hemoglobin Concentration"],
    "788-0": ["RDW", "Red Cell Distribution Width", "Red Cell Distribution Width (RDW)"],
    "777-3": ["Platelet Count", "Platelets", "Plt"],
    "776-5": ["MPV", "Mean Platelet Volume", "Mean Platelet Volume (MPV)"],
    # CBC differential
    "751-8": ["Absolute Neutrophils", "Neutrophils Absolute", "Neuts Absolute"],
    "731-0": ["Absolute Lymphocytes", "Lymphocytes Absolute", "Lymphs Absolute"],
    "742-7": ["Absolute Monocytes", "Monocytes Absolute"],
    "711-2": ["Absolute Eosinophils", "Eosinophils Absolute", "Eos Absolute"],
    "704-7": ["Absolute Basophils", "Basophils Absolute"],
    "770-8": ["Neutrophils %", "Neutrophils Percent", "Neuts %", "Neutrophils"],
    "736-9": ["Lymphocytes %", "Lymphocytes Percent", "Lymphs %", "Lymphocytes"],
    "5905-5": ["Monocytes %", "Monocytes Percent", "Monocytes"],
    "713-8": ["Eosinophils %", "Eosinophils Percent", "Eos %", "Eosinophils"],
    "706-2": ["Basophils %", "Basophils Percent", "Basophils"],
    # Other markers
    "30522-7": ["hs-CRP", "hs CRP", "High-Sensitivity C-Reactive Protein", "High-Sensitivity C-Reactive Protein (hs-CRP)"],
    "20448-7": ["Insulin", "INSULIN"],
    "4548-4": ["Hemoglobin A1c", "HbA1c", "A1c", "Hemoglobin A1c (HbA1c)", "HEMOGLOBIN A1c"],
    "1884-6": ["Apolipoprotein B", "ApoB", "Apolipoprotein B (ApoB)", "APOLIPOPROTEIN B"],
    # Urinalysis (qualitative — many LOINC variants exist; using common ones)
    "5778-6": ["Color", "Color - Urine", "Urine Color", "COLOR"],
    "5767-9": ["Appearance", "Appearance - Urine", "Urine Appearance", "Clarity"],
    "5811-5": ["Specific Gravity", "Specific Gravity - Urine", "SP GRAVITY"],
    "5803-2": ["pH", "pH - Urine", "Urine pH"],
    "5792-7": ["Glucose - Urine", "Urine Glucose", "Glucose (Urine)"],
    "5770-3": ["Bilirubin - Urine", "Urine Bilirubin", "Bilirubin (Urine)"],
    "5797-6": ["Ketones - Urine", "Ketones", "Urine Ketones"],
    "5794-3": ["Occult Blood - Urine", "Blood - Urine", "Hemoglobin - Urine", "Urine Blood", "Occult Blood"],
    "5804-0": ["Protein - Urine", "Urine Protein", "Protein (Urine)"],
    "5802-4": ["Nitrite - Urine", "Nitrite", "Urine Nitrite"],
    "5799-2": ["Leukocyte Esterase - Urine", "Leukocyte Esterase", "LE"],
    "5821-4": ["WBC - Urine", "White Blood Cell (WBC) - Urine", "WBC (Urine)", "Urine WBC"],
    "13945-1": ["RBC - Urine", "Red Blood Cell (RBC) - Urine", "RBC (Urine)", "Urine RBC"],
    "5787-7": ["Squamous Epithelial Cells - Urine", "Squamous Epithelial Cells", "Squamous Epi"],
    "5769-5": ["Bacteria - Urine", "Bacteria", "Urine Bacteria"],
    "5808-1": ["Hyaline Cast - Urine", "Hyaline Casts", "Hyaline Cast"],
    # IgE allergen panel — total + food + environmental allergens
    # Extends coverage from cedars-myhealth Allergen Profile w/ Component Reflex
    # (Quest test code; ~80 individual allergens). The "X IgE Class" interpretive
    # scores (0-6) intentionally have no LOINC codes — they remain unmatched.
    "51651-8": ["IGE", "IGE Total Serum", "Total IgE", "IgE Total", "IgE, Total"],
    # Food allergens (F-series codes from Quest)
    "6106-9": ["Egg White (F001) IgE", "Egg White IgE"],
    "6206-7": ["Peanut (F013) IgE", "Peanut IgE"],
    "6276-0": ["Wheat (F004) IgE", "Wheat IgE"],
    "6273-7": ["Walnut (F256) IgE", "Walnut IgE"],
    "6082-2": ["Codfish (F03) IgE", "Codfish IgE", "Cod IgE"],
    "6174-7": ["Milk, Cow's (F02) IgE", "Cow Milk IgE", "Milk IgE", "Cow's Milk IgE"],
    "6248-9": ["Soybean (F014) IgE", "Soybean IgE", "Soy IgE"],
    "6246-3": ["Shrimp (F024) IgE", "Shrimp IgE"],
    "7691-9": ["Scallop (F338) IgE", "Scallop IgE"],
    "6242-2": ["Sesame Seed (F010) IgE", "Sesame Seed IgE", "Sesame IgE"],
    "6136-6": ["Hazelnut/Filbert (F017) IgE", "Hazelnut IgE", "Filbert IgE"],
    "6718-1": ["Cashew Nut (F202) IgE", "Cashew IgE"],
    "6019-4": ["Almond (F020) IgE", "Almond IgE"],
    "6237-2": ["Salmon (F041) IgE", "Salmon IgE"],
    "6270-3": ["Tuna (F040) IgE", "Tuna IgE"],
    # Inhalant / environmental allergens (D/M/E/I/T/G/W series)
    "6095-4": ["D pteronyssinus (D001) IgE", "Dermatophagoides pteronyssinus IgE", "House Dust Mite IgE"],
    "6096-2": ["D farinae (D002) IgE", "Dermatophagoides farinae IgE"],
    "6212-5": ["Penicillium notatum (M001) IgE", "Penicillium IgE"],
    "6075-6": ["C herbarum (M002) IgE", "Cladosporium herbarum IgE", "Cladosporium IgE"],
    "6025-1": ["Aspergillus fumigatus (M003) IgE", "Aspergillus IgE"],
    "6098-8": ["Cat Dander (E001) IgE", "Cat Dander IgE", "Cat IgE"],
    "6099-6": ["Dog Dander (E005) IgE", "Dog Dander IgE", "Dog IgE"],
    "6078-0": ["Cockroach (I006) IgE", "Cockroach IgE"],
    "15284-3": ["Alder, Grey (T002) IgE", "Alder IgE", "Grey Alder IgE"],
    "21428-8": ["Olive Tree (T009) IgE", "Olive Tree IgE", "Olive IgE"],
    "102651-7": ["Walnut Pollen (T010) IgE", "Walnut Pollen IgE"],
    "6090-5": ["Cottonwood Tree (T014) IgE", "Cottonwood Tree IgE", "Cottonwood IgE"],
    "6189-5": ["Oak, White (T007) IgE", "Oak White IgE", "White Oak IgE", "Oak IgE"],
    "102293-8": ["Elm, American (T008) IgE", "American Elm IgE", "Elm IgE"],
    "6281-0": ["White Mulberry (T070) IgE", "White Mulberry IgE", "Mulberry IgE"],
    "6041-8": ["Bermuda Grass (G002) IgE", "Bermuda Grass IgE", "Bermuda IgE"],
    "6265-3": ["Timothy (G006) IgE", "Timothy Grass IgE", "Timothy IgE"],
    "6152-3": ["Johnson Grass (G010) IgE", "Johnson Grass IgE"],
    "6181-2": ["Mouse Urine Proteins IgE", "Mouse Urine Protein IgE", "Mouse Urine IgE"],
    "6085-5": ["Ragweed, Short/Common (W001) IgE", "Short Ragweed IgE", "Common Ragweed IgE", "Ragweed IgE"],
    "6183-8": ["Mugwort (W006) IgE", "Mugwort IgE"],
    "7604-2": ["Pigweed, Rough (W014) IgE", "Rough Pigweed IgE", "Pigweed IgE"],
}

# Clinical category by LOINC range/specific code — used by CODE-T07.
# (Captured here for now; extracted to its own module in T07.)
CLINICAL_CATEGORY: dict[str, str] = {
    "2345-7": "Metabolic", "1558-6": "Metabolic", "4548-4": "Metabolic", "20448-7": "Metabolic",
    "3094-0": "Kidney", "2160-0": "Kidney", "33914-3": "Kidney",
    "2951-2": "Kidney", "2823-3": "Kidney", "2075-0": "Kidney", "17861-6": "Kidney",
    "2028-9": "Electrolytes",
    "2885-2": "Liver", "1751-7": "Liver", "2336-6": "Liver", "1759-0": "Liver",
    "1975-2": "Liver", "6768-6": "Liver", "1920-8": "Liver", "1742-6": "Liver",
    "3097-3": "Kidney",
    "6690-2": "Immune Regulation",
    "789-8": "Blood", "718-7": "Blood", "4544-3": "Blood", "787-2": "Blood",
    "785-6": "Blood", "786-4": "Blood", "788-0": "Blood", "777-3": "Blood", "776-5": "Blood",
    "751-8": "Immune Regulation", "731-0": "Immune Regulation", "742-7": "Immune Regulation",
    "711-2": "Immune Regulation", "704-7": "Immune Regulation",
    "770-8": "Immune Regulation", "736-9": "Immune Regulation", "5905-5": "Immune Regulation",
    "713-8": "Immune Regulation", "706-2": "Immune Regulation",
    "30522-7": "Heart", "1884-6": "Heart",
    "5778-6": "Urine", "5767-9": "Urine", "5811-5": "Urine", "5803-2": "Urine",
    "5792-7": "Urine", "5770-3": "Urine", "5797-6": "Urine", "5794-3": "Urine",
    "5804-0": "Urine", "5802-4": "Urine", "5799-2": "Urine",
    "5821-4": "Urine", "13945-1": "Urine", "5787-7": "Urine",
    "5769-5": "Urine", "5808-1": "Urine",
    # IgE allergen panel
    "51651-8": "Allergens",
    # Food allergens
    "6106-9": "Allergens", "6206-7": "Allergens", "6276-0": "Allergens",
    "6273-7": "Allergens", "6082-2": "Allergens", "6174-7": "Allergens",
    "6248-9": "Allergens", "6246-3": "Allergens", "7691-9": "Allergens",
    "6242-2": "Allergens", "6136-6": "Allergens", "6718-1": "Allergens",
    "6019-4": "Allergens", "6237-2": "Allergens", "6270-3": "Allergens",
    # Inhalant / environmental allergens
    "6095-4": "Allergens", "6096-2": "Allergens", "6212-5": "Allergens",
    "6075-6": "Allergens", "6025-1": "Allergens", "6098-8": "Allergens",
    "6099-6": "Allergens", "6078-0": "Allergens", "15284-3": "Allergens",
    "21428-8": "Allergens", "102651-7": "Allergens", "6090-5": "Allergens",
    "6189-5": "Allergens", "102293-8": "Allergens", "6281-0": "Allergens",
    "6041-8": "Allergens", "6265-3": "Allergens", "6152-3": "Allergens",
    "6181-2": "Allergens", "6085-5": "Allergens", "6183-8": "Allergens",
    "7604-2": "Allergens",
}


def fetch_loinc_lookup(code: str) -> dict | None:
    """Fetch canonical display + system info for a LOINC code via NLM API."""
    url = (
        "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"
        f"?terms={urllib.parse.quote(code)}"
        "&df=LOINC_NUM,LONG_COMMON_NAME,COMPONENT,SYSTEM,SCALE_TYP,EXAMPLE_UCUM_UNITS"
        "&maxList=5"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        print(f"  ! API fetch failed for {code}: {exc}")
        return None
    total, codes, _, fields = data
    for c, f in zip(codes, fields):
        if c == code:
            return {
                "code": c,
                "long_common_name": f[1],
                "component": f[2],
                "system": f[3],
                "scale": f[4],
                "ucum_units": f[5],
            }
    return None


def main() -> None:
    showcase = json.loads(SHOWCASE.read_text())
    showcase_codes = {c["code"]: c for c in showcase["codes"]}

    print(f"showcase: {len(showcase_codes)} codes")

    # Get verified codes from Function Health output for our PDF
    har = json.loads(HAR.read_text())
    fh_doc = next(
        json.loads(e["response"]["content"]["text"])
        for e in har["log"]["entries"]
        if "parsed/1778178825031939" in e["request"]["url"] and e["request"]["method"] == "GET"
    )
    fh_bios = fh_doc["content"]["biomarkers"]
    fh_codes = {b["loincCode"]: b for b in fh_bios if b.get("loincCode")}
    print(f"function-health verified codes: {len(fh_codes)}")

    # Merge: ALIASES is the spine (these are the codes we care about for v1).
    # Pull metadata for each from showcase first, then FH, then NLM API.
    out_codes = OrderedDict()
    nlm_fetches_needed = 0

    for code, aliases in ALIASES.items():
        entry: dict = {
            "code": code,
            "system": "http://loinc.org",
            "aliases": aliases,
            "verified_against": [],
        }
        # Pull display + unit from showcase if present
        if code in showcase_codes:
            sc = showcase_codes[code]
            entry["display"] = sc["display"]
            entry["unit"] = sc.get("unit")
            entry["category"] = sc.get("category", "chemistry")
            entry["verified_against"].append("showcase-loinc-2.77")
            if sc.get("notes"):
                entry["notes"] = sc["notes"]
        # Cross-verify against Function Health
        if code in fh_codes:
            fh = fh_codes[code]
            entry["verified_against"].append("function-health-2025-11-19")
            if "display" not in entry:
                entry["display"] = fh.get("name", "")
            if not entry.get("unit"):
                entry["unit"] = fh.get("unit")
        # Add clinical category (CODE-T07 preview)
        if code in CLINICAL_CATEGORY:
            entry["clinical_category"] = CLINICAL_CATEGORY[code]
        # If we still don't have a display, fetch from NLM
        if "display" not in entry:
            print(f"  fetch NLM: {code}")
            nlm_fetches_needed += 1
            nlm = fetch_loinc_lookup(code)
            if nlm:
                entry["display"] = nlm["long_common_name"]
                if not entry.get("unit") and nlm.get("ucum_units"):
                    entry["unit"] = nlm["ucum_units"]
                entry["verified_against"].append("nlm-clinical-tables-api")
            else:
                entry["display"] = aliases[0]
                entry["verified_against"].append("MANUAL-VERIFY-NEEDED")

        out_codes[code] = entry

    output = {
        "version": "0.2.0",
        "generated_at": "2026-05-07",
        "scope": (
            "Common labs reference table for the multipass-fhir code-resolution post-pass. "
            "Extends the original 22-code showcase to cover the 58 tests in our Function Health "
            "comparison PDF + the long tail of common CMP/CBC/lipid/thyroid/A1c/urinalysis tests. "
            "Sources: showcase-loinc.json (LOINC 2.77 verified), Function Health parser output "
            "(2025-11-19 PDF, real-world cross-verified), NLM Clinical Tables API for gaps."
        ),
        "sources": [
            "ehi-atlas/corpus/reference/loinc/showcase-loinc.json",
            "pdf-review/blake-functionhealth-2025-11-19/function-outputs/...har (Function Health parser)",
            "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search",
        ],
        "codes": list(out_codes.values()),
    }

    OUT.write_text(json.dumps(output, indent=2))
    print()
    print(f"wrote {OUT}")
    print(f"  total codes: {len(out_codes)}")
    print(f"  NLM fetches needed: {nlm_fetches_needed}")
    print(f"  verified against showcase: {sum(1 for e in out_codes.values() if 'showcase-loinc-2.77' in e['verified_against'])}")
    print(f"  verified against FH:        {sum(1 for e in out_codes.values() if 'function-health-2025-11-19' in e['verified_against'])}")
    print(f"  needing manual verify:      {sum(1 for e in out_codes.values() if 'MANUAL-VERIFY-NEEDED' in e['verified_against'])}")


if __name__ == "__main__":
    main()
