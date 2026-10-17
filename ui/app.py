from __future__ import annotations
import html
import hashlib
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = PROJECT_ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
os.environ.setdefault("CARIAGENT_SAVE_OUTPUTS", "0")
from localization import is_english, localized
import simple_mvp

if not os.getenv("OPENAI_API_KEY"):
    try:
        secret_api_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        secret_api_key = ""
    if secret_api_key:
        os.environ["OPENAI_API_KEY"] = secret_api_key
st.set_page_config(
    page_title="CariAgent",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    '\n    <style>\n    :root {\n        --ca-bg: #f7f9fc;\n        --ca-surface: #ffffff;\n        --ca-surface-soft: #f1f6fa;\n        --ca-line: #d9e3ea;\n        --ca-line-strong: #c5d3dc;\n        --ca-text: #101828;\n        --ca-muted: #667785;\n        --ca-blue: #0e7890;\n        --ca-blue-dark: #0b6379;\n        --ca-blue-soft: #e8f5f8;\n        --ca-progress-bg: #d5e2ea;\n        --ca-green: #12805c;\n        --ca-amber: #a96800;\n    }\n    header[data-testid="stHeader"] {\n        display: block !important;\n        visibility: visible !important;\n        background: rgba(247, 249, 252, .96);\n        height: 2.75rem !important;\n    }\n    .stApp {\n        background: var(--ca-bg);\n    }\n    .block-container {\n        max-width: 1180px;\n        padding-top: 1.25rem;\n        padding-bottom: 3rem;\n    }\n    h1, h2, h3, p {\n        letter-spacing: 0;\n    }\n    div[data-testid="stMarkdown"] h1 {\n        font-size: 2rem;\n        line-height: 1.22;\n        margin: .25rem 0 1.1rem;\n    }\n    div[data-testid="stMarkdown"] h2 {\n        font-size: 1.45rem;\n        line-height: 1.3;\n        margin: 1.45rem 0 .7rem;\n    }\n    div[data-testid="stMarkdown"] h3 {\n        font-size: 1.16rem;\n        line-height: 1.35;\n        margin: 1rem 0 .5rem;\n    }\n    div[data-testid="stSidebar"] {\n        background: #eef3f7;\n        border-right: 1px solid var(--ca-line);\n        width: min(13vw, 180px) !important;\n        min-width: 150px !important;\n    }\n    div[data-testid="stSidebar"] > div:first-child {\n        width: min(13vw, 180px) !important;\n        min-width: 150px !important;\n        padding-left: .65rem;\n        padding-right: .65rem;\n    }\n    .ca-topbar {\n        display: grid;\n        grid-template-columns: 1fr auto 1fr;\n        align-items: center;\n        gap: 1rem;\n        padding: .85rem 0 1.05rem 0;\n        border-bottom: 1px solid var(--ca-line);\n        margin-bottom: .75rem;\n        min-height: 72px;\n        overflow: visible;\n    }\n    .ca-brand {\n        display: flex;\n        align-items: center;\n        gap: .8rem;\n        font-weight: 760;\n        color: var(--ca-text);\n        font-size: 1.08rem;\n    }\n    .ca-logo {\n        width: 38px;\n        height: 38px;\n        border-radius: 12px;\n        background: linear-gradient(135deg, #0d7891, #0a6780);\n        color: white;\n        display: inline-flex;\n        align-items: center;\n        justify-content: center;\n        font-weight: 780;\n        box-shadow: 0 8px 18px rgba(14, 120, 144, .18);\n    }\n    .ca-top-title {\n        color: var(--ca-muted);\n        font-size: 1.03rem;\n        font-weight: 650;\n    }\n    .ca-status {\n        justify-self: end;\n        color: var(--ca-blue-dark);\n        font-weight: 700;\n        font-size: .9rem;\n    }\n    .ca-status-dot {\n        display: inline-block;\n        width: .52rem;\n        height: .52rem;\n        border-radius: 999px;\n        background: var(--ca-blue);\n        margin-right: .45rem;\n    }\n    .ca-page {\n        margin-top: 2.6rem;\n    }\n    .ca-page-title {\n        color: var(--ca-text);\n        font-size: 1.8rem;\n        font-weight: 780;\n        margin-bottom: .35rem;\n    }\n    .ca-page-subtitle {\n        color: var(--ca-muted);\n        font-size: 1.02rem;\n        line-height: 1.55;\n        margin-bottom: 1.6rem;\n    }\n    .ca-card {\n        background: var(--ca-surface);\n        border: 1px solid var(--ca-line);\n        border-radius: 14px;\n        padding: 1.35rem 1.45rem;\n        box-shadow: 0 10px 24px rgba(20, 40, 60, .05);\n    }\n    .ca-soft-card {\n        background: var(--ca-surface-soft);\n        border: 1px solid var(--ca-line);\n        border-radius: 14px;\n        padding: 1.15rem 1.3rem;\n    }\n    .ca-card-title {\n        color: var(--ca-text);\n        font-weight: 760;\n        font-size: .96rem;\n        margin-bottom: .35rem;\n    }\n    .ca-label {\n        color: var(--ca-muted);\n        font-size: .78rem;\n        font-weight: 730;\n        letter-spacing: .06em;\n        text-transform: uppercase;\n        margin-bottom: .55rem;\n    }\n    .ca-pill {\n        display: inline-flex;\n        align-items: center;\n        border: 1px solid #b9dce5;\n        background: #edf8fb;\n        color: var(--ca-blue-dark);\n        border-radius: 999px;\n        padding: .28rem .68rem;\n        margin: .18rem .22rem .18rem 0;\n        font-size: .86rem;\n        font-weight: 620;\n    }\n    .ca-muted {\n        color: var(--ca-muted);\n    }\n    .ca-success {\n        color: var(--ca-green);\n        font-weight: 720;\n    }\n    .ca-warning {\n        color: var(--ca-amber);\n        font-weight: 720;\n    }\n    .ca-big-score {\n        font-size: 3rem;\n        line-height: 1;\n        color: var(--ca-text);\n        font-weight: 800;\n    }\n    .ca-score-denom {\n        color: var(--ca-muted);\n        font-size: 1.4rem;\n        font-weight: 650;\n    }\n    .ca-two-grid {\n        display: grid;\n        grid-template-columns: 1fr 1fr;\n        gap: 1rem;\n    }\n    .ca-list-item {\n        border-bottom: 1px solid var(--ca-line);\n        padding: .55rem 0;\n        line-height: 1.45;\n    }\n    .ca-list-item:last-child {\n        border-bottom: 0;\n    }\n    .ca-summary-grid {\n        display: grid;\n        grid-template-columns: 1fr 1fr;\n        gap: 1rem;\n        margin-top: 1rem;\n    }\n    .ca-summary-card {\n        background: var(--ca-surface);\n        border: 1px solid var(--ca-line);\n        border-radius: 14px;\n        padding: 1.05rem 1.2rem;\n        box-shadow: 0 8px 18px rgba(20, 40, 60, .04);\n    }\n    .ca-summary-item {\n        padding: .72rem 0;\n        line-height: 1.58;\n        border-bottom: 1px solid var(--ca-line);\n    }\n    .ca-summary-item:last-child {\n        border-bottom: 0;\n    }\n    .ca-summary-item-text {\n        line-height: 1.58;\n    }\n    .ca-score-bar {\n        width: 100%;\n        height: .7rem;\n        border-radius: 999px;\n        background: var(--ca-progress-bg);\n        overflow: hidden;\n        margin-top: .9rem;\n    }\n    .ca-score-fill {\n        height: 100%;\n        border-radius: 999px;\n        background: var(--ca-blue);\n    }\n    .ca-question-text {\n        font-size: 1.28rem;\n        line-height: 1.42;\n        font-weight: 760;\n        color: var(--ca-text);\n        margin-top: .75rem;\n    }\n    .ca-footnote {\n        color: var(--ca-muted);\n        font-size: .84rem;\n        margin: -.8rem 0 1.15rem;\n    }\n    .ca-followup-actions-spacer {\n        height: 1.25rem;\n    }\n    .ca-check {\n        color: var(--ca-green);\n        font-weight: 800;\n        margin-right: .35rem;\n    }\n    .ca-warn {\n        color: var(--ca-amber);\n        font-weight: 800;\n        margin-right: .35rem;\n    }\n    div[data-testid="stMetric"] {\n        background: var(--ca-surface);\n        border: 1px solid var(--ca-line);\n        border-radius: 12px;\n        padding: .9rem 1rem;\n        box-shadow: 0 8px 18px rgba(20, 40, 60, .04);\n    }\n    div[data-testid="stExpander"] {\n        background: var(--ca-surface);\n        border: 1px solid var(--ca-line);\n        border-radius: 12px;\n    }\n    div[data-testid="stProgress"] {\n        margin-top: .75rem;\n    }\n    div[data-testid="stProgress"] > div {\n        background-color: var(--ca-progress-bg) !important;\n        height: .68rem !important;\n        border-radius: 999px !important;\n        overflow: hidden !important;\n    }\n    div[data-testid="stProgress"] div[role="progressbar"] {\n        background-color: var(--ca-blue) !important;\n    }\n    div[data-baseweb="textarea"] {\n        border: 2px solid var(--ca-line-strong) !important;\n        border-radius: 14px !important;\n        box-shadow: none !important;\n        background: #ffffff !important;\n        overflow: hidden !important;\n    }\n    div[data-baseweb="textarea"]:focus-within {\n        border-color: var(--ca-blue) !important;\n        box-shadow: 0 0 0 1px rgba(14, 120, 144, .18) !important;\n    }\n    div[data-baseweb="textarea"] > div,\n    div[data-baseweb="textarea"] div {\n        border-color: transparent !important;\n        box-shadow: none !important;\n    }\n    div[data-baseweb="textarea"] textarea {\n        border: none !important;\n        outline: none !important;\n        box-shadow: none !important;\n        background: #ffffff !important;\n        color: var(--ca-text);\n        font-size: 1rem;\n        line-height: 1.65;\n        resize: vertical !important;\n    }\n    .stButton button {\n        border-radius: 10px;\n        border: 1px solid var(--ca-line-strong);\n        font-weight: 700;\n        min-height: 2.55rem;\n        padding-left: .5cm;\n        padding-right: .5cm;\n    }\n    .stButton button[kind="primary"],\n    div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] {\n        background: var(--ca-blue) !important;\n        border-color: var(--ca-blue) !important;\n        color: #ffffff !important;\n        box-shadow: 0 8px 18px rgba(14, 120, 144, .18) !important;\n    }\n    .stButton button[kind="primary"] *,\n    div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] * {\n        color: #ffffff !important;\n    }\n    div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] {\n        color: var(--ca-text) !important;\n        background: transparent !important;\n        border-color: transparent !important;\n    }\n    div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"]:hover {\n        color: var(--ca-blue-dark) !important;\n        border-color: var(--ca-line-strong) !important;\n        background: #ffffff !important;\n    }\n    .ca-step-row {\n        display: grid;\n        grid-template-columns: repeat(5, minmax(0, 1fr));\n        gap: .55rem;\n        padding: .85rem 0 1rem 0;\n        border-bottom: 1px solid var(--ca-line);\n    }\n    .ca-resume {\n        background: #ffffff;\n        border: 1px solid var(--ca-line);\n        border-radius: 14px;\n        padding: 2rem 2.3rem;\n        box-shadow: 0 10px 24px rgba(20, 40, 60, .06);\n    }\n    div[data-testid="stVerticalBlockBorderWrapper"] {\n        border-color: var(--ca-line) !important;\n        border-radius: 14px !important;\n        box-shadow: 0 10px 24px rgba(20, 40, 60, .05);\n        background: #ffffff;\n    }\n    .ca-history-row {\n        display: flex;\n        align-items: center;\n        justify-content: space-between;\n        gap: .7rem;\n        padding: .58rem 0;\n        border-bottom: 1px solid var(--ca-line);\n        font-size: .9rem;\n    }\n    .ca-history-row:last-child {\n        border-bottom: 0;\n    }\n    .ca-history-title {\n        color: var(--ca-text);\n        font-weight: 700;\n    }\n    .ca-history-meta {\n        color: var(--ca-muted);\n        font-size: .82rem;\n    }\n    </style>\n    ',
    unsafe_allow_html=True,
)
STEPS = [
    ("experience", "Experience Database", "Experience Bank"),
    ("jd", "Target JD", "Target JD"),
    ("match", "Match Summary", "Match Summary"),
    ("followup", "AI Follow-up Questions", "AI Follow-up"),
    ("resume", "Resume Draft", "Resume Draft"),
]


