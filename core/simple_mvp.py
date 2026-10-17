from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable
import json
import os
import time

try:
    from .localization import is_english, localized
except ImportError:
    from localization import is_english, localized
from openai import OpenAI, RateLimitError

try:
    from retrieval import retrieve_sectioned_task_unit_evidence
except ModuleNotFoundError:
    from .retrieval import retrieve_sectioned_task_unit_evidence
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIENCE_FILE = PROJECT_ROOT / "data" / "exp_bank.txt"
JD_FILE = PROJECT_ROOT / "data" / "sample_jd.txt"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
SAVE_OUTPUTS = os.getenv("CARIAGENT_SAVE_OUTPUTS", "1") == "1"
PROMPT_DIR = PROJECT_ROOT / "prompts"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "180"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
OPENAI_RETRY_SECONDS = float(os.getenv("OPENAI_RETRY_SECONDS", "40"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
MAX_RETRIEVAL_CONTEXT_CHARS = int(os.getenv("MAX_RETRIEVAL_CONTEXT_CHARS", "0"))
STEP_MODELS = {
    "context": os.getenv("OPENAI_MODEL_CONTEXT", DEFAULT_MODEL),
    "section_parser": os.getenv("OPENAI_MODEL_SECTION_PARSER", DEFAULT_MODEL),
    "s3": os.getenv("OPENAI_MODEL_S3", DEFAULT_MODEL),
    "s4": os.getenv("OPENAI_MODEL_S4", DEFAULT_MODEL),
    "fit_verdict": os.getenv("OPENAI_MODEL_FIT_VERDICT", DEFAULT_MODEL),
    "input_quality": os.getenv("OPENAI_MODEL_INPUT_QUALITY", DEFAULT_MODEL),
    "s5": os.getenv("OPENAI_MODEL_S5", DEFAULT_MODEL),
    "s6": os.getenv(
        "OPENAI_MODEL_S6", os.getenv("OPENAI_MODEL_FOLLOWUP", DEFAULT_MODEL)
    ),
    "s7": os.getenv(
        "OPENAI_MODEL_S7", os.getenv("OPENAI_MODEL_FOLLOWUP", DEFAULT_MODEL)
    ),
    "s8": os.getenv("OPENAI_MODEL_S8", DEFAULT_MODEL),
}
READINESS_THRESHOLD = 0.8
SCORING_VERSION = "readiness_formula_v0.2"
COVERAGE_RUBRIC_VERSION = "coverage_rubric_v0.2"
MIN_EXPECTED_GAIN = 0.05
MAX_QUESTIONS = 10
MAX_TOPIC_FOLLOWUPS = 2
TOPIC_CLARIFICATION_BUDGET = 1
EXIT_WORDS = {"done", "End", "Generate first", "Exit", "No more questions"}
SKIP_WORDS = {
    "pass",
    "No",
    "None",
    "Don't know",
    "Unclear",
    "Next",
    "Skip",
    "Pass",
    "That's all",
    "No thanks",
}
EXIT_WORDS |= {"finish", "stop", "generate now"}
SKIP_WORDS |= {"skip", "none", "n/a", "not sure", "i don't know", "i do not know"}
CHUNKS_PER_TASK_UNIT = int(
    os.getenv("CHUNKS_PER_TASK_UNIT", os.getenv("CHUNKS_PER_REQUIREMENT", "3"))
)
MAX_RETRIEVED_CHUNKS = int(os.getenv("MAX_RETRIEVED_CHUNKS", "18"))
PROFESSIONAL_SECTION_KEYS = {"work_experience", "internship_experience"}
PROJECT_SECTION_KEYS = {"project_experience"}
SECTION_RETRIEVAL_QUOTAS = {
    "professional_experience": int(os.getenv("PROFESSIONAL_RETRIEVAL_QUOTA", "12")),
    "project_experience": int(os.getenv("PROJECT_RETRIEVAL_QUOTA", "6")),
    "campus_other_experience": int(os.getenv("OTHER_RETRIEVAL_QUOTA", "3")),
}
API_CALL_TRACE: list[dict] = []


def object_schema(properties: dict, required: list[str]) -> dict:
    """Generate the strict object schema required for Structured Outputs."""
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TEXT_ARRAY_SCHEMA = {"type": "array", "items": {"type": "string"}}
EXPERIENCE_RECORD_SCHEMA = object_schema(
    {
        "record_title": {"type": "string"},
        "organization": {"type": "string"},
        "role": {"type": "string"},
        "time_range": {"type": "string"},
        "content": {"type": "string"},
    },
    ["record_title", "organization", "role", "time_range", "content"],
)
JD_ANALYSIS_SCHEMA = object_schema(
    {
        "role_title": {"type": "string"},
        "job_goal": {"type": "string"},
        "basic_requirements": TEXT_ARRAY_SCHEMA,
        "core_responsibilities": TEXT_ARRAY_SCHEMA,
        "ksa_requirements": object_schema(
            {
                "knowledge": {
                    "type": "array",
                    "items": object_schema(
                        {
                            "item": {"type": "string"},
                            "importance": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "evidence_needed_on_resume": {"type": "string"},
                        },
                        ["item", "importance", "evidence_needed_on_resume"],
                    ),
                },
                "skills": {
                    "type": "array",
                    "items": object_schema(
                        {
                            "item": {"type": "string"},
                            "importance": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "evidence_needed_on_resume": {"type": "string"},
                        },
                        ["item", "importance", "evidence_needed_on_resume"],
                    ),
                },
                "abilities": {
                    "type": "array",
                    "items": object_schema(
                        {
                            "item": {"type": "string"},
                            "importance": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "evidence_needed_on_resume": {"type": "string"},
                        },
                        ["item", "importance", "evidence_needed_on_resume"],
                    ),
                },
            },
            ["knowledge", "skills", "abilities"],
        ),
        "keyword_map": {
            "type": "array",
            "items": object_schema(
                {
                    "keyword": {"type": "string"},
                    "ksa_type": {
                        "type": "string",
                        "enum": ["knowledge", "skill", "ability", "other"],
                    },
                    "why_it_matters": {"type": "string"},
                },
                ["keyword", "ksa_type", "why_it_matters"],
            ),
        },
        "keywords_to_mirror": TEXT_ARRAY_SCHEMA,
    },
    [
        "role_title",
        "job_goal",
        "basic_requirements",
        "core_responsibilities",
        "ksa_requirements",
        "keyword_map",
        "keywords_to_mirror",
    ],
)
EXPERIENCE_SECTIONS_SCHEMA = object_schema(
    {
        "experience_sections": {
            "type": "array",
            "items": object_schema(
                {
                    "section_key": {
                        "type": "string",
                        "enum": [
                            "basic_information",
                            "profile",
                            "education",
                            "work_experience",
                            "internship_experience",
                            "project_experience",
                            "campus_experience",
                            "club_experience",
                            "volunteer_experience",
                            "awards",
                            "skills",
                            "certifications",
                            "hobbies",
                            "other",
                        ],
                    },
                    "section_name": {"type": "string"},
                    "content": {"type": "string"},
                    "experience_records": {
                        "type": "array",
                        "items": EXPERIENCE_RECORD_SCHEMA,
                    },
                    "why_this_section": {"type": "string"},
                },
                [
                    "section_key",
                    "section_name",
                    "content",
                    "experience_records",
                    "why_this_section",
                ],
            ),
        },
        "parsing_notes": TEXT_ARRAY_SCHEMA,
    },
    ["experience_sections", "parsing_notes"],
)
EXPERIENCE_ATOMS_SCHEMA = object_schema(
    {
        "available_sections": {
            "type": "array",
            "items": object_schema(
                {
                    "section_key": {"type": "string"},
                    "section_name": {"type": "string"},
                    "why_available": {"type": "string"},
                },
                ["section_key", "section_name", "why_available"],
            ),
        },
        "experience_atoms": {
            "type": "array",
            "items": object_schema(
                {
                    "id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "section_key": {"type": "string"},
                    "source_experience": {"type": "string"},
                    "star": object_schema(
                        {
                            "situation": {"type": "string"},
                            "task": {"type": "string"},
                            "actions": TEXT_ARRAY_SCHEMA,
                            "results": TEXT_ARRAY_SCHEMA,
                        },
                        ["situation", "task", "actions", "results"],
                    ),
                    "tools": TEXT_ARRAY_SCHEMA,
                    "ksa_evidence": object_schema(
                        {
                            "knowledge": TEXT_ARRAY_SCHEMA,
                            "skills": TEXT_ARRAY_SCHEMA,
                            "abilities": TEXT_ARRAY_SCHEMA,
                        },
                        ["knowledge", "skills", "abilities"],
                    ),
                    "capability_tags": TEXT_ARRAY_SCHEMA,
                    "star_gaps": TEXT_ARRAY_SCHEMA,
                    "missing_details": TEXT_ARRAY_SCHEMA,
                },
                [
                    "id",
                    "display_name",
                    "section_key",
                    "source_experience",
                    "star",
                    "tools",
                    "ksa_evidence",
                    "capability_tags",
                    "star_gaps",
                    "missing_details",
                ],
            ),
        },
    },
    ["available_sections", "experience_atoms"],
)
INPUT_QUALITY_SCHEMA = object_schema(
    {
        "overall_quality": {"type": "string", "enum": ["high", "medium", "low"]},
        "summary": {"type": "string"},
        "strengths": TEXT_ARRAY_SCHEMA,
        "common_gaps": TEXT_ARRAY_SCHEMA,
        "experience_level_gaps": {
            "type": "array",
            "items": object_schema(
                {
                    "experience_name": {"type": "string"},
                    "missing_star_fields": TEXT_ARRAY_SCHEMA,
                    "missing_details": TEXT_ARRAY_SCHEMA,
                },
                ["experience_name", "missing_star_fields", "missing_details"],
            ),
        },
        "user_message": {"type": "string"},
    },
    [
        "overall_quality",
        "summary",
        "strengths",
        "common_gaps",
        "experience_level_gaps",
        "user_message",
    ],
)
MATCH_RESULT_SCHEMA = object_schema(
    {
        "matches": {
            "type": "array",
            "items": object_schema(
                {
                    "ksa_type": {
                        "type": "string",
                        "enum": ["knowledge", "skill", "ability"],
                    },
                    "jd_requirement": {"type": "string"},
                    "importance": {"type": "string", "enum": ["high", "medium", "low"]},
                    "matched_experience_ids": TEXT_ARRAY_SCHEMA,
                    "matched_experience_names": TEXT_ARRAY_SCHEMA,
                    "match_level": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "none"],
                    },
                    "evidence": {"type": "string"},
                    "evidence_quality": {
                        "type": "string",
                        "enum": ["strong", "partial", "weak", "none"],
                    },
                    "gap": {"type": "string"},
                },
                [
                    "ksa_type",
                    "jd_requirement",
                    "importance",
                    "matched_experience_ids",
                    "matched_experience_names",
                    "match_level",
                    "evidence",
                    "evidence_quality",
                    "gap",
                ],
            ),
        },
        "overall_summary": {"type": "string"},
    },
    ["matches", "overall_summary"],
)
FIT_VERDICT_SCHEMA = object_schema(
    {
        "fit_level": {
            "type": "string",
            "enum": ["high_fit", "good_fit", "partial_fit", "weak_fit", "low_fit"],
        },
        "fit_summary": {"type": "string"},
        "major_matches": TEXT_ARRAY_SCHEMA,
        "major_gaps": TEXT_ARRAY_SCHEMA,
        "recommendation": {
            "type": "string",
            "enum": ["continue", "continue_with_caution", "reconsider"],
        },
        "user_message": {"type": "string"},
    },
    [
        "fit_level",
        "fit_summary",
        "major_matches",
        "major_gaps",
        "recommendation",
        "user_message",
    ],
)
FOLLOWUP_PLAN_SCHEMA = object_schema(
    {
        "candidate_questions": {
            "type": "array",
            "items": object_schema(
                {
                    "id": {"type": "string"},
                    "question_type": {
                        "type": "string",
                        "enum": ["ksa_gap", "star_gap"],
                    },
                    "gap_priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "target_requirement": {"type": "string"},
                    "target_ksa_type": {
                        "type": "string",
                        "enum": ["knowledge", "skill", "ability", "none"],
                    },
                    "target_star_field": {
                        "type": "string",
                        "enum": ["situation", "task", "action", "result", "none"],
                    },
                    "related_experience_id": {"type": "string"},
                    "related_experience_name": {"type": "string"},
                    "question": {"type": "string"},
                    "why_ask": {"type": "string"},
                    "improvability": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "theoretical_improvement": object_schema(
                        {
                            "coverage_before": {"type": "number"},
                            "coverage_after_if_answered": {"type": "number"},
                        },
                        ["coverage_before", "coverage_after_if_answered"],
                    ),
                    "priority_reason": {"type": "string"},
                },
                [
                    "id",
                    "question_type",
                    "gap_priority",
                    "target_requirement",
                    "target_ksa_type",
                    "target_star_field",
                    "related_experience_id",
                    "related_experience_name",
                    "question",
                    "why_ask",
                    "improvability",
                    "theoretical_improvement",
                    "priority_reason",
                ],
            ),
        },
        "planning_summary": {"type": "string"},
    },
    ["candidate_questions", "planning_summary"],
)
REVIEWED_ANSWERS_SCHEMA = object_schema(
    {
        "reviewed_answers": {
            "type": "array",
            "items": object_schema(
                {
                    "question_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["answered", "pass", "off_topic"],
                    },
                    "answered_ksa_type": {
                        "type": "string",
                        "enum": ["knowledge", "skill", "ability", "none"],
                    },
                    "answered_star_field": {
                        "type": "string",
                        "enum": ["situation", "task", "action", "result", "none"],
                    },
                    "usable_information": TEXT_ARRAY_SCHEMA,
                    "reason": {"type": "string"},
                    "clarification_prompt": {"type": "string"},
                    "belongs_to_experience_id": {"type": "string"},
                    "belongs_to_experience_name": {"type": "string"},
                    "is_new_experience": {"type": "boolean"},
                    "current_run_only": {"type": "boolean"},
                },
                [
                    "question_id",
                    "status",
                    "answered_ksa_type",
                    "answered_star_field",
                    "usable_information",
                    "reason",
                    "clarification_prompt",
                    "belongs_to_experience_id",
                    "belongs_to_experience_name",
                    "is_new_experience",
                    "current_run_only",
                ],
            ),
        },
        "updated_experience_notes": TEXT_ARRAY_SCHEMA,
    },
    ["reviewed_answers", "updated_experience_notes"],
)
TOPIC_FOLLOWUP_SCHEMA = object_schema(
    {
        "should_follow_up": {"type": "boolean"},
        "question_type": {"type": "string", "enum": ["ksa_gap", "star_gap"]},
        "gap_priority": {"type": "string", "enum": ["high", "medium", "low"]},
        "target_requirement": {"type": "string"},
        "target_ksa_type": {
            "type": "string",
            "enum": ["knowledge", "skill", "ability", "none"],
        },
        "target_star_field": {
            "type": "string",
            "enum": ["situation", "task", "action", "result", "none"],
        },
        "question": {"type": "string"},
        "why_ask": {"type": "string"},
        "improvability": {"type": "string", "enum": ["high", "medium", "low"]},
        "theoretical_improvement": object_schema(
            {
                "coverage_before": {"type": "number"},
                "coverage_after_if_answered": {"type": "number"},
            },
            ["coverage_before", "coverage_after_if_answered"],
        ),
        "priority_reason": {"type": "string"},
    },
    [
        "should_follow_up",
        "question_type",
        "gap_priority",
        "target_requirement",
        "target_ksa_type",
        "target_star_field",
        "question",
        "why_ask",
        "improvability",
        "theoretical_improvement",
        "priority_reason",
    ],
)
RESUME_OUTPUT_SCHEMA = object_schema(
    {
        "resume_markdown": {"type": "string"},
        "improvement_suggestions_markdown": {"type": "string"},
    },
    ["resume_markdown", "improvement_suggestions_markdown"],
)
SCHEMAS = {
    "resume_output": RESUME_OUTPUT_SCHEMA,
    "jd_analysis": JD_ANALYSIS_SCHEMA,
    "experience_sections": EXPERIENCE_SECTIONS_SCHEMA,
    "experience_atoms": EXPERIENCE_ATOMS_SCHEMA,
    "input_quality": INPUT_QUALITY_SCHEMA,
    "match_result": MATCH_RESULT_SCHEMA,
    "fit_verdict": FIT_VERDICT_SCHEMA,
    "followup_plan": FOLLOWUP_PLAN_SCHEMA,
    "reviewed_answers": REVIEWED_ANSWERS_SCHEMA,
    "topic_followup": TOPIC_FOLLOWUP_SCHEMA,
}


