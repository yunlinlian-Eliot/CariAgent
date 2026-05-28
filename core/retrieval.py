from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from openai import OpenAI


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass
class Chunk:
    id: str
    text: str
    start_char: int
    end_char: int
    experience_title: str = ""
    company_or_project: str = ""
    section_type: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "experience_title": self.experience_title,
            "company_or_project": self.company_or_project,
            "section_type": self.section_type,
        }


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


EXPERIENCE_PATTERNS = [
    {
        "keywords": ["北京艺恩", "艺恩", "Endata", "竞品周报", "品牌露出"],
        "experience_title": "北京艺恩世纪数据分析实习：竞品周报制作",
        "company_or_project": "北京艺恩世纪数据",
        "section_type": "internship_experience",
    },
    {
        "keywords": ["好未来", "TAL", "教研", "产品研发", "技术团队", "用户反馈"],
        "experience_title": "好未来教育产品研发实习：用户反馈与产品迭代支持",
        "company_or_project": "好未来",
        "section_type": "internship_experience",
    },
    {
        "keywords": ["CariAgent", "自研AI Agent", "自研 AI Agent", "简历生成", "经历库", "作品集"],
        "experience_title": "自研 AI Agent 项目：CariAgent",
        "company_or_project": "CariAgent",
        "section_type": "project_experience",
    },
    {
        "keywords": ["外卖平台", "Postgre", "PostgreSQL", "SQL", "KPI", "window function"],
        "experience_title": "外卖平台经营与用户指标 SQL 分析项目",
        "company_or_project": "SQL 数据分析项目",
        "section_type": "project_experience",
    },
    {
        "keywords": ["电商", "广告投放", "GA4", "BigQuery", "渠道分析", "漏斗"],
        "experience_title": "电商广告投放效果漏斗及渠道分析项目",
        "company_or_project": "电商数据分析项目",
        "section_type": "project_experience",
    },
    {
        "keywords": ["RFM", "客户分群", "运营策略"],
        "experience_title": "RFM 客户分群与运营策略分析项目",
        "company_or_project": "客户运营分析项目",
        "section_type": "project_experience",
    },
    {
        "keywords": ["创新创业联盟", "北京工业大学创新创业联盟"],
        "experience_title": "北京工业大学创新创业联盟经历",
        "company_or_project": "北京工业大学创新创业联盟",
        "section_type": "campus_experience",
    },
    {
        "keywords": ["心理协会", "心理健康协会"],
        "experience_title": "心理协会校园经历",
        "company_or_project": "心理协会",
        "section_type": "campus_experience",
    },
]


def infer_experience_metadata(cleaned_text: str, start: int, end: int) -> dict:
    """Infer coarse source metadata from nearby text.

    This is intentionally simple and portable: it does not mutate the source bank,
    but gives each chunk a stable provenance label so downstream prompts do not
    borrow evidence across experiences.
    """
    window_start = max(0, start - 1600)
    window_end = min(len(cleaned_text), end + 120)
    context = cleaned_text[window_start:window_end]

    best = None
    best_score = 0
    for candidate in EXPERIENCE_PATTERNS:
        score = sum(1 for keyword in candidate["keywords"] if keyword.lower() in context.lower())
        if score > best_score:
            best = candidate
            best_score = score

    if best:
        return {
            "experience_title": best["experience_title"],
            "company_or_project": best["company_or_project"],
            "section_type": best["section_type"],
        }

    return {
        "experience_title": "未识别来源经历",
        "company_or_project": "",
        "section_type": "unknown",
    }