def safe_text(value) -> str:
    return html.escape(str(value or ""))


def workflow_cache_key(stage: str) -> str:
    payload = json.dumps(
        {
            "stage": stage,
            "experience_text": st.session_state.experience_text,
            "jd_text": st.session_state.jd_text,
            "model_version": getattr(simple_mvp, "DEFAULT_MODEL", ""),
            "language": "en",
            "scoring_version": getattr(simple_mvp, "SCORING_VERSION", ""),
            "rubric_version": getattr(simple_mvp, "COVERAGE_RUBRIC_VERSION", ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fit_level_label(value: str) -> str:
    labels = {
        "high_fit": "High Match",
        "good_fit": "Good Match",
        "partial_fit": "Partial Match",
        "weak_fit": "Weak Match",
        "low_fit": "Low Match",
        "strong_fit": "Strong Match",
        "adjacent_fit": "Transferable Match",
    }
    return labels.get(value, value or "-")


def render_score_bar(progress: float) -> None:
    width = max(0, min(100, int(round(progress * 100))))
    st.markdown(
        f'\n        <div class="ca-score-bar">\n            <div class="ca-score-fill" style="width: {width}%"></div>\n        </div>\n        ',
        unsafe_allow_html=True,
    )


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


DEMO_EXPERIENCE = "Mock test case for reference only\n\nThe following is not a formal resume but a user’s casually compiled experience database containing some duplicates, colloquial, and less concise expressions. CariAgent’s task is to extract facts and condense expressions from this raw material, then combine with the job description (JD) to generate a more resume-like version.\n\nMy general direction is data analysis/product operations. I majored in Information Management and Information Systems for my undergraduate studies from September 2021 to June 2025 at East China University of Finance and Economics. GPA 3.72/4.00; I won second prize once in a data analysis competition and led the data team of the university’s business analysis association. Relevant courses related to the role include database, statistics, Python data analysis, market research, operations management, and experimental design.\n\nFrom May 2024 to September 2024, I interned as a product operation intern in Alibaba Local Life’s in-store business. The focus was not primarily coding but analyzing merchant growth funnels. We examined funnel changes from new merchant onboarding, profile completion, first order conversion, event registration to repurchase. I used SQL to query city-level data and created a weekly dashboard covering about 12 city teams. Notably, a batch of merchants showed low conversion; initially, the team assumed poor merchant quality, but I broke down the pathway and discovered many merchants stalled at profile completion and benefit comprehension, also first-week exposure was insufficient. I collaborated with product, operations, and sales teams to revise the merchant task center by adding benefit explanations and task reminder rules. In pilot cities, first-week task completion rate increased by about 16%. I also participated in the 618 event retrospective, compiling GMV, order volume, subsidy cost, ROI metrics for reference in the next promotion phase.\n\nFrom November 2023 to March 2024, I interned in Tencent Ads' business analysis group, focusing more on data analysis. I frequently used SQL and Python to clean advertiser campaign data and produced weekly industry reports. Metrics included impressions, clicks, CTR, CVR, CPA, and budget consumption. I analyzed education, gaming, and local services industries, mainly studying creative performance, campaign timing, and converting audiences. Once, I found a client’s ads had good click rates but poor conversion; after review, we found targeting was too narrow and creatives were fatigued. I made a 20+ page visualization report for business colleagues to review clients.\n\nFrom June 2023 to September 2023, I interned in ByteDance’s commercialization growth tools direction as a data product intern. The experience was diverse. I helped streamline the merchant lead management tool process from lead creation, follow-up, conversion to loss, organizing fields and statuses. I interviewed 8 sales and operations colleagues; major feedback was inconsistent lead statuses, missing follow-up records, and repeated input. Later, I participated in requirement review, drafted the initial PRD, and pushed for lead status validation and follow-up reminders. The project outcome did not have clear business numbers but reduced manual checking costs for sales.\n\nIn a school project, I analyzed user retention for a campus food delivery platform from October 2024 to December 2024 using simulated order data. I cleaned data, constructed features, and conducted cohort analysis with Python, calculating retention, repurchase, and average order value. I later classified users into frequent/essential, price-sensitive, promotion-driven, and silent churn groups, providing coupon targeting and membership benefits optimization suggestions. Finally, I created a Tableau dashboard and presented a 15-minute report in class.\n\nAnother project was an RFM user segmentation from March 2024 to May 2024 using recency, frequency, and monetary values to score user value, then clustering with K-means. This was more methodological practice; I designed a recall strategy and simulated an A/B test plan measuring click-through rate, repurchase rate, and conversion cost.\n\nIn extracurriculars, from September 2022 to June 2023, I led the university’s business analysis association data team, organizing sharing sessions on instant retail, content e-commerce, and membership operations. I also led a 5-person team conducting campus coffee consumption surveys collecting over 300 questionnaires and produced a user persona report.\n\nSkills include SQL, Python, Excel, Tableau, PowerPoint. Methodologies covered: A/B testing, RFM, K-means, cohort analysis, user segmentation, funnel analysis, business analysis, and PRD writing."
DEMO_JD = "Data Analyst Intern\n\nJob Responsibilities:\n1. Support data analysis related to user growth, membership operations, and product iteration.\n2. Use SQL/Python to process business data, build daily metric dashboards, and analysis reports.\n3. Participate in user segmentation, event retrospectives, A/B testing, and conversion funnel analysis.\n4. Communicate with product, operations, and marketing teams to propose optimization suggestions based on data insights.\n\nQualifications:\n1. Familiar with SQL and experienced in Python or R data analysis.\n2. Understand basic statistical methods and can clearly explain analysis processes and conclusions.\n3. Prior project experience in user growth, product operations, market analysis, or business analysis is preferred.\n4. Good communication skills and ability for structured expression."


@st.cache_data(show_spinner=False)
def load_default_inputs(language: str) -> tuple[str, str]:
    return (DEMO_EXPERIENCE.strip(), DEMO_JD.strip())


def reset_demo_session_inputs() -> None:
    default_experience, default_jd = load_default_inputs("en")
    st.session_state.workflow_state = None
    st.session_state.openai_client = None
    st.session_state.current_step = "experience"
    st.session_state.analysis_done = False
    st.session_state.resume_done = False
    st.session_state.followup_done = False
    st.session_state.progress_log = []
    st.session_state.workflow_cache = {}
    st.session_state.experience_sections_cache = None
    st.session_state.experience_sections_cache_text = ""
    st.session_state.experience_text = default_experience
    st.session_state.jd_text = default_jd


def docx_run(text: str, bold: bool = False, size: int = 24) -> str:
    escaped = html.escape(text, quote=False)
    props = [f'<w:sz w:val="{size}"/>']
    if bold:
        props.insert(0, "<w:b/>")
    return (
        "<w:r><w:rPr>"
        + "".join(props)
        + f'</w:rPr><w:t xml:space="preserve">{escaped}</w:t></w:r>'
    )


def docx_paragraph(text: str, bold: bool = False, size: int = 24) -> str:
    return f"<w:p>{docx_run(text, bold=bold, size=size)}</w:p>"


def markdown_to_docx_bytes(markdown_text: str) -> bytes:
    paragraphs: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            paragraphs.append("<w:p/>")
            continue
        if line.startswith("# "):
            paragraphs.append(docx_paragraph(line[2:].strip(), bold=True, size=32))
        elif line.startswith("## "):
            paragraphs.append(docx_paragraph(line[3:].strip(), bold=True, size=28))
        elif line.startswith("### "):
            paragraphs.append(docx_paragraph(line[4:].strip(), bold=True, size=26))
        elif line.startswith(("- ", "* ")):
            paragraphs.append(docx_paragraph("• " + line[2:].strip(), size=23))
        else:
            paragraphs.append(docx_paragraph(line, size=23))
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:body>\n    {''.join(paragraphs)}\n    <w:sectPr>\n      <w:pgSz w:w="11906" w:h="16838"/>\n      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>\n    </w:sectPr>\n  </w:body>\n</w:document>"""
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n  <Default Extension="xml" ContentType="application/xml"/>\n  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n</Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n</Relationships>'
    output = BytesIO()
    with ZipFile(output, "w") as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/document.xml", document_xml)
    return output.getvalue()


def ensure_session_defaults() -> None:
    default_experience, default_jd = load_default_inputs("en")
    defaults = {
        "workflow_state": None,
        "openai_client": None,
        "current_step": "experience",
        "analysis_done": False,
        "resume_done": False,
        "followup_done": False,
        "followup_answer": "",
        "progress_log": [],
        "workflow_cache": {},
        "experience_sections_cache": None,
        "experience_sections_cache_text": "",
        "experience_text": default_experience,
        "jd_text": default_jd,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def extract_docx_text(raw: bytes) -> str:
    with ZipFile(BytesIO(raw)) as docx:
        xml = docx.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        texts = [node.text for node in paragraph.findall(".//w:t", ns) if node.text]
        text = "".join(texts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs).strip()


def extract_pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError(
            "PDF parsing requires pypdf. Install it with: python -m pip install pypdf"
        ) from error
    reader = PdfReader(BytesIO(raw))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join((page for page in pages if page)).strip()


def decode_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    raw = uploaded_file.getvalue()
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in {".txt", ".md"}:
        return raw.decode("utf-8", errors="ignore").strip()
    if suffix == ".docx":
        return extract_docx_text(raw)
    if suffix == ".pdf":
        return extract_pdf_text(raw)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        raise RuntimeError(
            "Image parsing requires integration with OCR or vision models; currently please paste text from the image first."
        )
    raise RuntimeError(f"Unsupported file type: {suffix or uploaded_file.name}")


def progress_writer(message: str) -> None:
    st.session_state.progress_log.append(message)


def visible_progress_writer(message: str) -> None:
    progress_writer(message)


def run_timed_step(label: str, fn):
    start = time.perf_counter()
    visible_progress_writer(f"{label} start")
    result = fn()
    elapsed = time.perf_counter() - start
    visible_progress_writer(f"{label} finished · {elapsed:.1f}s")
    return result


def page_title_for_step(step_key: str) -> str:
    return next((english for key, _, english in STEPS if key == step_key), "Workspace")


def status_for_step(step_key: str) -> str:
    state = st.session_state.workflow_state
    if step_key == "experience":
        return (
            "Experience database ready"
            if st.session_state.experience_text
            else "Waiting for experience database"
        )
    if step_key == "jd":
        return (
            "JD analyzed" if state and state.jd_analysis else "Waiting for JD analysis"
        )
    if step_key == "match":
        return (
            "Match summary generated"
            if state and state.fit_verdict
            else "Waiting for matching"
        )
    if step_key == "followup":
        if state and state.followup_plan:
            questions = get_prioritized_questions(state)
            if questions:
                handled = min(len(answered_question_ids(state)), len(questions))
                if handled >= len(questions):
                    return "Follow-up handled"
                return f"AI Follow-up {handled}/{len(questions)}"
            return "AI Follow-up in progress"
        return "Waiting for follow-up"
    if step_key == "resume":
        return (
            "Draft generated"
            if state and state.resume_markdown
            else "Waiting for draft generation"
        )
    return "Workspace"


def step_is_complete(step_key: str) -> bool:
    state = st.session_state.workflow_state
    if step_key == "experience":
        return bool(st.session_state.experience_text)
    if step_key == "jd":
        return bool(state and state.jd_analysis)
    if step_key == "match":
        return bool(state and state.fit_verdict)
    if step_key == "followup":
        if not state:
            return False
        questions = get_prioritized_questions(state)
        if not questions:
            return True
        return len(answered_question_ids(state)) >= len(questions)
    if step_key == "resume":
        return bool(state and state.resume_markdown)
    return False


def render_topbar() -> None:
    step = st.session_state.current_step
    st.markdown(
        f'\n        <div class="ca-topbar">\n            <div class="ca-brand">\n                <span class="ca-logo">C</span>\n                <span>CariAgent</span>\n            </div>\n            <div class="ca-top-title">{safe_text(page_title_for_step(step))}</div>\n            <div class="ca-status">\n                <span class="ca-status-dot"></span>{safe_text(status_for_step(step))}\n            </div>\n        </div>\n        ',
        unsafe_allow_html=True,
    )


def step_label(step: tuple[str, str, str]) -> str:
    key, zh, _ = step
    index = STEPS.index(step) + 1
    if step_is_complete(key):
        prefix = "✓"
    else:
        prefix = str(index)
    return f"{prefix}  {zh}"


def render_step_nav() -> None:
    cols = st.columns(len(STEPS))
    for col, step in zip(cols, STEPS):
        key, _, _ = step
        active = key == st.session_state.current_step
        with col:
            if st.button(
                step_label(step),
                key=f"step_nav_{key}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                st.session_state.current_step = key
                st.rerun()


def get_section_counts() -> dict[str, int]:
    state = st.session_state.workflow_state
    experience_sections = None
    if state and state.experience_sections:
        experience_sections = state.experience_sections
    elif (
        st.session_state.get("experience_sections_cache")
        and st.session_state.get("experience_sections_cache_text")
        == st.session_state.experience_text
    ):
        experience_sections = st.session_state.experience_sections_cache
    labels = {
        "profile": "Personal Summary",
        "education": "Education",
        "work_experience": "Work Experience",
        "internship_experience": "Internship Experience",
        "project_experience": "Project Experience",
        "campus_experience": "Campus Experience",
        "club_experience": "Club Activities",
        "volunteer_experience": "Volunteer Service",
        "awards": "Awards",
        "skills": "Skills",
        "certifications": "Certifications",
        "basic_information": "Basic Information",
        "hobbies": "Personal Interests",
        "other": "Others",
    }
    display_order = [
        "Personal Summary",
        "Basic Information",
        "Education",
        "Work Experience",
        "Internship Experience",
        "Project Experience",
        "Campus Experience",
        "Club Activities",
        "Volunteer Service",
        "Awards",
        "Skills",
        "Certifications",
        "Personal Interests",
        "Others",
    ]
    counts = {label: 0 for label in display_order}
    if not experience_sections:
        return counts
    for section in experience_sections.get("experience_sections", []):
        key = section.get("section_key", "")
        label = labels.get(key, section.get("section_name") or key or "Others")
        counts.setdefault(label, 0)
        records = section.get("experience_records") or []
        counts[label] += len(records) if records else 1
    return counts


def get_prioritized_questions(state: simple_mvp.WorkflowState) -> list[dict]:
    scored_matches = state.readiness_score.get("scored_matches", [])
    questions = [
        simple_mvp.calculate_question_priority(question, scored_matches)
        for question in state.followup_plan.get("candidate_questions", [])
    ]
    return sorted(
        questions, key=lambda item: item.get("question_priority_score", 0), reverse=True
    )


def reviewed_answer_items(state: simple_mvp.WorkflowState) -> list[dict]:
    if not state.reviewed_answers:
        return []
    return state.reviewed_answers.get("reviewed_answers", []) or []


def answered_question_ids(state: simple_mvp.WorkflowState) -> set[str]:
    return {
        item.get("question_id", "")
        for item in reviewed_answer_items(state)
        if item.get("question_id")
    }


def next_unanswered_question(
    state: simple_mvp.WorkflowState, questions: list[dict]
) -> tuple[dict | None, int]:
    answered_ids = answered_question_ids(state)
    for index, question in enumerate(questions, start=1):
        if question.get("id") not in answered_ids:
            return (question, index)
    return (None, len(questions))


def merge_reviewed_answer(
    state: simple_mvp.WorkflowState,
    reviewed_item: dict,
    updated_notes: list[str] | None,
    stop_reason: str,
) -> None:
    previous_items = reviewed_answer_items(state)
    previous_notes = []
    if state.reviewed_answers:
        previous_notes = (
            state.reviewed_answers.get("updated_experience_notes", []) or []
        )
    state.reviewed_answers = {
        "reviewed_answers": [*previous_items, reviewed_item],
        "updated_experience_notes": [*previous_notes, *(updated_notes or [])],
        "stop_reason": stop_reason,
        "estimated_readiness_score_after_followups": round(
            state.readiness_score.get("overall_readiness_score", 0), 3
        ),
    }


def set_reviewed_answers_from_question(
    client, state: simple_mvp.WorkflowState, question: dict, answer_text: str
) -> None:
    normalized = simple_mvp.normalize_user_control_text(answer_text)
    if normalized in simple_mvp.SKIP_WORDS or not answer_text.strip():
        reviewed_item = simple_mvp.build_pass_review_item(
            question, "User skipped this question in the Streamlit demo."
        )
        merge_reviewed_answer(
            state, reviewed_item, [], "streamlit_user_skipped_followup"
        )
        state.interaction_log.append(
            {"question": question, "review": reviewed_item, "source": "streamlit_demo"}
        )
        return
    answer = {
        "question_id": question["id"],
        "related_experience_id": question.get("related_experience_id", ""),
        "related_experience_name": question.get("related_experience_name", ""),
        "question": question["question"],
        "answer": answer_text.strip(),
    }
    reviewed = simple_mvp.review_user_answers(client, [answer])
    reviewed_item = reviewed.get("reviewed_answers", [{}])[0]
    reviewed_item.setdefault("question_id", question["id"])
    merge_reviewed_answer(
        state,
        reviewed_item,
        reviewed.get("updated_experience_notes", []),
        "streamlit_followup_answered",
    )
    state.reviewed_answers["estimated_readiness_score_after_followups"] = round(
        min(
            1.0,
            state.readiness_score.get("overall_readiness_score", 0)
            + question.get("expected_gain", 0),
        ),
        3,
    )
    state.interaction_log.append(
        {"question": question, "review": reviewed_item, "source": "streamlit_demo"}
    )


def run_jd_parse_from_session() -> None:
    st.session_state.progress_log = []
    st.session_state.analysis_done = False
    st.session_state.resume_done = False
    st.session_state.followup_done = False
    st.session_state.followup_answer = ""
    cache_key = workflow_cache_key("jd_parse")
    cached_state = st.session_state.workflow_cache.get(cache_key)
    if cached_state is not None:
        st.session_state.workflow_state = cached_state
        st.session_state.analysis_done = True
        progress_writer("Reuse cache: JD breakdown results")
        return
    with st.status(
        "CariAgent is breaking down the current JD...", expanded=True
    ) as status:
        status.update(label="CariAgent is preparing the running environment...")
        st.write("1/3 Preparing running environment")
        client = run_timed_step(
            "Initializing OpenAI client", simple_mvp.initialize_workflow_runtime
        )
        status.update(label="CariAgent is reading input...")
        st.write("2/3 Reading experience database and target JD")
        state = run_timed_step(
            "Reading experience database and JD",
            lambda: simple_mvp.create_workflow_state(
                st.session_state.experience_text, st.session_state.jd_text
            ),
        )
        if (
            st.session_state.experience_sections_cache
            and st.session_state.experience_sections_cache_text
            == st.session_state.experience_text
        ):
            state.experience_sections = st.session_state.experience_sections_cache
        status.update(label="CariAgent is breaking down the target JD...")
        st.write("3/3 Decomposing JD requirements")
        state = run_timed_step(
            "JD structured breakdown",
            lambda: simple_mvp.run_jd_analysis_workflow(client, state),
        )
        st.session_state.workflow_state = state
        st.session_state.openai_client = client
        st.session_state.analysis_done = True
        st.session_state.workflow_cache[cache_key] = state
        status.update(label="JD breakdown completed", state="complete")


def run_match_from_session() -> None:
    state = st.session_state.workflow_state
    client = st.session_state.openai_client
    if not state or not state.jd_analysis:
        run_jd_parse_from_session()
        state = st.session_state.workflow_state
        client = st.session_state.openai_client
    if client is None:
        client = simple_mvp.initialize_workflow_runtime()
        st.session_state.openai_client = client
    cache_key = workflow_cache_key("match_summary")
    cached_state = st.session_state.workflow_cache.get(cache_key)
    if cached_state is not None:
        st.session_state.workflow_state = cached_state
        progress_writer("Reuse cache: match summary")
        return
    with st.status(
        "CariAgent is retrieving evidence and generating the match summary...",
        expanded=True,
    ) as status:
        status.update(label="CariAgent is retrieving relevant experience evidence...")
        st.write("1/4 Retrieving experience evidence")
        state = run_timed_step(
            "Experience database segmentation + RAG retrieval",
            lambda: simple_mvp.run_retrieval_workflow(
                client, state, progress_callback=visible_progress_writer
            ),
        )
        status.update(
            label="CariAgent is organizing evidence and judging coverage levels..."
        )
        st.write("2/4 Organizing evidence atoms and judging coverage level")
        state = run_timed_step(
            "Atoms extraction + matching + Fit judgment",
            lambda: simple_mvp.run_matching_workflow(
                client, state, progress_callback=visible_progress_writer
            ),
        )
        status.update(label="CariAgent is generating follow-up plan...")
        st.write("3/4 Generate follow-up plan")
        state = run_timed_step(
            "Follow-up plan generation",
            lambda: simple_mvp.run_followup_planning_workflow(state),
        )
        st.write("4/4 Save match summary")
        st.session_state.workflow_state = state
        st.session_state.openai_client = client
        if state.experience_sections:
            st.session_state.experience_sections_cache = state.experience_sections
            st.session_state.experience_sections_cache_text = state.experience_text
        st.session_state.workflow_cache[cache_key] = state
        status.update(label="Match summary generated", state="complete")


def render_page_heading(title: str, subtitle: str) -> None:
    st.markdown(
        f'\n        <div class="ca-page">\n            <div class="ca-page-title">{safe_text(title)}</div>\n            <div class="ca-page-subtitle">{safe_text(subtitle)}</div>\n        </div>\n        ',
        unsafe_allow_html=True,
    )


def render_experience_page() -> None:
    render_page_heading(
        "Experience Database",
        "Maintain your authentic professional experience. CariAgent will extract evidence from here to match every role.",
    )
    counts = get_section_counts()
    st.markdown(
        "".join(
            (
                f"""<span class="ca-pill">{safe_text(name)} {(count if count else '')}</span>"""
                for name, count in counts.items()
            )
        ),
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "Import Resume/Document",
        type=["txt", "md", "docx", "pdf", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            uploaded_text = decode_uploaded_file(uploaded)
            if uploaded_text:
                st.session_state.experience_text = uploaded_text
                st.session_state.workflow_state = None
                st.success("Uploaded content read, can continue editing.")
        except Exception as error:
            st.warning(str(error))
    st.text_area(
        "Plain Text Editing (Markdown Format)", key="experience_text", height=430
    )
    st.markdown(
        f'\n        <div class="ca-soft-card">\n            <span class="ca-success">✓ Experience database ready</span><br>\n            <span class="ca-muted">Evidence Source · {len(st.session_state.experience_text)} characters</span>\n        </div>\n        ',
        unsafe_allow_html=True,
    )
    _, right = st.columns([3, 1])
    if right.button(
        "Continue filling in the target JD  →", type="primary", use_container_width=True
    ):
        st.session_state.current_step = "jd"
        st.rerun()


def render_jd_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        "Target JD",
        "Paste a job description you are interested in, CariAgent will extract the core requirements.",
    )
    if state and state.jd_analysis:
        jd = state.jd_analysis
        st.markdown(
            f"""\n            <div class="ca-card">\n                <div class="ca-label">Target Role</div>\n                <h2>{safe_text(jd.get('role_title', 'Target Role'))}</h2>\n                <p>{safe_text(jd.get('job_goal', ''))}</p>\n            </div>\n            """,
            unsafe_allow_html=True,
        )
        st.markdown("#### Core Requirements")
        for item in (jd.get("core_responsibilities", []) or [])[:5]:
            st.write(f"- {item}")
        keywords = jd.get("keywords_to_mirror", []) or []
        if keywords:
            st.markdown("#### Keywords")
            st.markdown(
                "".join(
                    (
                        f'<span class="ca-pill">{safe_text(item)}</span>'
                        for item in keywords[:12]
                    )
                ),
                unsafe_allow_html=True,
            )
        with st.expander("View full JD parsing details", expanded=False):
            st.json(jd, expanded=False)
        left, right = st.columns([1, 1])
        if left.button("← Paste JD again"):
            st.session_state.workflow_state = None
            st.rerun()
        if right.button("View Match Summary  →", type="primary"):
            if not state.fit_verdict:
                try:
                    run_match_from_session()
                except Exception as error:
                    st.error(f"Match analysis failed: {type(error).__name__}: {error}")
                    return
            st.session_state.current_step = "match"
            st.rerun()
        return
    uploaded = st.file_uploader(
        "Upload JD File",
        type=["txt", "md", "docx", "pdf", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            uploaded_text = decode_uploaded_file(uploaded)
            if uploaded_text:
                st.session_state.jd_text = uploaded_text
                st.success("Uploaded JD read, can continue editing.")
        except Exception as error:
            st.warning(str(error))
    st.text_area("Job Description (JD)", key="jd_text", height=420)
    st.caption(f"{len(st.session_state.jd_text)} characters")
    _, right = st.columns([3, 1])
    if right.button("Analyze JD", type="primary", use_container_width=True):
        try:
            run_jd_parse_from_session()
            st.rerun()
        except Exception as error:
            st.error(f"Run failed: {type(error).__name__}: {error}")


def score_to_display(score) -> tuple[int, float]:
    if not isinstance(score, (int, float)):
        return (0, 0.0)
    percent = int(round(score * 100))
    return (percent, max(0.0, min(1.0, float(score))))


def short_items(items: list[str], limit: int = 3) -> list[str]:
    return [str(item) for item in (items or [])[:limit]]


def render_summary_card(
    title: str, items: list[str], icon_class: str, icon: str
) -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        display_items = short_items(items, 3)
        if not display_items:
            st.caption("No entries available for display")
            return
        for item in display_items:
            st.markdown(
                f'<div class="ca-summary-item"><span class="{icon_class}">{icon}</span><span class="ca-summary-item-text">{safe_text(item)}</span></div>',
                unsafe_allow_html=True,
            )


def render_match_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        "Match Summary",
        "Based on your experience database and the RAG retrieval results of the target JD.",
    )
    if not state or not state.fit_verdict:
        st.info(
            "No match summary yet. Please run analysis first on the target JD page."
        )
        c1, c2 = st.columns([1, 1])
        if c1.button("Go fill target JD"):
            st.session_state.current_step = "jd"
            st.rerun()
        if (
            state
            and state.jd_analysis
            and c2.button("Start Matching Analysis", type="primary")
        ):
            try:
                run_match_from_session()
                st.rerun()
            except Exception as error:
                st.error(f"Match analysis failed: {type(error).__name__}: {error}")
        return
    percent, progress = score_to_display(
        state.readiness_score.get("overall_readiness_score", 0)
    )
    col_score, col_fit = st.columns(2)
    with col_score:
        st.markdown(
            f'\n            <div class="ca-card">\n                <div class="ca-label">Readiness Score</div>\n                <span class="ca-big-score">{percent}</span><span class="ca-score-denom"> /100</span>\n                <p class="ca-muted">Based on RAG retrieval experience coverage</p>\n            </div>\n            ',
            unsafe_allow_html=True,
        )
        render_score_bar(progress)
    with col_fit:
        st.markdown(
            f"""\n            <div class="ca-card">\n                <div class="ca-label">Fit Verdict</div>\n                <span class="ca-pill">{safe_text(fit_level_label(state.fit_verdict.get('fit_level', '-')))}</span>\n                <p>{safe_text(state.fit_verdict.get('fit_summary', ''))}</p>\n            </div>\n            """,
            unsafe_allow_html=True,
        )
    col_match, col_gap = st.columns(2)
    with col_match:
        render_summary_card(
            "TOP Matches", state.fit_verdict.get("major_matches", []), "ca-check", "✓"
        )
    with col_gap:
        render_summary_card(
            "TOP Gaps", state.fit_verdict.get("major_gaps", []), "ca-warn", "⚠"
        )
    with st.expander("View RAG Evidence", expanded=False):
        chunks = state.retrieval_result.get("selected_chunks", [])
        st.caption(f"Selected evidence chunks: {len(chunks)}")
        for index, chunk in enumerate(chunks[:20], start=1):
            with st.expander(
                f"Evidence {index}: {chunk.get('experience_title', 'Unrecognized Source')}"
            ):
                st.caption(chunk.get("section_group", ""))
                st.write(chunk.get("text", ""))
    with st.expander("View Matching Experience Details", expanded=False):
        st.json(state.match_result, expanded=False)
    with st.expander("View Workflow Trace", expanded=False):
        if st.session_state.progress_log:
            for item in st.session_state.progress_log:
                st.write(item)
        else:
            st.write("Workflow trace will appear after a new run.")
        api_calls = getattr(simple_mvp, "API_CALL_TRACE", [])
        if api_calls:
            st.markdown("#### API calls")
            for call in api_calls[-10:]:
                elapsed = call.get("elapsed_seconds")
                elapsed_text = (
                    f" · {elapsed:.1f}s" if isinstance(elapsed, (int, float)) else ""
                )
                usage = call.get("usage") or {}
                tokens = usage.get("total_tokens")
                token_text = f" · {tokens} tokens" if tokens else ""
                st.write(
                    f"{call.get('call_name', '-')}: {call.get('model', '-')}{elapsed_text}{token_text}"
                )
    left, right = st.columns([1, 1])
    if left.button("← Return to Target JD"):
        st.session_state.current_step = "jd"
        st.rerun()
    if right.button("Continue AI Follow-up  →", type="primary"):
        st.session_state.current_step = "followup"
        st.rerun()


def generate_resume_from_state(state: simple_mvp.WorkflowState) -> None:
    client = st.session_state.openai_client or simple_mvp.initialize_workflow_runtime()
    with st.spinner("Generating resume draft..."):
        state = simple_mvp.run_resume_generation_workflow(client, state)
        simple_mvp.save_workflow_trace(state)
        st.session_state.workflow_state = state
        st.session_state.resume_done = True
    st.session_state.current_step = "resume"
    st.rerun()


def render_followup_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        "AI Follow-up", "Prioritize addressing the most valuable evidence gaps."
    )
    if not state:
        st.info("Please run JD analysis first.")
        return
    st.markdown(
        '<div class="ca-footnote">* This answer is only for the current resume generation.</div>',
        unsafe_allow_html=True,
    )
    questions = get_prioritized_questions(state)
    question, question_index = next_unanswered_question(state, questions)
    if question:
        question_count = len(questions)
        st.markdown(
            f"""\n            <div class="ca-card">\n                <div class="ca-label">CariAgent Follow-up · {question_index} / {question_count}</div>\n                <div class="ca-question-text">{safe_text(question.get('question', ''))}</div>\n            </div>\n            """,
            unsafe_allow_html=True,
        )
        with st.expander("Why ask this question?", expanded=False):
            col_reason, col_exp = st.columns(2)
            with col_reason:
                st.caption("Reason for question")
                st.write(question.get("why_ask", ""))
                st.caption("Missing evidence type")
                st.write(question.get("target_requirement", ""))
            with col_exp:
                st.caption("Related Experience")
                st.write(question.get("related_experience_name", ""))
    elif questions:
        st.success(
            "This round of candidate follow-up questions completed, resume draft can be generated."
        )
    else:
        st.info(
            "No candidate follow-up questions currently, can generate resume draft directly."
        )
    if question:
        answer_text = st.text_area(
            "Your Answer",
            key=f"followup_answer_{question.get('id', question_index)}",
            height=180,
            placeholder="Enter your answer here, try to include concrete details, data, or decision processes.",
        )
        skip_col, submit_col, resume_col = st.columns([1, 1, 1])
        with skip_col:
            if st.button("Skip", key="followup_skip"):
                set_reviewed_answers_from_question(
                    st.session_state.openai_client, state, question, ""
                )
                st.rerun()
        with submit_col:
            if st.button("Submit Answer", key="followup_submit", type="primary"):
                client = (
                    st.session_state.openai_client
                    or simple_mvp.initialize_workflow_runtime()
                )
                try:
                    set_reviewed_answers_from_question(
                        client, state, question, answer_text
                    )
                    st.session_state.followup_done = True
                    st.rerun()
                except Exception as error:
                    st.error(
                        f"Follow-up answer interpretation failed: {type(error).__name__}: {error}"
                    )
        with resume_col:
            if st.button(
                "Generate Resume Draft  →",
                key="followup_generate_inline",
                type="primary",
            ):
                try:
                    generate_resume_from_state(state)
                except Exception as error:
                    st.error(
                        f"Resume generation failed: {type(error).__name__}: {error}"
                    )
    elif state.reviewed_answers:
        items = reviewed_answer_items(state)
        info = items[-1] if items else {}
        usable = (
            "；".join(info.get("usable_information", []) or [])
            or "This round of answers recorded."
        )
        st.markdown(
            f'\n            <div class="ca-card">\n                <span class="ca-success">✓ Processed {len(items)} follow-up questions</span>\n                <p>{safe_text(usable)}</p>\n            </div>\n            ',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="ca-followup-actions-spacer"></div>', unsafe_allow_html=True
    )
    nav_col, _, resume_col = st.columns([1, 1, 1])
    with nav_col:
        if st.button("← Return to Match Summary", key="followup_back"):
            st.session_state.current_step = "match"
            st.rerun()
    if not question:
        with resume_col:
            if st.button(
                "Generate Resume Draft  →",
                key="followup_generate_bottom",
                type="primary",
            ):
                try:
                    generate_resume_from_state(state)
                except Exception as error:
                    st.error(
                        f"Resume generation failed: {type(error).__name__}: {error}"
                    )


def experiences_used(state: simple_mvp.WorkflowState) -> list[str]:
    names: list[str] = []
    for match in state.match_result.get("matches", []):
        for name in match.get("matched_experience_names", []) or []:
            if name and name not in names:
                names.append(name)
    return names[:6]


def render_resume_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        "Resume Draft",
        "Generated based on experience database + RAG retrieval + AI follow-up answers.",
    )
    if not state:
        st.info("Please run JD analysis first.")
        return
    if not state.resume_markdown:
        st.info("Resume draft has not been generated yet.")
        if st.button("Go to AI Follow-up / Generate Draft"):
            st.session_state.current_step = "followup"
            st.rerun()
        return
    left, right = st.columns([2.2, 1])
    with left:
        with st.container(border=True):
            st.markdown(state.resume_markdown)
    with right:
        with st.container(border=True):
            st.markdown("#### Experiences Used")
            for name in experiences_used(state):
                st.write(f"✓ {name}")
            st.markdown("---")
            st.markdown("#### Strongest Evidence")
            for item in short_items(state.fit_verdict.get("major_matches", []), 2):
                st.write(f"- {item}")
    md_col, docx_col = st.columns([1, 1])
    with md_col:
        st.download_button(
            "Download Markdown",
            data=state.resume_markdown,
            file_name="cariagent_resume_en.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with docx_col:
        st.download_button(
            "Download Word (.docx)",
            data=markdown_to_docx_bytes(state.resume_markdown),
            file_name="cariagent_resume_en.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    if state.improvement_suggestions_markdown:
        with st.expander(
            "Resume Improvement Suggestions (Not Included in Downloaded File)",
            expanded=True,
        ):
            st.markdown(state.improvement_suggestions_markdown)


def display_last_run() -> None:
    state = st.session_state.get("workflow_state")
    if not state or not any(
        [state.fit_verdict, state.readiness_score, state.resume_markdown]
    ):
        st.info("No historical runs available for display in the current session.")
        return
    score = "-"
    if isinstance(state.readiness_score.get("overall_readiness_score"), (int, float)):
        score = f"{state.readiness_score.get('overall_readiness_score'):.3f}"
    fit_level = fit_level_label((state.fit_verdict or {}).get("fit_level", "-"))
    recommendation = (state.fit_verdict or {}).get("recommendation", "-")
    st.markdown(
        f'\n        <div class="ca-history-row">\n            <div>\n                <div class="ca-history-title">Current Session</div>\n                <div class="ca-history-meta">Readiness {safe_text(score)} · {safe_text(fit_level)}</div>\n            </div>\n            <div class="ca-history-meta">{safe_text(recommendation)}</div>\n        </div>\n        ',
        unsafe_allow_html=True,
    )
    with st.expander("View Resume Draft", expanded=False):
        st.markdown(state.resume_markdown or "No resume output yet")


def display_sidebar_experience_bank() -> None:
    try:
        counts = get_section_counts()
    except Exception as error:
        st.caption(
            f"Experience database summary temporarily unavailable: {type(error).__name__}"
        )
        counts = {}
    st.caption(
        f"Current experience database: {len(st.session_state.experience_text)} characters"
    )
    visible_counts = [f"{name} {count}" for name, count in counts.items() if count]
    if visible_counts:
        st.caption(" · ".join(visible_counts))
    else:
        st.caption("Structured parsing not yet completed, current saved text is raw.")
    if st.button("Open Experience Database", use_container_width=True):
        st.session_state.current_step = "experience"
        st.rerun()


def main() -> None:
    ensure_session_defaults()
    render_topbar()
    render_step_nav()
    st.sidebar.title("CariAgent")
    st.sidebar.write("OpenAI API Key")
    if os.getenv("OPENAI_API_KEY"):
        st.sidebar.success("Configured")
    else:
        st.sidebar.warning("Not Configured")
    st.sidebar.caption("Use Streamlit Secrets for public deployment.")
    with st.sidebar.expander("Personal Experience Database", expanded=True):
        display_sidebar_experience_bank()
    with st.sidebar.expander("History", expanded=False):
        display_last_run()
        if st.button("Reset Current Session", use_container_width=True):
            reset_demo_session_inputs()
            st.session_state.history_clear_message = "Current session reset, and virtual test cases restored. Local outputs folder will not be deleted."
            st.rerun()
    if st.session_state.get("history_clear_message"):
        st.sidebar.success(st.session_state.history_clear_message)
        st.session_state.history_clear_message = ""
    step = st.session_state.current_step
    if step == "experience":
        render_experience_page()
    elif step == "jd":
        render_jd_page()
    elif step == "match":
        render_match_page()
    elif step == "followup":
        render_followup_page()
    elif step == "resume":
        render_resume_page()


if __name__ == "__main__":
    main()
