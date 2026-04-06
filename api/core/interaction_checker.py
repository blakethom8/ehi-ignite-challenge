"""
Drug-Drug Interaction Checker
Static lookup table of clinically significant interactions for surgical patients.
Pairs are stored as frozensets of drug class keys (order-independent).
"""

from dataclasses import dataclass


@dataclass
class Interaction:
    drug_a: str          # drug class key (matches drug_classifier keys)
    drug_b: str          # drug class key
    severity: str        # "contraindicated" | "major" | "moderate"
    mechanism: str       # brief mechanistic explanation
    clinical_effect: str # what happens clinically
    management: str      # what to do about it


# Known interactions between drug classes
INTERACTIONS: list[Interaction] = [
    Interaction(
        drug_a="anticoagulants", drug_b="antiplatelets",
        severity="major",
        mechanism="Additive inhibition of hemostasis via independent pathways",
        clinical_effect="Significantly increased bleeding risk; major hemorrhage possible",
        management="Avoid combination if possible. If necessary, use lowest effective doses and monitor closely. High-risk for surgical bleeding."
    ),
    Interaction(
        drug_a="anticoagulants", drug_b="nsaids",
        severity="major",
        mechanism="NSAIDs inhibit platelet function and may cause GI ulceration",
        clinical_effect="Increased risk of GI bleeding; potentiation of anticoagulant effect",
        management="Avoid concurrent use. Use acetaminophen for pain if anticoagulation required."
    ),
    Interaction(
        drug_a="antiplatelets", drug_b="nsaids",
        severity="moderate",
        mechanism="Additive platelet inhibition; NSAIDs may displace aspirin from COX-1",
        clinical_effect="Increased bleeding time; may reduce cardioprotective effect of low-dose aspirin",
        management="Use with caution. Separate aspirin and ibuprofen dosing by ≥8 hours if both required."
    ),
    Interaction(
        drug_a="maois", drug_b="opioids",
        severity="contraindicated",
        mechanism="MAOIs block serotonin/norepinephrine breakdown; opioids (esp. meperidine, tramadol, fentanyl) trigger serotonin release",
        clinical_effect="Serotonin syndrome: hyperthermia, agitation, clonus, autonomic instability — potentially fatal",
        management="CONTRAINDICATED. Avoid all opioids with MAOIs. If surgery required, use morphine (lower risk) only with ICU monitoring."
    ),
    Interaction(
        drug_a="maois", drug_b="antidepressants",
        severity="contraindicated",
        mechanism="Combined serotonergic activity",
        clinical_effect="Serotonin syndrome risk",
        management="CONTRAINDICATED. Requires 14-day MAOI washout before starting other serotonergic agents."
    ),
    Interaction(
        drug_a="anticoagulants", drug_b="anticonvulsants",
        severity="moderate",
        mechanism="Many anticonvulsants (phenytoin, carbamazepine) are CYP2C9 inducers — accelerate warfarin metabolism",
        clinical_effect="Reduced anticoagulant effect; increased clotting risk",
        management="Monitor INR more frequently when starting/stopping anticonvulsants. Adjust warfarin dose accordingly."
    ),
    Interaction(
        drug_a="immunosuppressants", drug_b="nsaids",
        severity="major",
        mechanism="NSAIDs reduce renal prostaglandin synthesis; cyclosporine/tacrolimus are nephrotoxic",
        clinical_effect="Acute kidney injury risk significantly elevated",
        management="Avoid NSAIDs in patients on calcineurin inhibitors. Use acetaminophen. Monitor creatinine."
    ),
    Interaction(
        drug_a="anticoagulants", drug_b="corticosteroids",
        severity="moderate",
        mechanism="Corticosteroids have intrinsic procoagulant effects but may also cause GI ulceration increasing bleeding risk",
        clinical_effect="Unpredictable INR changes; increased GI bleeding risk",
        management="Monitor INR closely when initiating or stopping steroids. Add GI prophylaxis."
    ),
    Interaction(
        drug_a="antidiabetics", drug_b="corticosteroids",
        severity="moderate",
        mechanism="Corticosteroids cause dose-dependent hyperglycemia by inducing insulin resistance",
        clinical_effect="Poor glycemic control; steroid-induced hyperglycemia",
        management="Increase glucose monitoring frequency. May need to increase insulin or antidiabetic doses during steroid course."
    ),
    Interaction(
        drug_a="jak_inhibitors", drug_b="immunosuppressants",
        severity="major",
        mechanism="Combined immunosuppression",
        clinical_effect="Markedly increased infection risk including opportunistic infections",
        management="Avoid combination. If necessary, use lowest effective doses with close infectious disease monitoring."
    ),
]


def check_interactions(active_class_keys: list[str]) -> list[Interaction]:
    """Return all interactions between the given active drug class keys."""
    found = []
    keys = set(active_class_keys)
    for interaction in INTERACTIONS:
        if interaction.drug_a in keys and interaction.drug_b in keys:
            found.append(interaction)
    # Sort: contraindicated first, then major, then moderate
    severity_order = {"contraindicated": 0, "major": 1, "moderate": 2}
    return sorted(found, key=lambda i: severity_order.get(i.severity, 9))
