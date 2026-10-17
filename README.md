# CariAgent — Evidence-Based Resume Tailoring

CariAgent helps job seekers turn a broad experience bank into a resume tailored to a specific job description. It retrieves relevant source evidence, identifies gaps, asks optional follow-up questions, and generates a resume without inventing facts or mixing achievements across experiences.

This branch is the **English edition**, intended for international users and recruiters. Application text, prompts, guides, product documentation, diagrams, and exported PRD files are in English. The Chinese edition is maintained separately on `main`.

## Product documentation

- **[Product Requirements Document](docs/prd/CariAgent_PRD_en_v0.4.md)** — product goals, user and system flows, functional requirements, AI behavior rules, development history, technical decisions, and validation evidence.
- [PDF](docs/prd/exports/CariAgent_PRD_en_v0.4.pdf) · [Editable Word document](docs/prd/exports/CariAgent_PRD_en_v0.4.docx) · [Standalone HTML](docs/prd/exports/CariAgent_PRD_en_v0.4.html).
- [Evidence coverage scoring](docs/scoring_v0_2.md).
- [Experience bank guide](guides/guide_s1_input_experience.txt) · [Job description guide](guides/guide_s2_input_jd.txt).

## How it works

1. Enter or upload an experience bank and a target job description.
2. Parse the role requirements and organize experience into sections and records.
3. Retrieve source chunks using section-aware semantic and keyword search.
4. Structure evidence into STAR/KSA annotations, identify gaps, and calculate evidence coverage.
5. Review the match summary and optionally answer or skip follow-up questions.
6. Generate a resume and separate improvement suggestions. Markdown and Word downloads contain only the resume.

Source text and user answers are facts; model annotations and scores are interpretations. Evidence coverage is **not a hiring probability**. The interface uses synthetic demonstration inputs; they are not claims about the project author's employment history.

## Run locally

Python 3.12 was used for the current validation.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run ui/app_en.py
```

Configure `OPENAI_API_KEY` securely as an environment variable or in the ignored `.streamlit/secrets.toml` file:

```toml
OPENAI_API_KEY = "YOUR_API_KEY"
```

Do not commit credentials. The default generation model is `gpt-4.1-mini`; retrieval uses `text-embedding-3-small`. Generation models can be overridden through `OPENAI_MODEL` or step-specific variables such as `OPENAI_MODEL_S3`, `OPENAI_MODEL_S4`, and `OPENAI_MODEL_S8`.

## Deploy on Streamlit Community Cloud

Create an app using repository `yunlinlian-Eliot/CariAgent`, branch `english-app`, and entry point `ui/app_en.py`. Configure the API key in the deployed app's **Settings → Secrets**. The deployed app has its own secrets; credentials from a development environment are not automatically transferred.

Both `ui/app.py` and `ui/app_en.py` run English on this branch. Keep any existing Chinese deployment connected to `main`. The existing Dev Container configuration is preserved.

## Validate

Offline tests:

```bash
python -m unittest discover -s tests -v
```

Opt-in real API smoke test, using synthetic demo inputs and a simulated follow-up answer:

```bash
python scripts/smoke_english.py --output-dir /tmp/cariagent-english-test
```

The live test incurs API usage costs. It exercises JD analysis, real embeddings and retrieval, matching, answer review, and separate resume/advice generation. It does not replace human usability testing. The repository also checks English-only text and document exports.

## Project structure

```text
core/                 Workflow state, model calls, retrieval, and scoring
ui/                   Streamlit application and deployment entry point
prompts/              English system and step prompts
guides/               English input guidance
docs/prd/             English PRD, diagrams, and PDF/Word/HTML exports
docs/scoring_v0_2.md   Evidence coverage scoring specification
scripts/              Opt-in live API validation
tests/                Offline regression and English-only checks
```

## Scope and limitations

This is a working AI product MVP with a function-based workflow, not a completed multi-agent framework migration. It has no account system, persistent vector database, cross-session recovery, or guaranteed production SLA. TXT, Markdown, DOCX, and text-based PDF inputs are supported; image understanding/OCR is not implemented. Web outputs are not written to disk by default (`CARIAGENT_SAVE_OUTPUTS=0`), but session state and caches may retain runtime data. User inputs are sent to the configured model and embedding services.

The CLI remains available through `python core/simple_mvp.py`, requiring user-provided `data/exp_bank.txt` and `data/sample_jd.txt`. Its advanced follow-up controls differ from the web experience; see the PRD for the distinction.