def chunk_text(text: str, chunk_size: int = 620, overlap: int = 100) -> list[Chunk]:
    """Split long source text into overlapping evidence chunks with provenance metadata."""
    cleaned = normalize_text(text)
    if not cleaned:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 1
    while start < len(cleaned):
        hard_end = min(start + chunk_size, len(cleaned))
        end = hard_end
        if hard_end < len(cleaned):
            window = cleaned[start:hard_end]
            boundary = max(
                window.rfind("。"),
                window.rfind("；"),
                window.rfind(";"),
                window.rfind("！"),
                window.rfind("？"),
                window.rfind("\n"),
            )
            if boundary >= chunk_size // 2:
                end = start + boundary + 1

        chunk = cleaned[start:end].strip()
        if chunk:
            metadata = infer_experience_metadata(cleaned, start, end)
            chunks.append(
                Chunk(
                    id=f"chunk_{index:03d}",
                    text=chunk,
                    start_char=start,
                    end_char=end,
                    **metadata,
                )
            )
            index += 1

        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)

    return chunks


def chunk_section_text(
    text: str,
    section_key: str,
    section_name: str,
    *,
    chunk_size: int = 620,
    overlap: int = 100,
    id_prefix: str | None = None,
    experience_title: str | None = None,
    company_or_project: str | None = None,
) -> list[Chunk]:
    """Split one parsed resume section into chunks.

    Section-aware RAG should not let project chunks compete directly with work /
    internship chunks. This function keeps section provenance on every chunk.
    """
    cleaned = normalize_text(text)
    if not cleaned:
        return []

    prefix = id_prefix or section_key or "section"
    chunks: list[Chunk] = []
    start = 0
    index = 1
    while start < len(cleaned):
        hard_end = min(start + chunk_size, len(cleaned))
        end = hard_end
        if hard_end < len(cleaned):
            window = cleaned[start:hard_end]
            boundary = max(
                window.rfind("。"),
                window.rfind("；"),
                window.rfind(";"),
                window.rfind("!"),
                window.rfind("?"),
                window.rfind("\n"),
            )
            if boundary >= chunk_size // 2:
                end = start + boundary + 1

        chunk = cleaned[start:end].strip()
        if chunk:
            inferred = infer_experience_metadata(cleaned, start, end)
            chunk_experience_title = (
                experience_title
                or inferred.get("experience_title")
                if inferred.get("section_type") != "unknown"
                else section_name
            )
            if experience_title:
                chunk_experience_title = experience_title
            chunk_company_or_project = (
                company_or_project
                or inferred.get("company_or_project")
                or section_name
            )
            chunks.append(
                Chunk(
                    id=f"{prefix}_{index:03d}",
                    text=chunk,
                    start_char=start,
                    end_char=end,
                    experience_title=chunk_experience_title,
                    company_or_project=chunk_company_or_project,
                    section_type=section_key,
                )
            )
            index += 1

        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)

    return chunks


def build_jd_task_units(jd_analysis: dict, max_units: int = 7) -> list[dict]:
    """Build medium-grained JD retrieval queries.

    We prefer original responsibility/task sentences over tiny KSA fragments.
    KSA items are used only as supporting keywords, not as independent retrieval units.
    """
    raw_units: list[str] = []
    raw_units.extend(jd_analysis.get("core_responsibilities", []) or [])
    if jd_analysis.get("job_goal"):
        raw_units.insert(0, jd_analysis["job_goal"])
    # Basic requirements such as education or major are handled later as
    # resume filters/background, not as RAG queries against experience chunks.

    keywords = jd_analysis.get("keywords_to_mirror", []) or []
    ksa_keywords: list[str] = []
    for group in ("knowledge", "skills", "abilities"):
        for item in jd_analysis.get("ksa_requirements", {}).get(group, []):
            text = normalize_text(item.get("item", ""))
            if text:
                ksa_keywords.append(text)

    units: list[dict] = []
    seen = set()
    for unit in raw_units:
        task = normalize_text(unit)
        if not task or task in seen:
            continue
        supporting_terms = keywords[:8] + ksa_keywords[:8]
        query = normalize_text(" ".join([task, *supporting_terms]))
        units.append(
            {
                "task_unit_id": f"task_{len(units) + 1:03d}",
                "task_unit": task,
                "query": query,
            }
        )
        seen.add(task)
        if len(units) >= max_units:
            break

    if not units:
        fallback = normalize_text(" ".join(keywords + ksa_keywords))
        if fallback:
            units.append(
                {
                    "task_unit_id": "task_001",
                    "task_unit": fallback,
                    "query": fallback,
                }
            )

    return units


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def tokenize_for_keyword_search(text: str) -> list[str]:
    lowered = text.lower()
    latin_tokens = re.findall(r"[a-z0-9+#.]+", lowered)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    cjk_bigrams: list[str] = []
    for run in cjk_runs:
        cjk_bigrams.extend(run[i : i + 2] for i in range(len(run) - 1))
    return latin_tokens + cjk_bigrams