def read_text_file(file_path: Path) -> str:
    """Read the content of a txt file."""
    return file_path.read_text(encoding="utf-8").strip()


def save_json(file_name: str, data: dict) -> None:
    """Save the Python dictionary as a JSON file for us to review intermediate results."""
    if not SAVE_OUTPUTS:
        return
    file_path = OUTPUT_DIR / file_name
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_markdown(file_name: str, text: str) -> None:
    """Save the final resume content as a Markdown file."""
    if not SAVE_OUTPUTS:
        return
    file_path = OUTPUT_DIR / file_name
    file_path.write_text(text, encoding="utf-8")


def save_experience_updates(notes: list) -> None:
    """Save the user's additional facts as lightweight update records for reuse in subsequent processes."""
    if not SAVE_OUTPUTS:
        return
    file_path = OUTPUT_DIR / "experience_updates.json"
    existing = []
    if file_path.exists():
        existing = json.loads(file_path.read_text(encoding="utf-8"))
    merged = deduplicate_items(existing + notes)
    file_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_prompt(file_name: str) -> str:
    """Read a txt prompt file so you can directly edit the prompt text later."""
    directory = PROMPT_DIR
    return (directory / file_name).read_text(encoding="utf-8")


def render_prompt(template: str, **values: str) -> str:
    """Replace the placeholders in the prompt with real content."""
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def parse_json_response_text(text: str) -> dict:
    """Parse the model's returned JSON, compatible with ```json fenced blocks."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    return json.loads(cleaned)


def to_prompt_json(data) -> str:
    """Serialize context for prompts without pretty-print whitespace."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def json_char_len(data) -> int:
    """Rough payload size for API slimming diagnostics."""
    if isinstance(data, str):
        return len(data)
    return len(to_prompt_json(data))


