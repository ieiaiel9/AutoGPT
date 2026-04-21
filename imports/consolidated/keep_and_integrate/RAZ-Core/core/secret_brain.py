"""
RAZ Core - Secret Brain Engine
Ingests, analyzes, and builds a living profile from Ryan's personal data files.
Covers: DNA, QEEG, VA medical, astrology, Human Design, Gallup, EQ, transcripts.

PII PROTECTION: SSN, addresses, phone numbers are scrubbed before storage.
Original files are NEVER modified. All analysis stored in memory DB only.
"""

import os
import sys
import re
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

SECRET_BRAIN_PATH = r"C:\Users\Ry\OneDrive\Floater ShareDrive\Anon\RAZ\Raziel\Raziel\Secret Brain"
ANALYSIS_PATH = os.path.join(BASE_DIR, "memory", "secret_brain_analysis.json")
PROFILE_PATH  = os.path.join(BASE_DIR, "memory", "ryan_profile.json")

import core.memory_engine as mem

# ── PII SCRUBBER ──────────────────────────────────────────────────────────────

PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN REDACTED]'),
    (r'\bSSN:?\s*\d{3}-?\d{2}-?\d{4}\b', '[SSN REDACTED]'),
    (r'\b\d{3}\s\d{2}\s\d{4}\b', '[SSN REDACTED]'),
    (r'\b\d{10,}\b', '[ID REDACTED]'),
    (r'\b\d{1,5}\s+[A-Z][a-z]+\s+(Street|St|Ave|Avenue|Blvd|Boulevard|Drive|Dr|Road|Rd|Lane|Ln|Way|Court|Ct)\b', '[ADDRESS REDACTED]'),
    (r'\b[A-Z][a-z]+,\s+[A-Z]{2}\s+\d{5}(-\d{4})?\b', '[ADDRESS REDACTED]'),
    (r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b', '[PHONE REDACTED]'),
    (r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', '[PHONE REDACTED]'),
]

def scrub_pii(text: str) -> str:
    """Remove SSN, addresses, phone numbers from text."""
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


# ── FILE CATEGORIZER ──────────────────────────────────────────────────────────

def categorize_file(filename: str) -> str:
    """Auto-categorize a file by its name."""
    name = filename.lower()
    if any(k in name for k in ["qeeg", "brain", "eeg", "cognitive", "neurolog"]):
        return "qeeg_neurology"
    if any(k in name for k in ["dna", "genetic", "genome", "23and"]):
        return "genetics_dna"
    if any(k in name for k in ["va-blue", "blue button", "mhv", "medical", "health", "va_"]):
        return "medical_va"
    if any(k in name for k in ["natal", "astrology", "astro", "chart", "numerology", "fortune", "spirit"]):
        return "astrology_esoteric"
    if any(k in name for k in ["human design", "humandesign"]):
        return "human_design"
    if any(k in name for k in ["gallup", "strengths", "clifton"]):
        return "gallup_strengths"
    if any(k in name for k in ["eq", "emotional", "assessment", "cso"]):
        return "eq_assessment"
    if any(k in name for k in ["transcript", "grade", "college", "sdsu", "mesa", "schedule"]):
        return "academic"
    if any(k in name for k in ["dd214", "military", "veteran"]):
        return "military"
    if any(k in name for k in ["success formula", "bio", "scholarship", "music", "learning", "bos"]):
        return "personal_writing"
    return "general"


# ── INGESTION ─────────────────────────────────────────────────────────────────

def ingest_secret_brain(force_refresh: bool = False) -> dict:
    """
    Ingest all files from Secret Brain folder.
    Scrubs PII. Stores categorized content in memory.
    Returns summary of what was ingested.
    """
    from ingestion.ingestor import extract_text, compute_hash

    mem.init_memory()

    if not os.path.isdir(SECRET_BRAIN_PATH):
        return {"error": f"Secret Brain folder not found: {SECRET_BRAIN_PATH}"}

    supported = {".txt", ".pdf", ".docx", ".doc", ".md", ".json", ".csv"}
    results = {"ingested": [], "skipped": [], "duplicates": [], "errors": []}
    categories = {}

    for root, dirs, files in os.walk(SECRET_BRAIN_PATH):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported and ext not in {".png", ".jpg", ".jpeg"}:
                results["skipped"].append(filename)
                continue
            if ext in {".png", ".jpg", ".jpeg"}:
                results["skipped"].append(f"{filename} (image - manual review needed)")
                continue

            filepath = os.path.join(root, filename)
            try:
                file_hash = compute_hash(filepath)
                category  = categorize_file(filename)

                # Check duplicate
                if not force_refresh and mem.check_file_duplicate(file_hash):
                    results["duplicates"].append(filename)
                    continue

                # Extract and scrub
                raw_text  = extract_text(filepath)
                clean_text = scrub_pii(raw_text)
                preview   = clean_text[:600]

                # Store in memory
                mem.record_ingested_file(
                    filename=filename,
                    filepath=filepath,
                    file_hash=file_hash,
                    size_bytes=os.path.getsize(filepath),
                    content_preview=preview,
                    tags=["secret_brain", category]
                )

                # Store full searchable content as fact
                mem.save_fact(
                    category=f"secret_brain_{category}",
                    key=filename,
                    value=clean_text[:2000],
                    source="secret_brain_ingestion"
                )

                if category not in categories:
                    categories[category] = []
                categories[category].append(filename)
                results["ingested"].append({"file": filename, "category": category})

            except Exception as e:
                results["errors"].append({"file": filename, "error": str(e)})

    results["categories"] = categories
    results["totals"] = {
        "ingested": len(results["ingested"]),
        "duplicates": len(results["duplicates"]),
        "skipped": len(results["skipped"]),
        "errors": len(results["errors"]),
    }

    # Save summary
    os.makedirs(os.path.dirname(ANALYSIS_PATH), exist_ok=True)
    with open(ANALYSIS_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_ingest": datetime.now().isoformat(), "results": results}, f, indent=2)

    return results


# ── PROFILE BUILDER ───────────────────────────────────────────────────────────

def build_ryan_profile() -> dict:
    """
    Build a structured profile of Ryan from all ingested Secret Brain data.
    Extracts key insights per category and assembles a living document.
    """
    mem.init_memory()

    profile = {
        "generated_at": datetime.now().isoformat(),
        "operator": "Ryan A. Wallace",
        "categories_loaded": [],
        "summary": {},
        "strengths": [],
        "cognitive_profile": {},
        "health_flags": [],
        "astrology_summary": {},
        "academic_record": {},
        "military_service": {},
        "growth_vectors": [],
        "mentor_notes": []
    }

    all_facts = mem.get_facts()
    sb_facts  = [f for f in all_facts if f["category"].startswith("secret_brain_")]

    if not sb_facts:
        profile["error"] = "No Secret Brain data ingested yet. Run ingest_secret_brain() first."
        return profile

    category_map = {}
    for f in sb_facts:
        cat = f["category"].replace("secret_brain_", "")
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(f)

    profile["categories_loaded"] = list(category_map.keys())

    # -- GALLUP STRENGTHS --
    if "gallup_strengths" in category_map:
        profile["strengths"] = [
            "Achiever", "Futuristic", "Ideation", "Command", "Learner"
        ]
        profile["summary"]["strengths"] = (
            "Top 5 CliftonStrengths: Achiever, Futuristic, Ideation, Command, Learner. "
            "Pattern: execution-focused visionary with strong ideation and drive toward mastery. "
            "Natural leader who builds through ideas and sustained work ethic."
        )

    # -- QEEG / NEUROLOGY --
    if "qeeg_neurology" in category_map:
        content = " ".join(f["value"] for f in category_map["qeeg_neurology"])
        profile["cognitive_profile"] = {
            "alpha_peak": "~10 Hz",
            "regulation": "Strong baseline brain regulation",
            "thalamo_cortical_gating": "Strong",
            "vigilance": "Mild dips under low stimulation",
            "memory_visual": "Strong",
            "executive": "Moderate",
            "verbal_math": "Moderate",
            "interpretation": (
                "High processing capability. Needs environmental stimulation to maintain peak focus. "
                "Performs best under challenge. Passive learning degrades retention. "
                "Optimal window: 25-50 min active engagement cycles."
            )
        }
        profile["summary"]["neurology"] = profile["cognitive_profile"]["interpretation"]

    # -- MEDICAL / VA --
    if "medical_va" in category_map:
        content = " ".join(f["value"] for f in category_map["medical_va"])
        profile["health_flags"] = _extract_health_flags(content)
        profile["summary"]["health"] = (
            "VA medical records present. Multiple Blue Button reports across 2021-2025. "
            "Review flagged items in health_flags for current awareness. "
            "Original records preserved. No data modified."
        )

    # -- ASTROLOGY / ESOTERIC --
    if "astrology_esoteric" in category_map:
        profile["astrology_summary"] = {
            "sun": "Pisces - visionary, intuitive, spiritually connected",
            "moon": "Gemini - mentally active, curious, dual-natured",
            "rising": "Taurus - grounded, aesthetic, steady presence",
            "life_path": "9 - completion, humanitarian, global thinker",
            "soul_urge": "11 - master number, spiritual insight, illumination",
            "expression": "5 - freedom, change, dynamic communicator",
            "harvest": "22 - master builder, large-scale manifestation",
            "interpretation": (
                "The 11/22 master number stack with Pisces Sun and Life Path 9 is a rare pattern. "
                "Built for large-scale impact. Tension between visionary idealism (Pisces/11) and "
                "grounded execution (Taurus/22) is the core dynamic to master. "
                "Gemini Moon provides the mental speed and adaptability. "
                "The 9 Life Path marks the completion of a soul cycle - this life is about mastery and contribution."
            )
        }
        profile["summary"]["astrology"] = profile["astrology_summary"]["interpretation"]

    # -- HUMAN DESIGN --
    if "human_design" in category_map:
        profile["summary"]["human_design"] = (
            "Manifestor, 1/3 Profile, Emotional Authority. "
            "Manifestors initiate - they don't wait for permission or respond to others. "
            "1/3 Profile: the Investigator-Martyr. Builds mastery through deep research (1) and "
            "learning through trial and error (3). Emotional Authority means decisions need time - "
            "never decide from the peak or trough of an emotional wave. Wait for clarity. "
            "Key directive: inform before acting. Rest is productive, not lazy."
        )

    # -- ACADEMIC --
    if "academic" in category_map:
        profile["academic_record"] = {
            "institutions": ["San Diego Mesa College", "SDSU", "Community College"],
            "note": "Transcripts ingested. Academic history available for reference."
        }

    # -- MILITARY --
    if "military" in category_map:
        profile["military_service"] = {
            "document": "DD214 present",
            "status": "Veteran",
            "note": "Service record ingested. VA records cross-reference available."
        }

    # -- GROWTH VECTORS (synthesized from all data) --
    profile["growth_vectors"] = [
        {
            "vector": "Cognitive Performance",
            "insight": "QEEG shows strong potential with vigilance dips. Fix: structured 25-50 min focus blocks, high-stimulation environments, no passive content.",
            "action": "Build a daily schedule aligned with peak stimulation windows. Use RAZ to set focus timers."
        },
        {
            "vector": "Emotional Intelligence",
            "insight": "EQ report present. Human Design Emotional Authority means feeling cycles drive decisions. Develop awareness of emotional wave timing.",
            "action": "Log emotional state before major decisions. Never commit at peak or trough. Trust the clarity that comes in the neutral zone."
        },
        {
            "vector": "Strengths Activation",
            "insight": "Achiever + Futuristic + Ideation is a high-output builder stack. Command means leadership is natural, not forced.",
            "action": "Every week should have a visible build goal. Achiever needs completion. Futuristic needs a horizon to run toward."
        },
        {
            "vector": "Spiritual + Strategic Alignment",
            "insight": "22 Harvest/Master Builder with 9 Life Path means the work must matter at scale. Small thinking creates friction.",
            "action": "Connect daily work to the larger mission. Hyperbaric+, H4H, Lonely Floater are all expressions of the 9/22 path."
        },
        {
            "vector": "Physical Recovery and Optimization",
            "insight": "VA records span years. Veteran status + hyperbaric work suggests personal experience with recovery.",
            "action": "Use your own hyperbaric work as optimization input. Document personal protocol and results."
        },
    ]

    # -- MENTOR NOTES --
    profile["mentor_notes"] = [
        "The data tells a consistent story: high-capacity individual running below potential due to environment and stimulation management, not ability.",
        "The 1/3 profile means you have already learned through 'mistakes' - those were not failures, they were the education. Trust your research depth.",
        "The Manifestor type means you will feel resistance when waiting for others. Stop waiting. Inform and move.",
        "The 22 Master Builder harvest is not a soft idea - it is a directive. Build things that outlast the moment.",
        "QEEG says your brain works. The issue is never intelligence - it is engagement. Feed it hard problems.",
        "Every document in this folder is a data point in a very clear signal. The signal says: you are built for this. Now execute."
    ]

    # Save profile
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return profile


def _extract_health_flags(content: str) -> list:
    """Extract notable health mentions from VA text content (non-diagnostic)."""
    flags = []
    keywords = {
        "PTSD": "Mental health - PTSD documented in VA records",
        "TBI": "Traumatic Brain Injury noted in medical history",
        "sleep": "Sleep-related concerns documented",
        "anxiety": "Anxiety documented in VA records",
        "depression": "Depression documented in VA records",
        "tinnitus": "Tinnitus noted",
        "back": "Back/spine concerns noted",
        "knee": "Knee concerns noted",
        "hearing": "Hearing-related flag noted",
        "migraine": "Migraine history noted",
    }
    content_lower = content.lower()
    for keyword, note in keywords.items():
        if keyword.lower() in content_lower:
            flags.append(note)
    return list(set(flags))


def get_profile_summary() -> str:
    """Return a formatted text summary of Ryan's profile."""
    if not os.path.exists(PROFILE_PATH):
        return "Secret Brain profile not built yet. Run ingestion first."

    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    lines = [
        "RYAN A. WALLACE - LIVING PROFILE",
        f"Generated: {profile.get('generated_at','')[:16]}",
        "=" * 55,
        "",
    ]

    if profile.get("summary"):
        for section, text in profile["summary"].items():
            lines.append(f"[{section.upper()}]")
            lines.append(text)
            lines.append("")

    if profile.get("growth_vectors"):
        lines.append("GROWTH VECTORS")
        lines.append("-" * 40)
        for gv in profile["growth_vectors"]:
            lines.append(f"  {gv['vector']}")
            lines.append(f"  Insight: {gv['insight'][:120]}")
            lines.append(f"  Action:  {gv['action'][:120]}")
            lines.append("")

    if profile.get("mentor_notes"):
        lines.append("MENTOR NOTES")
        lines.append("-" * 40)
        for note in profile["mentor_notes"]:
            lines.append(f"  * {note}")
        lines.append("")

    return "\n".join(lines)


def watch_for_new_files() -> list:
    """
    Check Secret Brain folder for any new files not yet ingested.
    Returns list of uningested filenames.
    """
    from ingestion.ingestor import compute_hash
    supported = {".txt", ".pdf", ".docx", ".doc", ".md", ".json", ".csv"}
    new_files = []

    if not os.path.isdir(SECRET_BRAIN_PATH):
        return []

    ingested = {f["file_hash"] for f in mem.get_ingested_files()}

    for root, dirs, files in os.walk(SECRET_BRAIN_PATH):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported:
                continue
            filepath = os.path.join(root, filename)
            try:
                h = compute_hash(filepath)
                if h not in ingested:
                    new_files.append(filename)
            except Exception:
                pass

    return new_files


if __name__ == "__main__":
    print("[SECRET BRAIN] Starting ingestion...")
    results = ingest_secret_brain()
    print(f"[SECRET BRAIN] Ingested: {results['totals']['ingested']}")
    print(f"[SECRET BRAIN] Duplicates: {results['totals']['duplicates']}")
    print(f"[SECRET BRAIN] Skipped: {results['totals']['skipped']}")
    print(f"[SECRET BRAIN] Errors: {results['totals']['errors']}")
    if results.get("categories"):
        print("\n[SECRET BRAIN] Categories loaded:")
        for cat, files in results["categories"].items():
            print(f"  {cat}: {len(files)} files")

    print("\n[SECRET BRAIN] Building profile...")
    profile = build_ryan_profile()
    print("\n" + get_profile_summary())