def keyword_overlap_score(query: str, chunk: str) -> float:
    query_tokens = Counter(tokenize_for_keyword_search(query))
    chunk_tokens = Counter(tokenize_for_keyword_search(chunk))
    if not query_tokens:
        return 0.0
    overlap = sum(min(count, chunk_tokens[token]) for token, count in query_tokens.items())
    return overlap / sum(query_tokens.values())


def embed_texts(client: OpenAI, texts: list[str], model: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def summarize_chunk_for_user(text: str, max_chars: int = 58) -> str:
    cleaned = normalize_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip("，。；;,. ") + "..."


def retrieve_task_unit_evidence(
    client: OpenAI,
    chunks: list[Chunk],
    jd_analysis: dict,
    *,
    chunks_per_task_unit: int = 3,
    max_total_chunks: int = 18,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    semantic_weight: float = 0.72,
    keyword_weight: float = 0.28,
    min_combined_score: float = 0.30,
) -> dict:
    task_units = build_jd_task_units(jd_analysis)
    if not chunks or not task_units:
        return {
            "task_units": task_units,
            "evidence_map": [],
            "selected_chunk_ids": [],
            "selected_chunks": [],
        }

    chunk_texts = [
        normalize_text(
            " ".join(
                part
                for part in [
                    chunk.experience_title,
                    chunk.company_or_project,
                    chunk.section_type,
                    chunk.text,
                ]
                if part
            )
        )
        for chunk in chunks
    ]
    chunk_embeddings = embed_texts(client, chunk_texts, embedding_model)
    query_embeddings = embed_texts(client, [unit["query"] for unit in task_units], embedding_model)

    evidence_map = []
    all_candidates = []
    selected_ids: set[str] = set()
    selected_chunks: list[dict] = []

    for unit, query_embedding in zip(task_units, query_embeddings):
        scored = []
        for chunk, chunk_embedding, searchable_text in zip(chunks, chunk_embeddings, chunk_texts):
            semantic_score = cosine_similarity(chunk_embedding, query_embedding)
            keyword_score = keyword_overlap_score(unit["query"], searchable_text)
            combined_score = semantic_weight * semantic_score + keyword_weight * keyword_score
            item = {
                **chunk.to_dict(),
                "task_unit_id": unit["task_unit_id"],
                "task_unit": unit["task_unit"],
                "semantic_score": round(semantic_score, 4),
                "keyword_score": round(keyword_score, 4),
                "combined_score": round(combined_score, 4),
                "evidence_summary": summarize_chunk_for_user(chunk.text),
            }
            scored.append(item)
            all_candidates.append(item)

        scored.sort(key=lambda item: item["combined_score"], reverse=True)
        scored = [item for item in scored if item["combined_score"] >= min_combined_score]

        task_selected = []
        used_sources_for_task: set[str] = set()
        for item in scored:
            if len(task_selected) >= chunks_per_task_unit:
                break
            source = item.get("experience_title", "")
            # Avoid filling one JD task with several overlapping chunks from the same source
            # unless there is not enough cross-source evidence.
            if source in used_sources_for_task and len(scored) > chunks_per_task_unit:
                continue
            task_selected.append(item)
            used_sources_for_task.add(source)

        for item in task_selected:
            if item["id"] not in selected_ids and len(selected_chunks) < max_total_chunks:
                selected_ids.add(item["id"])
                selected_chunks.append(item)

        evidence_map.append(
            {
                **unit,
                "evidence_chunks": task_selected,
            }
        )

    # If the per-task selection underfilled the global evidence budget, add best remaining chunks.
    if len(selected_chunks) < min(max_total_chunks, 12):
        all_candidates.sort(key=lambda item: item["combined_score"], reverse=True)
        for item in all_candidates:
            if item["combined_score"] < min_combined_score:
                continue
            if item["id"] in selected_ids:
                continue
            selected_ids.add(item["id"])
            selected_chunks.append(item)
            if len(selected_chunks) >= max_total_chunks:
                break

    selected_chunk_ids = [item["id"] for item in selected_chunks]
    for entry in evidence_map:
        entry["evidence_chunks"] = [
            item
            for item in entry["evidence_chunks"]
            if item["id"] in selected_ids
        ]

    return {
        "task_units": task_units,
        "evidence_map": evidence_map,
        "selected_chunk_ids": selected_chunk_ids,
        "selected_chunks": selected_chunks,
    }


def retrieve_sectioned_task_unit_evidence(
    client: OpenAI,
    experience_sections: dict,
    jd_analysis: dict,
    *,
    section_quotas: dict[str, int] | None = None,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> dict:
    """Run hybrid retrieval independently inside each resume section group."""
    section_quotas = section_quotas or {
        "professional_experience": 12,
        "project_experience": 6,
        "campus_other_experience": 3,
    }
    section_groups = {
        "professional_experience": {"work_experience", "internship_experience"},
        "project_experience": {"project_experience"},
        "campus_other_experience": {
            "campus_experience",
            "club_experience",
            "volunteer_experience",
            "other",
        },
    }
    non_retrieval_sections = {
        "education",
        "basic_information",
        "profile",
        "skills",
        "certifications",
        "awards",
        "hobbies",
    }

    sections = experience_sections.get("experience_sections", [])
    task_units = build_jd_task_units(jd_analysis)
    section_results = []
    selected_chunks = []
    selected_chunk_ids = []
    flattened_evidence_map = []
    direct_context_sections = []

    for section in sections:
        if section.get("section_key") in non_retrieval_sections:
            direct_context_sections.append(section)

    for section_group, section_keys in section_groups.items():
        group_sections = [
            section
            for section in sections
            if section.get("section_key") in section_keys
            and (
                normalize_text(section.get("content", ""))
                or section.get("experience_records")
            )
        ]
        group_chunks = []
        for section_index, section in enumerate(group_sections, start=1):
            records = section.get("experience_records") or []
            if records:
                for record_index, record in enumerate(records, start=1):
                    record_text = record.get("content", "")
                    if not normalize_text(record_text):
                        continue
                    record_title = (
                        record.get("record_title")
                        or record.get("organization")
                        or section.get("section_name", section_group)
                    )
                    organization = record.get("organization") or record_title
                    group_chunks.extend(
                        chunk_section_text(
                            record_text,
                            section.get("section_key", section_group),
                            section.get("section_name", section_group),
                            id_prefix=f"{section_group}_{section_index}_{record_index}",
                            experience_title=record_title,
                            company_or_project=organization,
                        )
                    )
            else:
                group_chunks.extend(
                    chunk_section_text(
                        section.get("content", ""),
                        section.get("section_key", section_group),
                        section.get("section_name", section_group),
                        id_prefix=f"{section_group}_{section_index}",
                    )
                )

        quota = section_quotas.get(section_group, 0)
        if not group_chunks or quota <= 0:
            section_results.append(
                {
                    "section_group": section_group,
                    "section_keys": sorted(section_keys),
                    "quota": quota,
                    "task_units": task_units,
                    "evidence_map": [],
                    "selected_chunk_ids": [],
                    "selected_chunks": [],
                }
            )
            continue

        group_result = retrieve_task_unit_evidence(
            client,
            group_chunks,
            jd_analysis,
            chunks_per_task_unit=3 if section_group == "professional_experience" else 2,
            max_total_chunks=quota,
            embedding_model=embedding_model,
            min_combined_score=0.0,
        )
        for entry in group_result.get("evidence_map", []):
            flattened_evidence_map.append(
                {
                    **entry,
                    "section_group": section_group,
                    "section_quota": quota,
                }
            )
        for chunk in group_result.get("selected_chunks", []):
            selected_chunks.append({**chunk, "section_group": section_group})
        selected_chunk_ids.extend(group_result.get("selected_chunk_ids", []))

        section_results.append(
            {
                "section_group": section_group,
                "section_keys": sorted(section_keys),
                "quota": quota,
                **group_result,
            }
        )

    return {
        "retrieval_mode": "section_aware_hybrid_retrieval",
        "task_units": task_units,
        "section_quotas": section_quotas,
        "direct_context_sections": direct_context_sections,
        "section_results": section_results,
        "evidence_map": flattened_evidence_map,
        "selected_chunk_ids": selected_chunk_ids,
        "selected_chunks": selected_chunks,
    }


def retrieve_requirement_evidence(
    client: OpenAI,
    chunks: list[Chunk],
    jd_analysis: dict,
    *,
    chunks_per_requirement: int = 3,
    max_total_chunks: int = 18,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    semantic_weight: float = 0.72,
    keyword_weight: float = 0.28,
    min_combined_score: float = 0.30,
) -> dict:
    """Backward-compatible wrapper; internally uses JD task-unit retrieval."""
    return retrieve_task_unit_evidence(
        client,
        chunks,
        jd_analysis,
        chunks_per_task_unit=chunks_per_requirement,
        max_total_chunks=max_total_chunks,
        embedding_model=embedding_model,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
        min_combined_score=min_combined_score,
    )


def retrieve_relevant_chunks(
    client: OpenAI,
    chunks: list[Chunk],
    queries: list[str],
    *,
    top_k: int = 8,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    semantic_weight: float = 0.75,
    keyword_weight: float = 0.25,
) -> dict:
    fake_jd = {
        "job_goal": "",
        "basic_requirements": [],
        "core_responsibilities": queries,
        "ksa_requirements": {"knowledge": [], "skills": [], "abilities": []},
        "keywords_to_mirror": [],
    }
    return retrieve_task_unit_evidence(
        client,
        chunks,
        fake_jd,
        chunks_per_task_unit=1,
        max_total_chunks=top_k,
        embedding_model=embedding_model,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
        min_combined_score=0.0,
    )


def render_evidence_map_context(evidence_map: list[dict]) -> str:
    """Render retrieved evidence for LLM context without exposing internal chunk IDs."""
    blocks: list[str] = []
    evidence_index = 1
    for entry in evidence_map:
        chunks = entry.get("evidence_chunks", [])
        if not chunks:
            continue
        section_line = (
            f"Section group: {entry.get('section_group')}\n"
            if entry.get("section_group")
            else ""
        )
        blocks.append(f"{section_line}JD task unit: {entry['task_unit']}")
        for chunk in chunks:
            blocks.append(
                f"Evidence {evidence_index} source: {chunk.get('experience_title', '未识别来源经历')}\n"
                f"Company/project: {chunk.get('company_or_project', '')}\n"
                f"Section type: {chunk.get('section_type', '')}\n"
                f"Evidence summary: {chunk['evidence_summary']}\n"
                f"Evidence text:\n{chunk['text']}"
            )
            evidence_index += 1
    return "\n\n".join(blocks)


def render_selected_chunks(selected_chunks: list[dict]) -> str:
    return "\n\n".join(
        f"Evidence {index} source: {chunk.get('experience_title', '未识别来源经历')}\n{chunk['text']}"
        for index, chunk in enumerate(selected_chunks, start=1)
    )
