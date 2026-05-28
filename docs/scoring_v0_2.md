# CariAgent Scoring v0.2

## Objective

CariAgent readiness score is an evidence coverage score.

It measures how well the user's current experience bank can support the requirements of a target JD. It does not measure final hiring probability, interview success probability, general candidate quality, or resume writing quality.

## Current Integration Scope

Scoring v0.2 is introduced as a compatibility layer over the existing workflow:

1. The existing JD analysis, RAG retrieval, and LLM match result steps remain in place.
2. The final readiness score is calculated deterministically from coverage levels.
3. Fit level and top matches/gaps are determined by program rules.
4. The LLM remains responsible for explanation text and follow-up wording.

This avoids a full rewrite while reducing score drift.

## Coverage Rubric

| Coverage level | Score | Meaning |
| --- | ---: | --- |
| strong | 1.00 | Direct evidence. The experience clearly supports the JD requirement and can be used directly in resume/interview. |
| medium | 0.65 | Relevant evidence. The experience is related but needs reframing because context, method, or result is not fully aligned. |
| weak | 0.35 | Transferable evidence only. The experience shows some related ability but is not strong enough to directly support the requirement. |
| none | 0.00 | No meaningful evidence found. The system should not infer or invent experience. |

## Weight Mapping

The future target schema uses `hard_constraint`, `must_have`, `preferred`, `soft_skill`, and `nice_to_have`.

The current matcher only emits `high`, `medium`, and `low`, so v0.2 uses this adapter:

| Existing importance | v0.2 label | Weight |
| --- | --- | ---: |
| high | must_have | 1.5 |
| medium | preferred | 1.0 |
| medium + ability | soft_skill | 0.8 |
| low | nice_to_have | 0.6 |

## Formula

For each requirement:

```text
w_i = requirement weight
c_i = coverage score
```

```text
Readiness Score = 100 * sum(w_i * c_i) / sum(w_i)
```

In code, `overall_readiness_score` is stored as `0.0-1.0`; the UI displays it as `0-100`.

## Fit Level Mapping

| Score range | Fit level |
| --- | --- |
| 85-100 | high_fit |
| 70-84 | good_fit |
| 55-69 | partial_fit |
| 40-54 | weak_fit |
| 0-39 | low_fit |

Fit level is determined by code, not by the LLM.

## Top Matches And Gaps

Top matches are selected deterministically:

```text
match_strength = requirement_weight * coverage_score * best_similarity
```

Only `strong` and `medium` coverage items are eligible.

Top gaps are also selected deterministically:

```text
gap_severity = requirement_weight * (1 - coverage_score)
```

Only `weak` and `none` coverage items are eligible.

## Stability Target

For the same JD and same experience bank, run the pipeline 3 times:

| Metric | Target |
| --- | --- |
| readiness score max-min | <= 5 |
| fit_level | should not cross more than one adjacent level |
| top matches overlap | >= 60% |
| top gaps overlap | >= 60% |

## Current Limitation

This is not the final architecture. The current v0.2 implementation still depends on the LLM-generated `match_level` and `evidence_quality`, then converts them into coverage levels conservatively.

The next improvement should make coverage grading more deterministic by using requirement-level retrieval, evidence IDs, semantic similarity, keyword/tool overlap, and STAR completeness.
