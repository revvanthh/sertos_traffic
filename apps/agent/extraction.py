"""
Information extraction engine for SERTOS Voice AI Emergency Agent (Phase 8.1.3).

Extracts ONLY explicitly stated emergency and clinical triage information:
- Emergency type
- Location description
- Patient count
- Patient details (name, age, gender, blood group)
- Reported injuries / symptoms
- Consciousness (CONSCIOUS, UNCONSCIOUS, ALTERED, UNKNOWN)
- Breathing status (NORMAL, LABORED, NOT_BREATHING, UNKNOWN — unknown unless explicitly stated)
- Additional notes
- Missing information evaluation

Strict Guardrails:
- Zero fabrication of missing information.
- Zero clinical diagnosis.
- Operates 100% offline and deterministic as a resilient zero-cost fallback.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


class ConsciousnessStatus:
    CONSCIOUS = "CONSCIOUS"
    UNCONSCIOUS = "UNCONSCIOUS"
    ALTERED = "ALTERED"
    UNKNOWN = "UNKNOWN"


class BreathingStatus:
    NORMAL = "NORMAL"
    LABORED = "LABORED"
    NOT_BREATHING = "NOT_BREATHING"
    UNKNOWN = "UNKNOWN"


class EmergencyType:
    CARDIAC = "CARDIAC"
    TRAUMA = "TRAUMA"
    RESPIRATORY = "RESPIRATORY"
    STROKE = "STROKE"
    BURN = "BURN"
    MATERNAL = "MATERNAL"
    PEDIATRIC = "PEDIATRIC"
    POISONING = "POISONING"
    OTHER = "OTHER"


REQUIRED_TRIAGE_FIELDS = [
    ("emergency_type", "Emergency type / nature of emergency"),
    ("location_description", "Location or landmarks"),
    ("consciousness", "Patient consciousness"),
    ("breathing_status", "Patient breathing status"),
    ("injuries_or_symptoms", "Specific injuries or symptoms"),
]


def extract_emergency_information(
    new_message: str,
    prior_data: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[str], bool, str]:
    """
    Extracts structured emergency data by combining newly transcribed driver speech
    with prior conversation state.

    Returns:
        (extracted_data, missing_information, needs_confirmation, assistant_message)
    """
    data = dict(prior_data or {})
    text = new_message.strip()
    lower_text = text.lower()

    # 1. Emergency Type Extraction
    if not data.get("emergency_type"):
        if re.search(r"\b(cardiac|chest pain|heart attack|angina|cardiac arrest)\b", lower_text):
            data["emergency_type"] = EmergencyType.CARDIAC
        elif re.search(r"\b(accident|crash|collision|trauma|fall|fracture|hit and run|head injury)\b", lower_text):
            data["emergency_type"] = EmergencyType.TRAUMA
        elif re.search(r"\b(asthma|respiratory|choking|shortness of breath|dyspnea)\b", lower_text):
            data["emergency_type"] = EmergencyType.RESPIRATORY
        elif re.search(r"\b(stroke|paralysis|facial droop|seizure|convulsion)\b", lower_text):
            data["emergency_type"] = EmergencyType.STROKE
        elif re.search(r"\b(burn|burns|scald|electrocution)\b", lower_text):
            data["emergency_type"] = EmergencyType.BURN
        elif re.search(r"\b(labor|delivery|pregnant|pregnancy|maternal)\b", lower_text):
            data["emergency_type"] = EmergencyType.MATERNAL
        elif re.search(r"\b(poison|poisoning|overdose|ingestion)\b", lower_text):
            data["emergency_type"] = EmergencyType.POISONING
        elif re.search(r"\b(pediatric|child|infant|toddler|baby)\b", lower_text):
            data["emergency_type"] = EmergencyType.PEDIATRIC

    # 2. Location Extraction
    loc_match = re.search(
        r"\b(?:location(?:\s+(?:is|at))?|we\s+are\s+at|we\s+are\s+near|near|at|on|heading\s+to)\s+([A-Z0-9][^\n.!?]{2,80})",
        text,
        re.IGNORECASE,
    )
    if loc_match and not data.get("location_description"):
        candidate_loc = loc_match.group(1).strip()
        # Truncate at patient, clinical triage keywords, and sentence/clause delimiters
        candidate_loc = re.split(
            r"(?:\s*,\s*|\s+)(?:patient|victim|driver|passenger|a\s+\d{1,3}|\d{1,3}\s*[-]?\s*(?:year|yo|yr)|conscious|unconscious|breathing|bleeding|with\s+chest|with\s+severe)\b.*$",
            candidate_loc,
            flags=re.IGNORECASE,
        )[0]
        # Strip leading prepositions
        candidate_loc = re.sub(r"^(?:on|at|near|heading\s+to)\s+", "", candidate_loc, flags=re.IGNORECASE)
        candidate_loc = candidate_loc.strip().rstrip(".,-")
        # Ensure it is not simply medical jargon or trivial articles
        if len(candidate_loc) > 3 and not re.match(r"^(the|patient|a|an|unknown)$", candidate_loc, re.IGNORECASE):
            data["location_description"] = candidate_loc

    # 3. Patient Count
    if "patient_count" not in data or data["patient_count"] is None:
        count_match = re.search(r"\b(\d+)\s*(?:patients?|victims?|people|persons?)\b", lower_text)
        if count_match:
            data["patient_count"] = int(count_match.group(1))
        elif re.search(r"\b(two|2)\s*(?:patients?|victims?)\b", lower_text):
            data["patient_count"] = 2
        elif re.search(r"\b(three|3)\s*(?:patients?|victims?)\b", lower_text):
            data["patient_count"] = 3
        elif re.search(r"\b(single|one|1)\s*(?:patient|victim)\b", lower_text) or re.search(r"\b(a|an)\s+(?:\d{1,2}|male|female|man|woman|child)", lower_text):
            data["patient_count"] = 1

    # 4. Patient Details: Age, Gender, Name, Blood Group
    if not data.get("patient_details"):
        data["patient_details"] = {
            "name": None,
            "age": None,
            "gender": "UNKNOWN",
            "blood_group": None,
        }

    pd = data["patient_details"]

    # Age extraction (e.g. "45 year old", "45-year-old", "age 32", "24yo")
    if pd.get("age") is None:
        age_match = re.search(r"\b(\d{1,3})\s*[-]?\s*(?:years?[-\s]+old|yo|yrs?\b|years\s+of\s+age)", lower_text)
        if not age_match:
            age_match = re.search(r"\bage\s*(?:is|:)?\s*(\d{1,3})\b", lower_text)
        if age_match:
            age_val = int(age_match.group(1))
            if 0 <= age_val <= 125:
                pd["age"] = age_val

    # Gender extraction
    if pd.get("gender") in [None, "UNKNOWN"]:
        if re.search(r"\b(male|man|gentleman|boy)\b", lower_text):
            pd["gender"] = "MALE"
        elif re.search(r"\b(female|woman|lady|girl)\b", lower_text):
            pd["gender"] = "FEMALE"

    # Name extraction
    if not pd.get("name"):
        name_match = re.search(r"(?:patient(?:\'s)?\s+name\s+(?:is|:)?|named)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
        if name_match:
            pd["name"] = name_match.group(1).strip()

    # Blood group extraction
    if not pd.get("blood_group"):
        bg_match = re.search(r"\b(a|b|ab|o)\s*([+-]|positive|pos|negative|neg)\b", lower_text)
        if bg_match:
            grp = bg_match.group(1).upper()
            sign = "+" if "pos" in bg_match.group(2) or "+" in bg_match.group(2) else "-"
            pd["blood_group"] = f"{grp}{sign}"

    # 5. Consciousness
    if not data.get("consciousness") or data["consciousness"] == ConsciousnessStatus.UNKNOWN:
        if re.search(r"\b(unconscious|unresponsive|passed out|not responding|blacked out)\b", lower_text):
            data["consciousness"] = ConsciousnessStatus.UNCONSCIOUS
        elif re.search(r"\b(semi-conscious|confused|drowsy|disoriented|altered)\b", lower_text):
            data["consciousness"] = ConsciousnessStatus.ALTERED
        elif re.search(r"\b(conscious|alert|awake|talking|responding)\b", lower_text):
            data["consciousness"] = ConsciousnessStatus.CONSCIOUS
        else:
            data.setdefault("consciousness", ConsciousnessStatus.UNKNOWN)

    # 6. Breathing Status (Strictly unknown unless explicitly stated)
    if not data.get("breathing_status") or data["breathing_status"] == BreathingStatus.UNKNOWN:
        if re.search(r"\b(not breathing|stopped breathing|no breath|no breathing|apneic)\b", lower_text):
            data["breathing_status"] = BreathingStatus.NOT_BREATHING
        elif re.search(
            r"\b(heavy breathing|breathing (?:is )?heavy|breathing heavily|labored|gasping|struggling to breathe|shortness of breath|difficulty breathing|breathless|shallow breathing|breathing (?:is )?shallow|rapid breathing|breathing (?:is )?rapid)\b",
            lower_text,
        ):
            data["breathing_status"] = BreathingStatus.LABORED
        elif re.search(
            r"\b(breathing normally|normal breathing|breathing (?:is )?normal|breathing fine|breathing (?:is )?fine|regular breathing|breathing (?:is )?regular)\b",
            lower_text,
        ):
            data["breathing_status"] = BreathingStatus.NORMAL
        else:
            data.setdefault("breathing_status", BreathingStatus.UNKNOWN)

    # 7. Reported Injuries / Symptoms
    if "reported_injuries" not in data or not isinstance(data["reported_injuries"], list):
        data["reported_injuries"] = []

    symptom_patterns = [
        ("severe chest pain", r"\b(?:severe\s+)?chest\s+pain\b"),
        ("head injury", r"\bhead\s+injury\b"),
        ("profuse bleeding", r"\b(?:profuse|heavy|severe)\s+bleeding\b"),
        ("bleeding", r"\bbleeding\b"),
        ("suspected fracture", r"\b(?:suspected\s+)?fracture\b"),
        ("laceration", r"\blaceration[s]?\b"),
        ("burns", r"\bburn[s]?\b"),
        ("seizure", r"\bseizure[s]?\b"),
        ("vomiting", r"\bvomiting\b"),
        ("dizziness", r"\bdizziness\b"),
        ("numbness in limb", r"\bnumbness\b"),
        ("difficulty speaking", r"\bdifficulty\s+speaking|slurred\s+speech\b"),
    ]

    for label, pattern in symptom_patterns:
        if re.search(pattern, lower_text) and label not in data["reported_injuries"]:
            data["reported_injuries"].append(label)

    # 8. Additional Notes
    if "additional_notes" not in data or not isinstance(data["additional_notes"], list):
        data["additional_notes"] = []

    # Detect traffic or situational mentions
    if re.search(r"\b(heavy traffic|traffic jam|road block|congestion)\b", lower_text):
        if "Heavy traffic reported" not in data["additional_notes"]:
            data["additional_notes"].append("Heavy traffic reported")

    # 9. Missing Information Evaluation
    missing_fields: List[str] = []

    if not data.get("emergency_type"):
        missing_fields.append("emergency_type")

    if not data.get("location_description"):
        missing_fields.append("location_description")

    if data.get("consciousness") in [None, ConsciousnessStatus.UNKNOWN]:
        missing_fields.append("consciousness")

    if data.get("breathing_status") in [None, BreathingStatus.UNKNOWN]:
        missing_fields.append("breathing_status")

    if not data.get("reported_injuries"):
        missing_fields.append("reported_injuries")

    if not pd.get("age"):
        missing_fields.append("patient_age")

    if pd.get("gender") in [None, "UNKNOWN"]:
        missing_fields.append("patient_gender")

    # 10. Confirmation & Assistant Message Synthesis
    # Critical triage minimum: emergency_type, location_description, consciousness, breathing_status
    critical_missing = [
        f for f in ["emergency_type", "location_description", "consciousness", "breathing_status"]
        if f in missing_fields
    ]

    # Needs confirmation when critical items are present
    needs_confirmation = len(critical_missing) == 0

    assistant_message = _generate_assistant_message(data, missing_fields, needs_confirmation)

    return data, missing_fields, needs_confirmation, assistant_message


def _generate_assistant_message(
    data: Dict[str, Any],
    missing: List[str],
    needs_confirmation: bool,
) -> str:
    """Generates natural, focused driver voice responses without diagnosis or hallucinations."""
    # Summary snippets
    parts = []
    pd = data.get("patient_details", {})

    if pd.get("age") and pd.get("gender") != "UNKNOWN":
        parts.append(f"{pd['age']}-year-old {pd['gender'].lower()}")
    elif pd.get("age"):
        parts.append(f"{pd['age']}-year-old patient")
    elif pd.get("gender") != "UNKNOWN":
        parts.append(f"{pd['gender'].lower()} patient")

    if data.get("emergency_type"):
        parts.append(f"suspected {data['emergency_type'].lower()} case")

    if data.get("reported_injuries"):
        parts.append(f"with {', '.join(data['reported_injuries'])}")

    if data.get("location_description"):
        loc_str = data["location_description"].strip()
        if loc_str.lower().startswith("near ") or loc_str.lower().startswith("at "):
            parts.append(loc_str)
        else:
            parts.append(f"at {loc_str}")

    prefix = "Understood. " if parts else ""
    summary = ", ".join(parts) if parts else "details noted"

    if needs_confirmation:
        return (
            f"{prefix}All primary emergency details recorded: {summary}. "
            f"Consciousness: {data.get('consciousness')}, Breathing: {data.get('breathing_status')}. "
            f"Please confirm: should I alert the dispatch center and nearest hospital now?"
        )

    # Ask for top missing items
    prompts = []
    if "location_description" in missing:
        prompts.append("What is your current location or nearest landmark?")
    elif "consciousness" in missing and "breathing_status" in missing:
        prompts.append("Is the patient currently conscious and breathing normally?")
    elif "consciousness" in missing:
        prompts.append("Is the patient conscious?")
    elif "breathing_status" in missing:
        prompts.append("What is the patient's breathing status?")
    elif "emergency_type" in missing:
        prompts.append("What is the primary emergency condition?")
    elif "reported_injuries" in missing:
        prompts.append("What injuries or symptoms are being reported?")
    elif "patient_age" in missing:
        prompts.append("What is the approximate age of the patient?")

    follow_up = " ".join(prompts[:2]) if prompts else "Please provide any additional patient triage details."
    return f"{prefix}Recorded: {summary}. {follow_up}".strip()