def extract_response_usage(response) -> dict:
    """Extract token usage when the SDK response exposes it."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {
        key: getattr(usage, key)
        for key in ["input_tokens", "output_tokens", "total_tokens"]
        if hasattr(usage, key)
    }


def record_api_call(
    *,
    call_name: str,
    model: str,
    prompt: str,
    response,
    response_type: str,
    schema_name: str = "",
    elapsed_seconds: float | None = None,
) -> None:
    """Record only size/usage metadata for each API call."""
    entry = {
        "call_name": call_name or "unnamed_call",
        "model": model,
        "response_type": response_type,
        "schema_name": schema_name,
        "prompt_chars": len(prompt or ""),
        "output_chars": len(getattr(response, "output_text", "") or ""),
        "usage": extract_response_usage(response),
    }
    if elapsed_seconds is not None:
        entry["elapsed_seconds"] = round(elapsed_seconds, 2)
    API_CALL_TRACE.append(entry)
    save_json("00_api_call_trace.json", {"calls": API_CALL_TRACE})


def create_response_with_retry(client: OpenAI, **kwargs):
    """Create a response with simple backoff for TPM rate limits."""
    kwargs.setdefault("temperature", OPENAI_TEMPERATURE)
    for attempt in range(OPENAI_MAX_RETRIES + 1):
        try:
            return client.responses.create(**kwargs)
        except RateLimitError:
            if attempt >= OPENAI_MAX_RETRIES:
                raise
            wait_seconds = OPENAI_RETRY_SECONDS * (attempt + 1)
            print(
                f"Encountered OpenAI rate limit, will retry automatically after waiting {wait_seconds:.0f} seconds..."
            )
            time.sleep(wait_seconds)


def parse_json_response_or_raise(response, schema_name: str) -> dict:
    try:
        return parse_json_response_text(response.output_text)
    except json.JSONDecodeError:
        debug_path = OUTPUT_DIR / f"last_invalid_json_response_{schema_name}.txt"
        if SAVE_OUTPUTS:
            debug_path.write_text(response.output_text or "", encoding="utf-8")
        raise ValueError(
            f"Model did not return parseable JSON, raw output path: {debug_path}"
        )


def build_selected_chunks_context(retrieval_result: dict) -> str:
    """Render only deduplicated selected RAG chunks for downstream atomization.

    These chunks are original evidence from the experience bank plus provenance.
    Step 4 should structure this candidate evidence, not re-read the full
    experience bank or rely on AI-generated summaries as the fact source.
    The full task-expanded retrieval map is still saved to outputs for debugging.
    """
    lines = []
    seen = set()
    evidence_index = 1
    for chunk in retrieval_result.get("selected_chunks", []):
        source = chunk.get("experience_title", "Unrecognized source experience")
        company_or_project = chunk.get("company_or_project", "")
        section_type = chunk.get("section_type", "")
        section_group = chunk.get("section_group", "")
        text = chunk.get("text", "")
        dedupe_key = (source, company_or_project, section_type, text[:220])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        lines.append(
            "\n".join(
                [
                    f"Evidence {evidence_index}",
                    f"Source experience: {source}",
                    f"Company/project: {company_or_project}",
                    f"Resume section type: {section_type}",
                    f"Retrieval section group: {section_group}",
                    f"Retrieved for JD task: {chunk.get('task_unit', '')}",
                    "Evidence text:",
                    text.strip(),
                ]
            )
        )
        evidence_index += 1
    return "\n\n".join(lines)


def build_compact_jd_context(jd_analysis: dict) -> dict:
    """Keep only fields useful for downstream workflow calls."""
    return {
        "job_goal": jd_analysis.get("job_goal", ""),
        "core_responsibilities": jd_analysis.get("core_responsibilities", []),
        "keywords_to_mirror": jd_analysis.get("keywords_to_mirror", []),
        "ksa_requirements": jd_analysis.get("ksa_requirements", {}),
    }


def build_compact_atoms_context(experience_atoms: dict) -> dict:
    """Drop section availability notes and keep atom-level evidence annotations."""
    return {"experience_atoms": experience_atoms.get("experience_atoms", [])}


def build_atoms_for_matching_context(experience_atoms: dict) -> dict:
    """Keep only atom fields needed for JD matching and readiness scoring."""
    atoms = []
    for atom in experience_atoms.get("experience_atoms", []):
        atoms.append(
            {
                "id": atom.get("id", ""),
                "display_name": atom.get("display_name", ""),
                "section_key": atom.get("section_key", ""),
                "source_experience": atom.get("source_experience", ""),
                "star": atom.get("star", {}),
                "tools": atom.get("tools", []),
                "ksa_evidence": atom.get("ksa_evidence", {}),
                "capability_tags": atom.get("capability_tags", []),
                "star_gaps": atom.get("star_gaps", []),
            }
        )
    return {"experience_atoms": atoms}


def build_atoms_for_resume_context(experience_atoms: dict) -> dict:
    """Resume generation view: facts + provenance, without internal debug fields."""
    atoms = []
    for atom in experience_atoms.get("experience_atoms", []):
        atoms.append(
            {
                "display_name": atom.get("display_name", ""),
                "section_key": atom.get("section_key", ""),
                "source_experience": atom.get("source_experience", ""),
                "star": atom.get("star", {}),
                "tools": atom.get("tools", []),
                "capability_tags": atom.get("capability_tags", []),
            }
        )
    return {"experience_atoms": atoms}


def build_direct_context_sections_for_api(sections: list[dict]) -> list[dict]:
    """Keep direct resume sections but drop parser reasoning fields."""
    return [
        {
            "section_key": section.get("section_key", ""),
            "section_name": section.get("section_name", ""),
            "content": section.get("content", ""),
        }
        for section in sections
    ]


def build_selected_evidence_summary(retrieval_result: dict) -> list[dict]:
    """Summarized retrieval view for audit/debug calls that do not need full text."""
    summaries = []
    seen = set()
    for index, chunk in enumerate(retrieval_result.get("selected_chunks", []), start=1):
        dedupe_key = (
            chunk.get("experience_title", ""),
            chunk.get("company_or_project", ""),
            chunk.get("section_type", ""),
            chunk.get("text", "")[:220],
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        summaries.append(
            {
                "evidence_no": index,
                "source_experience": chunk.get("experience_title", ""),
                "company_or_project": chunk.get("company_or_project", ""),
                "section_type": chunk.get("section_type", ""),
                "section_group": chunk.get("section_group", ""),
                "retrieved_for_jd_task": chunk.get("task_unit", ""),
                "evidence_summary": chunk.get("evidence_summary", ""),
            }
        )
    return summaries


def build_compact_match_context(match_result: dict) -> dict:
    """Trim verbose match evidence while preserving branch/follow-up decisions."""
    compact_matches = []
    for match in match_result.get("matches", []):
        evidence = match.get("evidence", "")
        if len(evidence) > 260:
            evidence = evidence[:260].rstrip("，。；;,. ") + "..."
        compact_matches.append(
            {
                "ksa_type": match.get("ksa_type", ""),
                "jd_requirement": match.get("jd_requirement", ""),
                "importance": match.get("importance", ""),
                "matched_experience_ids": match.get("matched_experience_ids", []),
                "matched_experience_names": match.get("matched_experience_names", []),
                "match_level": match.get("match_level", ""),
                "evidence_quality": match.get("evidence_quality", ""),
                "evidence": evidence,
                "gap": match.get("gap", ""),
            }
        )
    return {
        "matches": compact_matches,
        "overall_summary": match_result.get("overall_summary", ""),
    }


def build_resume_match_outline(match_result: dict) -> dict:
    """Final generation only needs steering signals, not verbose match evidence."""
    return {
        "matches": [
            {
                "jd_requirement": match.get("jd_requirement", ""),
                "importance": match.get("importance", ""),
                "matched_experience_names": match.get("matched_experience_names", []),
                "match_level": match.get("match_level", ""),
                "evidence_quality": match.get("evidence_quality", ""),
                "gap": match.get("gap", ""),
            }
            for match in match_result.get("matches", [])
        ],
        "overall_summary": match_result.get("overall_summary", ""),
    }


def build_reviewed_answers_for_resume_context(reviewed_answers: dict) -> dict:
    """Keep only usable follow-up facts for final generation."""
    usable_items = []
    for item in reviewed_answers.get("reviewed_answers", []):
        if item.get("status") != "answered":
            continue
        usable_items.append(
            {
                "belongs_to_experience_name": item.get(
                    "belongs_to_experience_name", ""
                ),
                "is_new_experience": item.get("is_new_experience", False),
                "current_run_only": item.get("current_run_only", True),
                "usable_information": item.get("usable_information", []),
            }
        )
    return {
        "usable_followup_information": usable_items,
        "stop_reason": reviewed_answers.get("stop_reason", ""),
        "estimated_readiness_score_after_followups": reviewed_answers.get(
            "estimated_readiness_score_after_followups", ""
        ),
    }


def build_scored_matches_for_verdict(readiness_score: dict) -> list[dict]:
    compact_items = []
    for item in readiness_score.get("scored_matches", []):
        compact_items.append(
            {
                "requirement_id": item.get("requirement_id", ""),
                "jd_requirement": item.get("jd_requirement", ""),
                "importance": item.get("importance", ""),
                "importance_label": item.get("importance_label", ""),
                "coverage_level": item.get("coverage_level", ""),
                "coverage_score": item.get("coverage_score", 0),
                "matched_experience_names": item.get("matched_experience_names", []),
                "gap": item.get("gap", ""),
                "earned_score": item.get("earned_score", 0),
                "possible_score": item.get("possible_score", 0),
                "match_strength": item.get("match_strength", 0),
                "gap_severity": item.get("gap_severity", 0),
            }
        )
    return compact_items


def build_compact_resume_context(state) -> dict:
    """Build the smallest practical Step 8 context while preserving evidence."""
    return {
        "jd": build_compact_jd_context(state.jd_analysis),
        "retrieval_summary": {
            "retrieval_mode": state.retrieval_result.get("retrieval_mode", ""),
            "section_quotas": state.retrieval_result.get("section_quotas", {}),
            "selected_chunk_count": len(
                state.retrieval_result.get("selected_chunks", [])
            ),
            "direct_context_sections": build_direct_context_sections_for_api(
                state.retrieval_result.get("direct_context_sections", [])
            ),
        },
        "selected_evidence_chunks": state.retrieved_context,
        "experience_atoms": build_atoms_for_resume_context(state.experience_atoms),
        "match_outline": build_resume_match_outline(state.match_result),
        "reviewed_followup_answers": build_reviewed_answers_for_resume_context(
            state.reviewed_answers
        ),
    }


def ask_ai_for_json_once(
    client: OpenAI, prompt: str, model: str, schema_name: str, call_name: str = ""
) -> dict:
    """Ask for JSON without inheriting previous response context.

    Use this for compact workflow slices where the prompt already contains all
    required state. This is the main API optimization path for web readiness.
    """
    start = time.perf_counter()
    response = create_response_with_retry(
        client,
        model=model,
        input=prompt,
        instructions=system_prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": SCHEMAS[schema_name],
                "strict": True,
            }
        },
    )
    elapsed_seconds = time.perf_counter() - start
    record_api_call(
        call_name=call_name or schema_name,
        model=model,
        prompt=prompt,
        response=response,
        response_type="json",
        schema_name=schema_name,
        elapsed_seconds=elapsed_seconds,
    )
    return (response, parse_json_response_or_raise(response, schema_name))


def ask_ai_for_text_once(
    client: OpenAI, prompt: str, model: str, call_name: str = ""
) -> str:
    """Ask for text without inheriting previous response context."""
    start = time.perf_counter()
    response = create_response_with_retry(
        client, model=model, input=prompt, instructions=system_prompt
    )
    elapsed_seconds = time.perf_counter() - start
    record_api_call(
        call_name=call_name or "text_generation",
        model=model,
        prompt=prompt,
        response=response,
        response_type="text",
        elapsed_seconds=elapsed_seconds,
    )
    return (response, response.output_text)


def review_user_answers(client: OpenAI, answers: list[dict]) -> dict:
    """Review follow-up answers as one compact independent call."""
    answer_review_prompt = f"\nBelow are the same user's natural language responses to this round of follow-up questions:\n\n{to_prompt_json(answers)}\n\n{load_prompt('task_s7_review_answers.txt')}\n"
    _, reviewed = ask_ai_for_json_once(
        client,
        answer_review_prompt,
        STEP_MODELS["s7"],
        "reviewed_answers",
        call_name="s7_review_single_followup_answer",
    )
    return reviewed


def deduplicate_items(items: list) -> list:
    """Deduplicate by content, while supporting both strings and structured objects like dictionaries."""
    unique_items = []
    seen_keys = set()
    for item in items:
        if isinstance(item, (dict, list)):
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        else:
            key = str(item)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_items.append(item)
    return unique_items


def calculate_star_completeness(atom: dict) -> float:
    """Calculate the completeness of a STAR for a single atomic experience."""
    star = atom.get("star", {})
    checks = [
        bool(star.get("situation")),
        bool(star.get("task")),
        bool(star.get("actions")),
        bool(star.get("results")),
    ]
    return sum(checks) / len(checks)


def has_professional_experience(atoms: list[dict]) -> bool:
    return any((atom.get("section_key") in PROFESSIONAL_SECTION_KEYS for atom in atoms))


def calculate_source_balance_multiplier(
    match: dict, matched_atoms: list[dict]
) -> float:
    """Make readiness more conservative when evidence only comes from projects.

    Projects can strongly prove technical skill, but for real recruiting scenarios
    work/internship evidence should carry independent weight. This multiplier avoids
    project-only matches inflating overall readiness too much.
    """
    if not matched_atoms:
        return 0.0
    if has_professional_experience(matched_atoms):
        return 1.0
    if match.get("ksa_type") == "ability":
        return 0.72
    if match.get("ksa_type") == "knowledge":
        return 0.82
    return 0.88


def importance_to_v02_weight(importance: str, ksa_type: str = "") -> tuple[str, float]:
    """Map existing high/medium/low importance into the v0.2 weight table.

    The current matcher does not yet emit the full v0.2 importance enum. This
    adapter lets us use the more stable weighted coverage formula without
    breaking the existing match_result schema.
    """
    if importance == "high":
        return ("must_have", 1.5)
    if importance == "medium":
        return ("soft_skill", 0.8) if ksa_type == "ability" else ("preferred", 1.0)
    return ("nice_to_have", 0.6)


def derive_coverage_level(match_level: str, evidence_quality: str) -> str:
    """Conservative rubric for coverage_level from existing matcher labels."""
    if match_level == "none" or evidence_quality == "none":
        return "none"
    if match_level == "high" and evidence_quality == "strong":
        return "strong"
    if match_level in {"high", "medium"} and evidence_quality in {"strong", "partial"}:
        return "medium"
    if match_level in {"high", "medium", "low"} and evidence_quality in {
        "strong",
        "partial",
        "weak",
    }:
        return "weak"
    return "none"


def coverage_level_to_score(level: str) -> float:
    return {"strong": 1.0, "medium": 0.65, "weak": 0.35, "none": 0.0}.get(level, 0.0)


def estimate_best_similarity(match: dict, coverage_level: str) -> float:
    """Stable proxy until requirement-level retrieval exposes similarity per evidence.

    This is not the final semantic similarity design. It gives deterministic
    ranking behavior while preserving the current pipeline shape.
    """
    quality_proxy = {"strong": 0.92, "medium": 0.78, "weak": 0.55, "none": 0.0}
    if isinstance(match.get("best_similarity"), (int, float)):
        return max(0.0, min(1.0, float(match["best_similarity"])))
    return quality_proxy.get(coverage_level, 0.0)


def calculate_readiness_score(match_result: dict, experience_atoms: dict) -> dict:
    """Calculate readiness as weighted evidence coverage.

    Scoring v0.2 keeps the existing LLM matching step for evidence
    classification, but the final score is deterministic:

    score = sum(requirement_weight * coverage_score) / sum(requirement_weight)
    """
    atoms_by_id = {
        atom["id"]: atom for atom in experience_atoms.get("experience_atoms", [])
    }
    scored_matches = []
    coverage_results = []
    total_possible = 0.0
    total_earned = 0.0
    for index, match in enumerate(match_result.get("matches", []), start=1):
        importance = match.get("importance", "medium")
        importance_label, requirement_weight = importance_to_v02_weight(
            importance, match.get("ksa_type", "")
        )
        coverage_level = derive_coverage_level(
            match.get("match_level", "none"), match.get("evidence_quality", "none")
        )
        coverage_score = coverage_level_to_score(coverage_level)
        best_similarity = estimate_best_similarity(match, coverage_level)
        matched_atoms = [
            atoms_by_id[atom_id]
            for atom_id in match.get("matched_experience_ids", [])
            if atom_id in atoms_by_id
        ]
        earned = requirement_weight * coverage_score
        possible = requirement_weight
        total_earned += earned
        total_possible += possible
        requirement_id = match.get("requirement_id") or f"R{index}"
        missing_info = []
        gap = match.get("gap", "")
        if gap:
            missing_info.append(gap)
        coverage_item = {
            "requirement_id": requirement_id,
            "requirement_text": match.get("jd_requirement", ""),
            "category": match.get("ksa_type", "other"),
            "importance": importance_label,
            "requirement_weight": requirement_weight,
            "coverage_level": coverage_level,
            "coverage_score": coverage_score,
            "evidence_ids": match.get("matched_experience_ids", []),
            "matched_experience_names": match.get("matched_experience_names", []),
            "best_similarity": round(best_similarity, 3),
            "missing_info": missing_info,
            "reason": match.get("evidence", ""),
        }
        coverage_results.append(coverage_item)
        scored_matches.append(
            {
                **match,
                "requirement_id": requirement_id,
                "importance_label": importance_label,
                "importance_weight": requirement_weight,
                "coverage_level": coverage_level,
                "coverage_score": coverage_score,
                "best_similarity": round(best_similarity, 3),
                "match_strength": round(
                    requirement_weight * coverage_score * best_similarity, 3
                ),
                "gap_severity": round(requirement_weight * (1 - coverage_score), 3),
                "has_professional_experience": has_professional_experience(
                    matched_atoms
                ),
                "earned_score": round(earned, 3),
                "possible_score": possible,
            }
        )
    overall = total_earned / total_possible if total_possible else 0.0
    return {
        "overall_readiness_score": round(overall, 3),
        "raw_readiness_score": round(overall, 3),
        "threshold": READINESS_THRESHOLD,
        "scoring_version": SCORING_VERSION,
        "rubric_version": COVERAGE_RUBRIC_VERSION,
        "coverage_results": coverage_results,
        "scored_matches": scored_matches,
    }


def calculate_fit_level(readiness_score: dict) -> dict:
    """Provide the job fit level based on quantitative results."""
    overall = readiness_score["overall_readiness_score"]
    if overall >= 0.85:
        fit_level = "high_fit"
        recommendation = "continue"
    elif overall >= 0.7:
        fit_level = "good_fit"
        recommendation = "continue"
    elif overall >= 0.55:
        fit_level = "partial_fit"
        recommendation = "continue_with_caution"
    elif overall >= 0.4:
        fit_level = "weak_fit"
        recommendation = "continue_with_caution"
    else:
        fit_level = "low_fit"
        recommendation = "reconsider"
    return {
        "fit_level": fit_level,
        "recommendation": recommendation,
        "overall_readiness_score": overall,
        "scoring_version": SCORING_VERSION,
    }


def summarize_scored_match(item: dict, *, gap_mode: bool = False) -> str:
    requirement = item.get("jd_requirement", "") or item.get("requirement_text", "")
    names = item.get("matched_experience_names", []) or []
    prefix = requirement.strip() or item.get("requirement_id", "Unnamed Requirement")
    if gap_mode:
        gap = (
            item.get("gap", "")
            or "Lacking more direct, quantifiable, or scenario-relevant evidence."
        )
        return f"{prefix}：{gap}"
    if names:
        return f"{prefix}: Evidence comes from {', '.join(names[:2])}"
    return f"{prefix}: Relevant evidence already covered"


def deterministic_top_matches(readiness_score: dict, limit: int = 3) -> list[str]:
    candidates = [
        item
        for item in readiness_score.get("scored_matches", [])
        if item.get("coverage_level") in {"strong", "medium"}
    ]
    candidates = sorted(
        candidates,
        key=lambda item: (
            item.get("match_strength", 0),
            item.get("importance_weight", 0),
            item.get("coverage_score", 0),
        ),
        reverse=True,
    )
    return [summarize_scored_match(item) for item in candidates[:limit]]


def deterministic_top_gaps(readiness_score: dict, limit: int = 3) -> list[str]:
    candidates = [
        item
        for item in readiness_score.get("scored_matches", [])
        if item.get("coverage_level") in {"weak", "none"}
    ]
    candidates = sorted(
        candidates,
        key=lambda item: (
            item.get("gap_severity", 0),
            item.get("importance_weight", 0),
        ),
        reverse=True,
    )
    return [summarize_scored_match(item, gap_mode=True) for item in candidates[:limit]]


def default_fit_summary(fit_metrics: dict) -> str:
    score = round(fit_metrics.get("overall_readiness_score", 0) * 100)
    labels = {
        "high_fit": "Strong evidence coverage; can directly organize resume content around the role.",
        "good_fit": "Most core requirements have evidence coverage but some gaps remain worth supplementing.",
        "partial_fit": "Transferable evidence exists but key requirements still need more direct materials.",
        "weak_fit": "Current experience database only offers limited evidence coverage; recommend cautious investment and prioritize adding materials.",
        "low_fit": "Current experience database insufficient to support core requirements of this JD.",
    }
    return (
        f"Readiness score {score}/100。{labels.get(fit_metrics.get('fit_level'), '')}"
    )


def stabilize_fit_verdict(
    fit_verdict: dict, fit_metrics: dict, readiness_score: dict
) -> dict:
    """Keep LLM wording, but make fit level and top lists deterministic."""
    stable = dict(fit_verdict or {})
    stable["fit_level"] = fit_metrics.get(
        "fit_level", stable.get("fit_level", "partial_fit")
    )
    stable["recommendation"] = fit_metrics.get(
        "recommendation", stable.get("recommendation", "continue_with_caution")
    )
    stable["fit_summary"] = stable.get("fit_summary") or default_fit_summary(
        fit_metrics
    )
    stable["major_matches"] = deterministic_top_matches(readiness_score)
    stable["major_gaps"] = deterministic_top_gaps(readiness_score)
    stable["user_message"] = stable.get("user_message") or stable["fit_summary"]
    return stable


def calculate_question_priority(question: dict, scored_matches: list[dict]) -> dict:
    """Calculate question priority based on coverage gaps and supplementability."""
    improvability_weights = {"high": 1.0, "medium": 0.7, "low": 0.4}
    related_requirement = question.get("target_requirement", "")
    matched_score = next(
        (
            item
            for item in scored_matches
            if item.get("jd_requirement") == related_requirement
        ),
        None,
    )
    if matched_score:
        possible = matched_score.get("possible_score", 0) or 1
        current_coverage = matched_score.get("earned_score", 0) / possible
        importance_weight = matched_score.get("importance_weight", 1)
    else:
        current_coverage = question.get("theoretical_improvement", {}).get(
            "coverage_before", 0
        )
        importance_weight = 1
    theoretical = question.get("theoretical_improvement", {})
    coverage_after = theoretical.get("coverage_after_if_answered", current_coverage)
    max_increment = max(0.0, coverage_after - current_coverage)
    improvability = improvability_weights.get(question.get("improvability", "low"), 0.4)
    question_priority_score = importance_weight * (1 - current_coverage) * improvability
    expected_gain = importance_weight * max_increment * improvability
    return {
        **question,
        "current_coverage": round(current_coverage, 3),
        "question_priority_score": round(question_priority_score, 3),
        "expected_gain": round(expected_gain, 3),
    }


def build_topic_pool(candidate_questions: list[dict]) -> list[dict]:
    """Group root questions by experience topic and attach shared budgets."""
    topics_by_id = {}
    for question in candidate_questions:
        topic_id = question.get("related_experience_id") or question["id"]
        topic = topics_by_id.setdefault(
            topic_id,
            {
                "topic_id": topic_id,
                "experience_id": question.get("related_experience_id", ""),
                "experience_name": question.get("related_experience_name", ""),
                "root_questions": [],
                "clarification_budget": TOPIC_CLARIFICATION_BUDGET,
                "followup_budget": MAX_TOPIC_FOLLOWUPS,
            },
        )
        topic["root_questions"].append(question)
    topics = []
    for topic in topics_by_id.values():
        topic["root_questions"] = sorted(
            topic["root_questions"],
            key=lambda item: item.get("question_priority_score", 0),
            reverse=True,
        )
        topic["topic_priority_score"] = topic["root_questions"][0].get(
            "question_priority_score", 0
        )
        topics.append(topic)
    return sorted(
        topics, key=lambda item: item.get("topic_priority_score", 0), reverse=True
    )


def build_topic_followup_prompt(
    topic: dict,
    last_question: dict,
    last_review: dict,
    estimated_readiness_score: float,
) -> str:
    """Provide the model with enough context to decide the next in-topic follow-up."""
    return f"\nCurrent topic:\n{to_prompt_json({'topic_id': topic['topic_id'], 'experience_id': topic.get('experience_id', ''), 'experience_name': topic.get('experience_name', ''), 'clarification_budget_left': topic.get('clarification_budget', 0), 'followup_budget_left': topic.get('followup_budget', 0)})}\n\nLast asked question:\n{to_prompt_json(last_question)}\n\nLatest reviewed answer:\n{to_prompt_json(last_review)}\n\nCurrent estimated readiness score:\n{estimated_readiness_score}\n"


def generate_topic_followup_question(
    client: OpenAI,
    topic: dict,
    last_question: dict,
    last_review: dict,
    scored_matches: list[dict],
    estimated_readiness_score: float,
) -> dict | None:
    """Generate one immediate same-topic follow-up question when deeper digging is worthwhile."""
    topic_context_prompt = build_topic_followup_prompt(
        topic, last_question, last_review, estimated_readiness_score
    )
    prompt = f"\n{topic_context_prompt}\n\n{load_prompt('task_s6b_generate_topic_followup.txt')}\n"
    _, next_question = ask_ai_for_json_once(
        client,
        prompt,
        STEP_MODELS["s6"],
        "topic_followup",
        call_name="s6b_generate_topic_followup",
    )
    if not next_question.get("should_follow_up"):
        return None
    followup_question = {
        **next_question,
        "id": f"{topic['topic_id']}_followup_{MAX_TOPIC_FOLLOWUPS - topic.get('followup_budget', 0) + 1}",
        "related_experience_id": topic.get("experience_id", ""),
        "related_experience_name": topic.get("experience_name", ""),
    }
    return calculate_question_priority(followup_question, scored_matches)


def build_gap_followup_plan(match_result: dict) -> dict:
    """Build stable follow-up questions directly from matching gaps."""
    questions = []
    high_priority_gaps = []
    fallback_gaps = []
    for index, match in enumerate(match_result.get("matches", []), start=1):
        if (
            match.get("match_level") == "high"
            and match.get("evidence_quality") == "strong"
        ):
            continue
        gap_item = (index, match)
        if match.get("importance") == "high":
            high_priority_gaps.append(gap_item)
        elif match.get("match_level") in {"low", "none"} or match.get(
            "evidence_quality"
        ) in {"weak", "none"}:
            fallback_gaps.append(gap_item)
    selected_gaps = high_priority_gaps or fallback_gaps
    for index, match in selected_gaps:
        if len(questions) >= MAX_QUESTIONS:
            break
        requirement = match.get("jd_requirement", "This job requirement")
        experience_names = match.get("matched_experience_names") or []
        experience_ids = match.get("matched_experience_ids") or []
        related_name = experience_names[0] if experience_names else ""
        related_id = experience_ids[0] if experience_ids else ""
        gap = match.get("gap", "")
        if related_name:
            question = f'For "{related_name}", can you share a concrete example demonstrating "{requirement}"? Focus on what you did and the outcome.'
        else:
            question = f'Is there a real experience demonstrating "{requirement}"? Briefly describe the context, your actions, and the outcome.'
        questions.append(
            {
                "id": f"fallback_q{index}",
                "question_type": "ksa_gap",
                "gap_priority": match.get("importance", "medium"),
                "target_requirement": requirement,
                "target_ksa_type": match.get("ksa_type", "none"),
                "target_star_field": "none",
                "related_experience_id": related_id,
                "related_experience_name": related_name,
                "question": question,
                "why_ask": gap
                or "This evidence is still insufficient in the current retrieval results.",
                "improvability": "medium",
                "theoretical_improvement": {
                    "coverage_before": 0.0,
                    "coverage_after_if_answered": 0.35,
                },
                "priority_reason": "Generated from the matching gap by the Follow-up Agent.",
            }
        )
    return {
        "candidate_questions": questions,
        "planning_summary": "Follow-up questions were generated from matching gaps.",
    }


def has_unasked_high_priority_questions(
    questions: list[dict], asked_question_ids: set[str]
) -> bool:
    """Determine whether there are still any high-priority questions that have not been asked."""
    return any(
        (
            question.get("gap_priority") == "high"
            and question.get("id") not in asked_question_ids
            for question in questions
        )
    )


@dataclass
class WorkflowState:
    """Single-run workflow state.

    This object is the bridge between the CLI version and a future web backend.
    Raw evidence and user answers remain the fact source; model outputs are
    structured annotations used by later workflow steps.
    """

    experience_text: str = ""
    jd_text: str = ""
    jd_analysis: dict = field(default_factory=dict)
    experience_sections: dict = field(default_factory=dict)
    retrieval_result: dict = field(default_factory=dict)
    retrieved_context: str = ""
    experience_atoms: dict = field(default_factory=dict)
    input_quality_audit: dict = field(default_factory=dict)
    match_result: dict = field(default_factory=dict)
    readiness_score: dict = field(default_factory=dict)
    fit_metrics: dict = field(default_factory=dict)
    fit_verdict: dict = field(default_factory=dict)
    followup_plan: dict = field(default_factory=dict)
    reviewed_answers: dict = field(default_factory=dict)
    interaction_log: list = field(default_factory=list)
    resume_markdown: str = ""
    improvement_suggestions_markdown: str = ""
    branch_decisions: list = field(default_factory=list)
    memory_layers: dict = field(default_factory=dict)
    api_payload_manifest: dict = field(default_factory=dict)

    def record_branch(self, name: str, decision: str, reason: str = "") -> None:
        self.branch_decisions.append(
            {"branch": name, "decision": decision, "reason": reason}
        )

    def remember_api_payload(self, step_name: str, payload, note: str = "") -> None:
        """Track what each step sends to the model without storing raw prompts."""
        if isinstance(payload, dict):
            fields = list(payload.keys())
        else:
            fields = []
        self.api_payload_manifest[step_name] = {
            "payload_chars": json_char_len(payload),
            "top_level_fields": fields,
            "note": note,
        }

    def refresh_memory_layers(self) -> None:
        """Experimental layered memory for API context slicing.

        Full artifacts remain available locally, while API calls should consume
        compact views built from the appropriate layer.
        """
        self.memory_layers = {
            "raw_source_memory": {
                "experience_text_chars": len(self.experience_text),
                "jd_text_chars": len(self.jd_text),
            },
            "retrieval_memory": {
                "selected_chunk_count": len(
                    self.retrieval_result.get("selected_chunks", []) or []
                ),
                "selected_chunks_context_chars": len(self.retrieved_context),
                "section_quotas": self.retrieval_result.get("section_quotas", {}),
            },
            "annotation_memory": {
                "atom_count": len(
                    self.experience_atoms.get("experience_atoms", []) or []
                ),
                "match_count": len(self.match_result.get("matches", []) or []),
            },
            "decision_memory": {
                "readiness_score": self.readiness_score.get(
                    "overall_readiness_score", ""
                ),
                "fit_level": self.fit_verdict.get("fit_level", ""),
                "recommendation": self.fit_verdict.get("recommendation", ""),
                "followup_question_count": len(
                    self.followup_plan.get("candidate_questions", []) or []
                ),
            },
            "presentation_memory": {"resume_chars": len(self.resume_markdown)},
            "api_context_memory": self.api_payload_manifest,
            "api_call_trace": API_CALL_TRACE,
        }


def create_client_from_env() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not found, please configure it in environment variables first."
        )
    return OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)


def initialize_workflow_runtime() -> OpenAI:
    """Initialize shared runtime used by CLI and future web API handlers."""
    global system_prompt
    system_prompt = load_prompt("system_cariagent.txt")
    API_CALL_TRACE.clear()
    return create_client_from_env()


def load_cli_inputs() -> WorkflowState:
    experience_text = read_text_file(EXPERIENCE_FILE)
    jd_text = read_text_file(JD_FILE)
    return create_workflow_state(experience_text, jd_text)


def create_workflow_state(experience_text: str, jd_text: str) -> WorkflowState:
    """Create a workflow state from UI/API/CLI inputs."""
    if not experience_text:
        raise ValueError("exp_bank.txt is still empty.")
    if not jd_text:
        raise ValueError("sample_jd.txt is still empty.")
    return WorkflowState(experience_text=experience_text, jd_text=jd_text)


def save_workflow_trace(state: WorkflowState) -> None:
    """Save a compact trace for debugging and portfolio explanation."""
    state.refresh_memory_layers()
    lines = ["# CariAgent Workflow Trace", ""]
    lines.append(
        f"- JD task count: {len(state.jd_analysis.get('core_responsibilities', []) or [])}"
    )
    lines.append(
        f"- Parsed sections: {len(state.experience_sections.get('experience_sections', []) or [])}"
    )
    lines.append(
        f"- Selected chunks: {len(state.retrieval_result.get('selected_chunks', []) or [])}"
    )
    lines.append(
        f"- Experience atoms: {len(state.experience_atoms.get('experience_atoms', []) or [])}"
    )
    lines.append(f"- Match items: {len(state.match_result.get('matches', []) or [])}")
    if state.readiness_score:
        lines.append(
            f"- Readiness score: {state.readiness_score.get('overall_readiness_score', '')}"
        )
    if state.fit_verdict:
        lines.append(
            f"- Fit verdict: {state.fit_verdict.get('fit_level', '')} / {state.fit_verdict.get('recommendation', '')}"
        )
    lines.append(
        f"- Follow-up questions: {len(state.followup_plan.get('candidate_questions', []) or [])}"
    )
    if state.reviewed_answers:
        lines.append(
            f"- Follow-up stop reason: {state.reviewed_answers.get('stop_reason', '')}"
        )
    lines.append("")
    lines.append("## Branch decisions")
    for item in state.branch_decisions:
        lines.append(
            f"- {item.get('branch')}: {item.get('decision')}"
            + (f" - {item.get('reason')}" if item.get("reason") else "")
        )
    lines.append("")
    lines.append("## Memory layers")
    lines.append("```json")
    lines.append(json.dumps(state.memory_layers, ensure_ascii=False, indent=2))
    lines.append("```")
    save_json("00_memory_layers.json", state.memory_layers)
    save_json("00_api_payload_manifest.json", state.api_payload_manifest)
    save_markdown("workflow_trace.md", "\n".join(lines).strip() + "\n")


def emit_progress(
    progress_callback: Callable[[str], None] | None, message: str
) -> None:
    """Emit progress for CLI now and web UI later."""
    if progress_callback:
        progress_callback(message)


def run_jd_analysis_workflow(client: OpenAI, state: WorkflowState) -> WorkflowState:
    """Step 3: parse JD into structured requirements with one compact call."""
    task_prompt = load_prompt("task_s3_parse_jd.txt")
    state.remember_api_payload(
        "s3_parse_jd",
        {"jd_text_chars": len(state.jd_text), "task_prompt": "task_s3_parse_jd.txt"},
        "This step must read the target JD once.",
    )
    prompt = f"\nYou are executing CariAgent Step 3: Decompose the target JD.\nPlease complete structured analysis based only on the JD text and task instructions below; do not add requirements not appearing in the JD.\n\nTarget JD:\n{state.jd_text}\n\nTask Instructions:\n{task_prompt}\n"
    _, state.jd_analysis = ask_ai_for_json_once(
        client, prompt, STEP_MODELS["s3"], "jd_analysis", call_name="s3_parse_jd"
    )
    save_json("01_jd_analysis.json", state.jd_analysis)
    state.refresh_memory_layers()
    return state


def run_retrieval_workflow(
    client: OpenAI,
    state: WorkflowState,
    progress_callback: Callable[[str], None] | None = None,
) -> WorkflowState:
    """Step 3A + 3B: section parsing and section-aware RAG retrieval."""
    if state.experience_sections:
        emit_progress(
            progress_callback,
            "Step 3A skipped: Reusing already parsed experience database sections",
        )
    else:
        emit_progress(
            progress_callback,
            "Step 3A start: Identifying experience database sections...",
        )
        section_task_prompt = load_prompt("task_s2_parse_experience_sections.txt")
        state.remember_api_payload(
            "s3a_parse_experience_sections",
            {
                "experience_text_chars": len(state.experience_text),
                "task_prompt": "task_s2_parse_experience_sections.txt",
            },
            "This step must read the raw experience bank once to create local sections.",
        )
        section_prompt = f"\nYou are executing CariAgent Step 3A: parsing the user’s full experience database into resume sections.\nPlease retain original facts and source boundaries as much as possible; do not rewrite into final resume bullet points.\n\nUser’s full experience database:\n{state.experience_text}\n\nTask instructions:\n{section_task_prompt}\n"
        _, state.experience_sections = ask_ai_for_json_once(
            client,
            section_prompt,
            STEP_MODELS["section_parser"],
            "experience_sections",
            call_name="s3a_parse_experience_sections",
        )
        save_json("01a_experience_sections.json", state.experience_sections)
        emit_progress(
            progress_callback,
            "Step 3A complete: AI divided experience database into resume sections",
        )
    emit_progress(
        progress_callback, "Step 3B start: Executing section-aware RAG retrieval..."
    )
    state.retrieval_result = retrieve_sectioned_task_unit_evidence(
        client,
        state.experience_sections,
        state.jd_analysis,
        section_quotas=SECTION_RETRIEVAL_QUOTAS,
    )
    save_json("01b_retrieval_result.json", state.retrieval_result)
    state.retrieved_context = build_selected_chunks_context(state.retrieval_result)
    if (
        MAX_RETRIEVAL_CONTEXT_CHARS > 0
        and len(state.retrieved_context) > MAX_RETRIEVAL_CONTEXT_CHARS
    ):
        state.retrieved_context = (
            state.retrieved_context[:MAX_RETRIEVAL_CONTEXT_CHARS]
            + "\n\n[Selected evidence context was truncated by MAX_RETRIEVAL_CONTEXT_CHARS. Full local retrieval details are saved in outputs/01b_retrieval_result.json.]"
        )
    state.remember_api_payload(
        "retrieval_memory_selected_evidence",
        {
            "selected_evidence_context_chars": len(state.retrieved_context),
            "selected_chunk_count": len(
                state.retrieval_result.get("selected_chunks", []) or []
            ),
            "direct_context_section_count": len(
                state.retrieval_result.get("direct_context_sections", []) or []
            ),
        },
        "Local full retrieval result is saved; downstream API calls use selected evidence only.",
    )
    state.refresh_memory_layers()
    emit_progress(
        progress_callback,
        "Step 3B complete: Retrieved the most relevant experience fragments by section for the current JD",
    )
    return state


def run_matching_workflow(
    client: OpenAI,
    state: WorkflowState,
    progress_callback: Callable[[str], None] | None = None,
) -> WorkflowState:
    """Step 4 + 4B + 5 + 5B: structure evidence, match, score, explain fit."""
    emit_progress(
        progress_callback,
        "Step 4 start: Organizing retrieved evidence into experience atoms...",
    )
    jd_context = build_compact_jd_context(state.jd_analysis)
    direct_context_sections = build_direct_context_sections_for_api(
        state.retrieval_result.get("direct_context_sections", [])
    )
    atomize_payload = {
        "jd": jd_context,
        "direct_context_sections": direct_context_sections,
        "selected_evidence_context_chars": len(state.retrieved_context),
    }
    state.remember_api_payload(
        "s4_atomize_selected_evidence",
        atomize_payload,
        "Step 4 receives only retrieved evidence chunks, not the full experience bank.",
    )
    atomize_prompt = f"\nYou are continuing the same CariAgent workflow for the same user.\nUse only the compact source evidence below. Do not assume access to the full experience bank.\n\nJD compact context:\n{to_prompt_json(jd_context)}\n\nDirect context sections such as education / skills:\n{to_prompt_json(direct_context_sections)}\n\nSelected retrieved evidence chunks:\n{state.retrieved_context}\n\nTask instructions:\n{load_prompt('task_s4_atomize_experience.txt')}\n"
    _, state.experience_atoms = ask_ai_for_json_once(
        client,
        atomize_prompt,
        STEP_MODELS["s4"],
        "experience_atoms",
        call_name="s4_atomize_selected_evidence",
    )
    save_json("02_experience_atoms.json", state.experience_atoms)
    emit_progress(
        progress_callback, "Step 4 complete: AI decomposed personal experience"
    )
    emit_progress(
        progress_callback,
        "Step 4B start: Checking candidate experience material quality...",
    )
    quality_payload = {
        "jd": jd_context,
        "selected_evidence_summary": build_selected_evidence_summary(
            state.retrieval_result
        ),
        "experience_atoms": build_atoms_for_matching_context(state.experience_atoms),
    }
    state.remember_api_payload(
        "s4b_quality_audit",
        quality_payload,
        "Quality audit uses evidence summaries and atoms, not full evidence text.",
    )
    quality_prompt = f"\nYou are checking the input quality of retrieved evidence and experience atoms under the current JD.\nPlease conservatively judge based on the provided compact context; do not fabricate missing information as facts.\n\nJD compact context:\n{to_prompt_json(jd_context)}\n\nSelected retrieved evidence summary:\n{to_prompt_json(quality_payload['selected_evidence_summary'])}\n\nExperience atoms:\n{to_prompt_json(quality_payload['experience_atoms'])}\n\nTask instructions:\n{load_prompt('task_s4c_input_quality_audit.txt')}\n"
    _, state.input_quality_audit = ask_ai_for_json_once(
        client,
        quality_prompt,
        STEP_MODELS["input_quality"],
        "input_quality",
        call_name="s4b_quality_audit",
    )
    save_json("02b_input_quality_audit.json", state.input_quality_audit)
    emit_progress(
        progress_callback,
        "Step 4B complete: AI finished experience database quality check",
    )
    emit_progress(
        progress_callback, "Step 5 start: Matching JD with experience atoms..."
    )
    matching_payload = {
        "jd": jd_context,
        "experience_atoms": build_atoms_for_matching_context(state.experience_atoms),
    }
    state.remember_api_payload(
        "s5_match_jd_to_atoms",
        matching_payload,
        "Step 5 matches JD against atoms; raw chunks stay local unless needed for audit.",
    )
    match_prompt = f"\nYou are executing CariAgent Step 5: Matching JD with experience atoms.\nPlease only use facts and provenance in atoms; do not borrow evidence across experiences.\n\nJD compact context:\n{to_prompt_json(jd_context)}\n\nExperience atoms:\n{to_prompt_json(matching_payload['experience_atoms'])}\n\nTask instructions:\n{load_prompt('task_s5_match_experience.txt')}\n"
    _, state.match_result = ask_ai_for_json_once(
        client,
        match_prompt,
        STEP_MODELS["s5"],
        "match_result",
        call_name="s5_match_jd_to_atoms",
    )
    save_json("03_match_result.json", state.match_result)
    emit_progress(progress_callback, "Step 5 complete: AI finished matching")
    emit_progress(
        progress_callback,
        "Step 5B start: Calculating readiness and generating match judgement...",
    )
    state.readiness_score = calculate_readiness_score(
        state.match_result, state.experience_atoms
    )
    save_json("03_readiness_score.json", state.readiness_score)
    state.fit_metrics = calculate_fit_level(state.readiness_score)
    save_json("03b_fit_metrics.json", state.fit_metrics)
    fit_payload = {
        "fit_metrics": state.fit_metrics,
        "scored_matches": build_scored_matches_for_verdict(state.readiness_score),
    }
    state.remember_api_payload(
        "s5b_explain_fit_verdict",
        fit_payload,
        "Fit verdict explains the calculated readiness result; it does not recalculate score.",
    )
    fit_verdict_prompt = f"\nPlease explain the job fit based on the system-calculated fit metrics.\nDo not recalculate scores or extend judgments beyond quantitative results.\n\n{to_prompt_json(state.fit_metrics)}\n\nSystem-computed scored matches:\n\n{to_prompt_json(fit_payload['scored_matches'])}\n\n{load_prompt('task_s5b_explain_fit_verdict.txt')}\n"
    _, state.fit_verdict = ask_ai_for_json_once(
        client,
        fit_verdict_prompt,
        STEP_MODELS["fit_verdict"],
        "fit_verdict",
        call_name="s5b_explain_fit_verdict",
    )
    state.fit_verdict = stabilize_fit_verdict(
        state.fit_verdict, state.fit_metrics, state.readiness_score
    )
    save_json("03c_fit_verdict.json", state.fit_verdict)
    emit_progress(
        progress_callback,
        "Step 5B complete: Generated match judgement and continuation/caution suggestions",
    )
    state.refresh_memory_layers()
    return state


def run_followup_planning_workflow(state: WorkflowState) -> WorkflowState:
    """Step 6: build follow-up plan from matching gaps."""
    state.followup_plan = build_gap_followup_plan(state.match_result)
    save_json("04_followup_plan.json", state.followup_plan)
    return state


def normalize_user_control_text(text: str) -> str:
    return text.strip().lower()


def build_pass_review_item(question: dict, reason: str) -> dict:
    return {
        "question_id": question["id"],
        "status": "pass",
        "answered_ksa_type": "none",
        "answered_star_field": "none",
        "usable_information": [],
        "reason": reason,
        "clarification_prompt": "",
        "belongs_to_experience_id": question.get("related_experience_id", ""),
        "belongs_to_experience_name": question.get("related_experience_name", ""),
        "is_new_experience": False,
        "current_run_only": True,
    }


def has_high_value_followup_question(candidate_questions: list[dict]) -> bool:
    """Keep one useful human check even when the score is already high."""
    return any(
        (
            question.get("gap_priority") == "high"
            or question.get("expected_gain", 0) >= MIN_EXPECTED_GAIN
            for question in candidate_questions
        )
    )


def should_skip_followup_by_readiness(
    state: WorkflowState, candidate_questions: list[dict] | None = None
) -> bool:
    if state.readiness_score.get("overall_readiness_score", 0) < READINESS_THRESHOLD:
        return False
    if candidate_questions and has_high_value_followup_question(candidate_questions):
        return False
    return True


def run_followup_interaction_workflow(
    client: OpenAI,
    state: WorkflowState,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> WorkflowState:
    """Step 7: CLI-compatible follow-up interaction.

    Future web UI can replace input_fn/output_fn or implement one-question-at-a-time
    endpoints using the same candidate question structure.
    """
    candidate_questions = [
        calculate_question_priority(question, state.readiness_score["scored_matches"])
        for question in state.followup_plan.get("candidate_questions", [])
    ]
    candidate_questions = sorted(
        candidate_questions,
        key=lambda item: item.get("question_priority_score", 0),
        reverse=True,
    )
    reviewed_items = []
    updated_notes = []
    interaction_log = []
    stop_reason = "question_plan_exhausted"
    estimated_readiness_score = state.readiness_score.get("overall_readiness_score", 0)
    asked_question_ids = set()
    topic_pool = build_topic_pool(candidate_questions)
    total_questions_asked = 0
    if not candidate_questions:
        stop_reason = "no_candidate_questions"
        state.record_branch("followup", "skip", "No candidate follow-up questions.")
        state.reviewed_answers = {
            "reviewed_answers": [],
            "updated_experience_notes": [],
            "stop_reason": stop_reason,
            "estimated_readiness_score_after_followups": round(
                estimated_readiness_score, 3
            ),
        }
        save_json("05_reviewed_answers.json", state.reviewed_answers)
        save_json("05_interaction_log.json", interaction_log)
        return state
    if should_skip_followup_by_readiness(state, candidate_questions):
        stop_reason = "readiness_threshold_reached"
        state.record_branch(
            "followup",
            "skip",
            f"Readiness score {estimated_readiness_score:.3f} >= {READINESS_THRESHOLD}.",
        )
        output_fn(
            f"\nCurrent readiness is high (readiness score: {estimated_readiness_score:.3f}), no further follow-up this round, generating resume draft directly."
        )
        state.reviewed_answers = {
            "reviewed_answers": [],
            "updated_experience_notes": [],
            "stop_reason": stop_reason,
            "estimated_readiness_score_after_followups": round(
                estimated_readiness_score, 3
            ),
        }
        save_json("05_reviewed_answers.json", state.reviewed_answers)
        save_json("05_interaction_log.json", interaction_log)
        return state
    if estimated_readiness_score >= READINESS_THRESHOLD:
        state.record_branch(
            "followup",
            "ask",
            f"Readiness score {estimated_readiness_score:.3f} >= {READINESS_THRESHOLD}, but at least one high-value follow-up question remains.",
        )
    else:
        state.record_branch(
            "followup",
            "ask",
            f"Readiness score {estimated_readiness_score:.3f} < {READINESS_THRESHOLD}.",
        )
    output_fn("\nNow entering user supplementation phase.")
    output_fn(
        "Answer naturally here; say pass if you don’t know; input done / end / generate first to finish."
    )

    def ask_topic_question(question: dict, topic: dict) -> tuple[dict | None, str]:
        nonlocal stop_reason
        nonlocal estimated_readiness_score
        nonlocal total_questions_asked
        if total_questions_asked >= MAX_QUESTIONS:
            stop_reason = "max_questions_reached"
            return (None, "stop")
        output_fn("\n" + question["question"])
        answer_text = input_fn("Your answer:").strip()
        normalized_answer = normalize_user_control_text(answer_text)
        if normalized_answer in EXIT_WORDS:
            stop_reason = "stopped_by_user"
            return (None, "stop")
        if normalized_answer in SKIP_WORDS:
            asked_question_ids.add(question["id"])
            total_questions_asked += 1
            reviewed_item = build_pass_review_item(
                question,
                "User skipped this question with a natural-language skip expression.",
            )
            reviewed_items.append(reviewed_item)
            interaction_log.append(
                {
                    "topic_id": topic["topic_id"],
                    "experience_name": topic["experience_name"],
                    "question": question,
                    "review": reviewed_item,
                    "estimated_readiness_score_after_question": round(
                        estimated_readiness_score, 3
                    ),
                    "clarification_budget_left": topic["clarification_budget"],
                    "followup_budget_left": topic["followup_budget"],
                }
            )
            return (reviewed_item, "ok")
        answer = {
            "question_id": question["id"],
            "related_experience_id": question["related_experience_id"],
            "related_experience_name": question["related_experience_name"],
            "question": question["question"],
            "answer": answer_text,
        }
        asked_question_ids.add(question["id"])
        total_questions_asked += 1
        first_review = review_user_answers(client, [answer])
        reviewed_item = first_review["reviewed_answers"][0]
        updated_notes.extend(first_review.get("updated_experience_notes", []))
        if (
            reviewed_item.get("status") == "off_topic"
            and topic["clarification_budget"] > 0
        ):
            topic["clarification_budget"] -= 1
            output_fn("\n" + reviewed_item["clarification_prompt"])
            second_answer_text = input_fn("Please supplement once more:").strip()
            normalized_second_answer = normalize_user_control_text(second_answer_text)
            if normalized_second_answer in EXIT_WORDS:
                stop_reason = "stopped_by_user"
                return (None, "stop")
            if normalized_second_answer in SKIP_WORDS:
                reviewed_item = build_pass_review_item(
                    question, "User skipped the clarification question."
                )
                reviewed_items.append(reviewed_item)
                interaction_log.append(
                    {
                        "topic_id": topic["topic_id"],
                        "experience_name": topic["experience_name"],
                        "question": question,
                        "review": reviewed_item,
                        "estimated_readiness_score_after_question": round(
                            estimated_readiness_score, 3
                        ),
                        "clarification_budget_left": topic["clarification_budget"],
                        "followup_budget_left": topic["followup_budget"],
                    }
                )
                return (reviewed_item, "ok")
            clarified_answer = {
                **answer,
                "first_answer": answer_text,
                "answer": second_answer_text,
                "clarification_round": 1,
            }
            second_review = review_user_answers(client, [clarified_answer])
            reviewed_item = second_review["reviewed_answers"][0]
            updated_notes.extend(second_review.get("updated_experience_notes", []))
            if reviewed_item.get("status") == "off_topic":
                reviewed_item = {
                    "question_id": question["id"],
                    "status": "pass",
                    "answered_ksa_type": "none",
                    "answered_star_field": "none",
                    "usable_information": [],
                    "reason": "Clarification was used for this topic, but the answer still did not address the question.",
                    "clarification_prompt": reviewed_item.get(
                        "clarification_prompt", ""
                    ),
                    "belongs_to_experience_id": question.get(
                        "related_experience_id", ""
                    ),
                    "belongs_to_experience_name": question.get(
                        "related_experience_name", ""
                    ),
                    "is_new_experience": False,
                    "current_run_only": True,
                }
        reviewed_items.append(reviewed_item)
        if reviewed_item.get("status") == "answered":
            estimated_readiness_score = min(
                1.0, estimated_readiness_score + question.get("expected_gain", 0)
            )
        interaction_log.append(
            {
                "topic_id": topic["topic_id"],
                "experience_name": topic["experience_name"],
                "question": question,
                "review": reviewed_item,
                "estimated_readiness_score_after_question": round(
                    estimated_readiness_score, 3
                ),
                "clarification_budget_left": topic["clarification_budget"],
                "followup_budget_left": topic["followup_budget"],
            }
        )
        return (reviewed_item, "ok")

    for topic in topic_pool:
        if total_questions_asked >= MAX_QUESTIONS:
            stop_reason = "max_questions_reached"
            break
        root_question = next(
            (
                question
                for question in topic["root_questions"]
                if question.get("id") not in asked_question_ids
            ),
            None,
        )
        if root_question is None:
            continue
        if (
            root_question.get("expected_gain", 0) < MIN_EXPECTED_GAIN
            and root_question.get("gap_priority") != "high"
        ):
            continue
        reviewed_item, status = ask_topic_question(root_question, topic)
        if status == "stop":
            break
        if reviewed_item is None or reviewed_item.get("status") != "answered":
            continue
        last_question = root_question
        last_review = reviewed_item
        while topic["followup_budget"] > 0 and total_questions_asked < MAX_QUESTIONS:
            try:
                followup_question = generate_topic_followup_question(
                    client,
                    topic,
                    last_question,
                    last_review,
                    state.readiness_score["scored_matches"],
                    estimated_readiness_score,
                )
            except Exception as error:
                interaction_log.append(
                    {
                        "topic_id": topic["topic_id"],
                        "experience_name": topic["experience_name"],
                        "followup_generation_error": {
                            "error_type": type(error).__name__,
                            "error_message": str(error),
                        },
                    }
                )
                break
            if followup_question is None:
                break
            if (
                followup_question.get("expected_gain", 0) < MIN_EXPECTED_GAIN
                and followup_question.get("gap_priority") != "high"
            ):
                break
            topic["followup_budget"] -= 1
            reviewed_item, status = ask_topic_question(followup_question, topic)
            if status == "stop":
                break
            if reviewed_item is None or reviewed_item.get("status") != "answered":
                break
            last_question = followup_question
            last_review = reviewed_item
        if stop_reason == "stopped_by_user":
            break
    state.reviewed_answers = {
        "reviewed_answers": reviewed_items,
        "updated_experience_notes": deduplicate_items(updated_notes),
        "stop_reason": stop_reason,
        "estimated_readiness_score_after_followups": round(
            estimated_readiness_score, 3
        ),
    }
    state.interaction_log = interaction_log
    save_json("05_reviewed_answers.json", state.reviewed_answers)
    save_json("05_interaction_log.json", state.interaction_log)
    save_experience_updates(state.reviewed_answers["updated_experience_notes"])
    return state


def run_resume_generation_workflow(
    client: OpenAI, state: WorkflowState
) -> WorkflowState:
    """Step 8: generate final markdown resume draft."""
    resume_context = build_compact_resume_context(state)
    state.remember_api_payload(
        "s8_generate_resume",
        resume_context,
        "Final generation uses fact evidence, resume-ready atoms, match outline, and usable follow-up facts.",
    )
    resume_prompt = f"\nYou are continuing the same CariAgent workflow for the same user.\nReturn a structured object with separate resume_markdown and improvement_suggestions_markdown fields.\nThe resume_markdown field must contain only the resume, without advice, analysis, or improvement notes.\nSelected evidence chunks and reviewed user answers are the source of truth.\nAtoms and match result are annotations.\nDo not borrow evidence across source experiences.\n\nCompact final generation context:\n{to_prompt_json(resume_context)}\n\nTask instructions:\n{load_prompt('task_s8_generate_resume.txt')}\n"
    _, output = ask_ai_for_json_once(
        client,
        resume_prompt,
        STEP_MODELS["s8"],
        "resume_output",
        call_name="s8_generate_resume",
    )
    state.resume_markdown = output["resume_markdown"]
    state.improvement_suggestions_markdown = output["improvement_suggestions_markdown"]
    save_markdown("result.md", state.resume_markdown)
    save_markdown("improvement_suggestions.md", state.improvement_suggestions_markdown)
    state.refresh_memory_layers()
    return state


def run_analysis_until_fit(client: OpenAI, state: WorkflowState) -> WorkflowState:
    """Run non-interactive analysis up to fit verdict.

    This is the natural first backend endpoint for a future web UI.
    """
    state = run_jd_analysis_workflow(client, state)
    state = run_retrieval_workflow(client, state)
    state = run_matching_workflow(client, state)
    state = run_followup_planning_workflow(state)
    return state


def run_full_cli_workflow() -> WorkflowState:
    """Current CLI entrypoint, built from reusable workflow steps."""
    client = initialize_workflow_runtime()
    state = load_cli_inputs()

    def cli_progress(message: str) -> None:
        print(message, flush=True)

    print("Step 1 complete: Personal experience database read")
    print("Step 2 complete: Target JD read")
    state = run_jd_analysis_workflow(client, state)
    print("Step 3 complete: AI decomposed JD")
    state = run_retrieval_workflow(client, state, progress_callback=cli_progress)
    state = run_matching_workflow(client, state, progress_callback=cli_progress)
    if state.fit_verdict.get("recommendation") == "reconsider":
        state.record_branch(
            "fit_verdict", "ask_continue", state.fit_verdict.get("user_message", "")
        )
        print("\n" + state.fit_verdict.get("user_message", ""))
        continue_choice = (
            input("Continue? Input y to continue, any other input to end:")
            .strip()
            .lower()
        )
        if continue_choice != "y":
            state.record_branch("fit_verdict", "stop", "User chose not to continue.")
            save_workflow_trace(state)
            raise SystemExit("This session ended per user choice.")
    else:
        state.record_branch(
            "fit_verdict", "continue", state.fit_verdict.get("recommendation", "")
        )
    print("Step 6 start: Generating follow-up plan based on match gaps...", flush=True)
    state = run_followup_planning_workflow(state)
    print("Step 6 complete: Follow-up plan generated")
    state = run_followup_interaction_workflow(client, state)
    followup_stop_reason = state.reviewed_answers.get("stop_reason", "")
    if followup_stop_reason in {
        "readiness_threshold_reached",
        "no_candidate_questions",
    }:
        print("Step 7 skipped: No user supplementation Q&A this round")
    else:
        print("Step 7 complete: AI understood your supplementary answers")
    state = run_resume_generation_workflow(client, state)
    print("Step 8 complete: Final resume content generated")
    print(f"Result saved to: {OUTPUT_DIR / 'result.md'}")
    print(
        f"Improvement suggestions saved separately to: {OUTPUT_DIR / 'improvement_suggestions.md'}"
    )
    save_workflow_trace(state)
    return state


if __name__ == "__main__":
    run_full_cli_workflow()
