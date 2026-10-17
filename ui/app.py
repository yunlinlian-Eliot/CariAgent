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
    """
    <style>
    :root {
        --ca-bg: #f7f9fc;
        --ca-surface: #ffffff;
        --ca-surface-soft: #f1f6fa;
        --ca-line: #d9e3ea;
        --ca-line-strong: #c5d3dc;
        --ca-text: #101828;
        --ca-muted: #667785;
        --ca-blue: #0e7890;
        --ca-blue-dark: #0b6379;
        --ca-blue-soft: #e8f5f8;
        --ca-progress-bg: #d5e2ea;
        --ca-green: #12805c;
        --ca-amber: #a96800;
    }
    header[data-testid="stHeader"] {
        display: block !important;
        visibility: visible !important;
        background: rgba(247, 249, 252, .96);
        height: 2.75rem !important;
    }
    .stApp {
        background: var(--ca-bg);
    }
    .block-container {
        max-width: 1180px;
        padding-top: 1.25rem;
        padding-bottom: 3rem;
    }
    h1, h2, h3, p {
        letter-spacing: 0;
    }
    div[data-testid="stMarkdown"] h1 {
        font-size: 2rem;
        line-height: 1.22;
        margin: .25rem 0 1.1rem;
    }
    div[data-testid="stMarkdown"] h2 {
        font-size: 1.45rem;
        line-height: 1.3;
        margin: 1.45rem 0 .7rem;
    }
    div[data-testid="stMarkdown"] h3 {
        font-size: 1.16rem;
        line-height: 1.35;
        margin: 1rem 0 .5rem;
    }
    div[data-testid="stSidebar"] {
        background: #eef3f7;
        border-right: 1px solid var(--ca-line);
        width: min(13vw, 180px) !important;
        min-width: 150px !important;
    }
    div[data-testid="stSidebar"] > div:first-child {
        width: min(13vw, 180px) !important;
        min-width: 150px !important;
        padding-left: .65rem;
        padding-right: .65rem;
    }
    .ca-topbar {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: center;
        gap: 1rem;
        padding: .85rem 0 1.05rem 0;
        border-bottom: 1px solid var(--ca-line);
        margin-bottom: .75rem;
        min-height: 72px;
        overflow: visible;
    }
    .ca-brand {
        display: flex;
        align-items: center;
        gap: .8rem;
        font-weight: 760;
        color: var(--ca-text);
        font-size: 1.08rem;
    }
    .ca-logo {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        background: linear-gradient(135deg, #0d7891, #0a6780);
        color: white;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 780;
        box-shadow: 0 8px 18px rgba(14, 120, 144, .18);
    }
    .ca-top-title {
        color: var(--ca-muted);
        font-size: 1.03rem;
        font-weight: 650;
    }
    .ca-status {
        justify-self: end;
        color: var(--ca-blue-dark);
        font-weight: 700;
        font-size: .9rem;
    }
    .ca-status-dot {
        display: inline-block;
        width: .52rem;
        height: .52rem;
        border-radius: 999px;
        background: var(--ca-blue);
        margin-right: .45rem;
    }
    .ca-page {
        margin-top: 2.6rem;
    }
    .ca-page-title {
        color: var(--ca-text);
        font-size: 1.8rem;
        font-weight: 780;
        margin-bottom: .35rem;
    }
    .ca-page-subtitle {
        color: var(--ca-muted);
        font-size: 1.02rem;
        line-height: 1.55;
        margin-bottom: 1.6rem;
    }
    .ca-card {
        background: var(--ca-surface);
        border: 1px solid var(--ca-line);
        border-radius: 14px;
        padding: 1.35rem 1.45rem;
        box-shadow: 0 10px 24px rgba(20, 40, 60, .05);
    }
    .ca-soft-card {
        background: var(--ca-surface-soft);
        border: 1px solid var(--ca-line);
        border-radius: 14px;
        padding: 1.15rem 1.3rem;
    }
    .ca-card-title {
        color: var(--ca-text);
        font-weight: 760;
        font-size: .96rem;
        margin-bottom: .35rem;
    }
    .ca-label {
        color: var(--ca-muted);
        font-size: .78rem;
        font-weight: 730;
        letter-spacing: .06em;
        text-transform: uppercase;
        margin-bottom: .55rem;
    }
    .ca-pill {
        display: inline-flex;
        align-items: center;
        border: 1px solid #b9dce5;
        background: #edf8fb;
        color: var(--ca-blue-dark);
        border-radius: 999px;
        padding: .28rem .68rem;
        margin: .18rem .22rem .18rem 0;
        font-size: .86rem;
        font-weight: 620;
    }
    .ca-muted {
        color: var(--ca-muted);
    }
    .ca-success {
        color: var(--ca-green);
        font-weight: 720;
    }
    .ca-warning {
        color: var(--ca-amber);
        font-weight: 720;
    }
    .ca-big-score {
        font-size: 3rem;
        line-height: 1;
        color: var(--ca-text);
        font-weight: 800;
    }
    .ca-score-denom {
        color: var(--ca-muted);
        font-size: 1.4rem;
        font-weight: 650;
    }
    .ca-two-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
    }
    .ca-list-item {
        border-bottom: 1px solid var(--ca-line);
        padding: .55rem 0;
        line-height: 1.45;
    }
    .ca-list-item:last-child {
        border-bottom: 0;
    }
    .ca-summary-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        margin-top: 1rem;
    }
    .ca-summary-card {
        background: var(--ca-surface);
        border: 1px solid var(--ca-line);
        border-radius: 14px;
        padding: 1.05rem 1.2rem;
        box-shadow: 0 8px 18px rgba(20, 40, 60, .04);
    }
    .ca-summary-item {
        padding: .72rem 0;
        line-height: 1.58;
        border-bottom: 1px solid var(--ca-line);
    }
    .ca-summary-item:last-child {
        border-bottom: 0;
    }
    .ca-summary-item-text {
        line-height: 1.58;
    }
    .ca-score-bar {
        width: 100%;
        height: .7rem;
        border-radius: 999px;
        background: var(--ca-progress-bg);
        overflow: hidden;
        margin-top: .9rem;
    }
    .ca-score-fill {
        height: 100%;
        border-radius: 999px;
        background: var(--ca-blue);
    }
    .ca-question-text {
        font-size: 1.28rem;
        line-height: 1.42;
        font-weight: 760;
        color: var(--ca-text);
        margin-top: .75rem;
    }
    .ca-footnote {
        color: var(--ca-muted);
        font-size: .84rem;
        margin: -.8rem 0 1.15rem;
    }
    .ca-followup-actions-spacer {
        height: 1.25rem;
    }
    .ca-check {
        color: var(--ca-green);
        font-weight: 800;
        margin-right: .35rem;
    }
    .ca-warn {
        color: var(--ca-amber);
        font-weight: 800;
        margin-right: .35rem;
    }
    div[data-testid="stMetric"] {
        background: var(--ca-surface);
        border: 1px solid var(--ca-line);
        border-radius: 12px;
        padding: .9rem 1rem;
        box-shadow: 0 8px 18px rgba(20, 40, 60, .04);
    }
    div[data-testid="stExpander"] {
        background: var(--ca-surface);
        border: 1px solid var(--ca-line);
        border-radius: 12px;
    }
    div[data-testid="stProgress"] {
        margin-top: .75rem;
    }
    div[data-testid="stProgress"] > div {
        background-color: var(--ca-progress-bg) !important;
        height: .68rem !important;
        border-radius: 999px !important;
        overflow: hidden !important;
    }
    div[data-testid="stProgress"] div[role="progressbar"] {
        background-color: var(--ca-blue) !important;
    }
    div[data-baseweb="textarea"] {
        border: 2px solid var(--ca-line-strong) !important;
        border-radius: 14px !important;
        box-shadow: none !important;
        background: #ffffff !important;
        overflow: hidden !important;
    }
    div[data-baseweb="textarea"]:focus-within {
        border-color: var(--ca-blue) !important;
        box-shadow: 0 0 0 1px rgba(14, 120, 144, .18) !important;
    }
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="textarea"] div {
        border-color: transparent !important;
        box-shadow: none !important;
    }
    div[data-baseweb="textarea"] textarea {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: #ffffff !important;
        color: var(--ca-text);
        font-size: 1rem;
        line-height: 1.65;
        resize: vertical !important;
    }
    .stButton button {
        border-radius: 10px;
        border: 1px solid var(--ca-line-strong);
        font-weight: 700;
        min-height: 2.55rem;
        padding-left: .5cm;
        padding-right: .5cm;
    }
    .stButton button[kind="primary"],
    div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
        background: var(--ca-blue) !important;
        border-color: var(--ca-blue) !important;
        color: #ffffff !important;
        box-shadow: 0 8px 18px rgba(14, 120, 144, .18) !important;
    }
    .stButton button[kind="primary"] *,
    div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] * {
        color: #ffffff !important;
    }
    div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"] {
        color: var(--ca-text) !important;
        background: transparent !important;
        border-color: transparent !important;
    }
    div[data-testid="stButton"] button[data-testid="stBaseButton-secondary"]:hover {
        color: var(--ca-blue-dark) !important;
        border-color: var(--ca-line-strong) !important;
        background: #ffffff !important;
    }
    .ca-step-row {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: .55rem;
        padding: .85rem 0 1rem 0;
        border-bottom: 1px solid var(--ca-line);
    }
    .ca-resume {
        background: #ffffff;
        border: 1px solid var(--ca-line);
        border-radius: 14px;
        padding: 2rem 2.3rem;
        box-shadow: 0 10px 24px rgba(20, 40, 60, .06);
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--ca-line) !important;
        border-radius: 14px !important;
        box-shadow: 0 10px 24px rgba(20, 40, 60, .05);
        background: #ffffff;
    }
    .ca-history-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .7rem;
        padding: .58rem 0;
        border-bottom: 1px solid var(--ca-line);
        font-size: .9rem;
    }
    .ca-history-row:last-child {
        border-bottom: 0;
    }
    .ca-history-title {
        color: var(--ca-text);
        font-weight: 700;
    }
    .ca-history-meta {
        color: var(--ca-muted);
        font-size: .82rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


STEPS = [
    ("experience", localized('经历库', 'Experience Database'), "Experience Bank"),
    ("jd", localized('目标 JD', 'Target JD'), "Target JD"),
    ("match", localized('匹配摘要', 'Match Summary'), "Match Summary"),
    ("followup", localized('AI 追问', 'AI Follow-up Questions'), "AI Follow-up"),
    ("resume", localized('简历草稿', 'Resume Draft'), "Resume Draft"),
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
            "language": "en" if is_english() else "zh",
            "scoring_version": getattr(simple_mvp, "SCORING_VERSION", ""),
            "rubric_version": getattr(simple_mvp, "COVERAGE_RUBRIC_VERSION", ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fit_level_label(value: str) -> str:
    labels = {
        "high_fit": localized('高匹配', 'High Match'),
        "good_fit": localized('良好匹配', 'Good Match'),
        "partial_fit": localized('部分匹配', 'Partial Match'),
        "weak_fit": localized('弱匹配', 'Weak Match'),
        "low_fit": localized('低匹配', 'Low Match'),
        "strong_fit": localized('强匹配', 'Strong Match'),
        "adjacent_fit": localized('可迁移匹配', 'Transferable Match'),
    }
    return labels.get(value, value or "-")


def render_score_bar(progress: float) -> None:
    width = max(0, min(100, int(round(progress * 100))))
    st.markdown(
        f"""
        <div class="ca-score-bar">
            <div class="ca-score-fill" style="width: {width}%"></div>
        </div>
        """,
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


DEMO_EXPERIENCE = localized('模拟测试用例，仅用于参考\n\n下面不是正式简历，是一个用户随手整理的经历库，里面有一些重复、口语化和不够精炼的表达。CariAgent 的任务就是从这种原始材料里提取事实、压缩表达，再结合 JD 生成更像简历的版本。\n\n我大概是数据分析 / 产品运营方向，本科是信息管理与信息系统，2021.09 到 2025.06 在华东财经大学。GPA 3.72/4.00，拿过一次数据分析竞赛二等奖，也做过校商业分析协会的数据组负责人。课程里面和岗位比较相关的有数据库、统计学、Python 数据分析、市场调研、运营管理、实验设计。\n\n2024.05-2024.09，我在阿里巴巴本地生活的到店业务做产品运营实习。主要不是写代码，而是围绕商家成长链路做分析。我们会看新商家从入驻、资料补全、首单转化、活动报名到复购的漏斗变化。我当时用 SQL 拉过一些城市维度的数据，也做过一个周度看板，覆盖大概 12 个城市团队。印象比较深的是有一批商家转化低，最开始大家以为是商家质量差，但我拆了一下路径，发现很多商家卡在资料补全和权益理解这里，另外首周曝光也不够。所以我和产品、运营、销售一起讨论了商家任务中心的改版，主要加了权益解释和任务提醒规则。试点城市首周任务完成率大概提升了 16%。618 活动复盘我也参与过，当时整理了 GMV、订单量、补贴成本、ROI 这些指标，给下一阶段投放做参考。\n\n2023.11-2024.03，我在腾讯广告商业分析组实习。这个更偏数据分析。工作里经常用 SQL 和 Python 清洗广告主投放数据，然后做行业周报。指标包括曝光、点击、CTR、CVR、CPA、预算消耗这些。我分析过教育、游戏、本地服务三个行业，主要看素材表现、投放时段、转化人群这些。有一次发现某个客户的素材点击还可以但转化很差，后来复盘发现是定向人群太窄，而且素材已经疲劳。我做过 20 多页的可视化分析报告，给业务同学做客户复盘用。\n\n2023.06-2023.09，我在字节跳动商业化的增长工具方向做数据产品实习。那段经历比较杂。我帮忙梳理过商家线索管理工具的流程，从线索创建、跟进、转化到流失，把字段和状态都整理了一遍。还访谈过 8 个销售和运营同学，大家反馈比较多的问题是线索状态不统一、跟进记录缺失、重复录入。后来我参与需求评审，写过 PRD 初稿，推动加了线索状态校验和跟进提醒。这个项目的结果没有特别明确的业务数字，但确实减少了一些销售手工核对成本。\n\n学校项目里有一个校园外卖平台用户留存分析，时间大概是 2024.10-2024.12。用的是模拟订单数据。我用 Python 做清洗、特征构造和 cohort 分析，算了留存、复购、客单价。后来把用户分成高频刚需、价格敏感、活动驱动、沉默流失几类，给了优惠券触达和会员权益优化建议。最后用 Tableau 做了 dashboard，在课上做了 15 分钟汇报。\n\n还有一个 RFM 用户分层项目，2024.03-2024.05。就是用 recency、frequency、monetary 算用户价值分，再用 K-means 分群。这个项目比较偏方法练习，但我有设计一个召回策略，也模拟了 A/B 测试方案，指标设的是点击率、复购率、转化成本。\n\n社团方面，2022.09-2023.06 我负责过校商业分析协会的数据组，组织过即时零售、内容电商、会员运营相关分享。还带 5 个人做过校园咖啡消费调研，收了 300 多份问卷，最后做了用户画像报告。\n\n技能大概是 SQL、Python、Excel、Tableau、PowerPoint。方法上接触过 A/B Testing、RFM、K-means、cohort analysis、用户分层、漏斗分析、商业分析和 PRD。\n', "Mock test case for reference only\n\nThe following is not a formal resume but a user’s casually compiled experience database containing some duplicates, colloquial, and less concise expressions. CariAgent’s task is to extract facts and condense expressions from this raw material, then combine with the job description (JD) to generate a more resume-like version.\n\nMy general direction is data analysis/product operations. I majored in Information Management and Information Systems for my undergraduate studies from September 2021 to June 2025 at East China University of Finance and Economics. GPA 3.72/4.00; I won second prize once in a data analysis competition and led the data team of the university’s business analysis association. Relevant courses related to the role include database, statistics, Python data analysis, market research, operations management, and experimental design.\n\nFrom May 2024 to September 2024, I interned as a product operation intern in Alibaba Local Life’s in-store business. The focus was not primarily coding but analyzing merchant growth funnels. We examined funnel changes from new merchant onboarding, profile completion, first order conversion, event registration to repurchase. I used SQL to query city-level data and created a weekly dashboard covering about 12 city teams. Notably, a batch of merchants showed low conversion; initially, the team assumed poor merchant quality, but I broke down the pathway and discovered many merchants stalled at profile completion and benefit comprehension, also first-week exposure was insufficient. I collaborated with product, operations, and sales teams to revise the merchant task center by adding benefit explanations and task reminder rules. In pilot cities, first-week task completion rate increased by about 16%. I also participated in the 618 event retrospective, compiling GMV, order volume, subsidy cost, ROI metrics for reference in the next promotion phase.\n\nFrom November 2023 to March 2024, I interned in Tencent Ads' business analysis group, focusing more on data analysis. I frequently used SQL and Python to clean advertiser campaign data and produced weekly industry reports. Metrics included impressions, clicks, CTR, CVR, CPA, and budget consumption. I analyzed education, gaming, and local services industries, mainly studying creative performance, campaign timing, and converting audiences. Once, I found a client’s ads had good click rates but poor conversion; after review, we found targeting was too narrow and creatives were fatigued. I made a 20+ page visualization report for business colleagues to review clients.\n\nFrom June 2023 to September 2023, I interned in ByteDance’s commercialization growth tools direction as a data product intern. The experience was diverse. I helped streamline the merchant lead management tool process from lead creation, follow-up, conversion to loss, organizing fields and statuses. I interviewed 8 sales and operations colleagues; major feedback was inconsistent lead statuses, missing follow-up records, and repeated input. Later, I participated in requirement review, drafted the initial PRD, and pushed for lead status validation and follow-up reminders. The project outcome did not have clear business numbers but reduced manual checking costs for sales.\n\nIn a school project, I analyzed user retention for a campus food delivery platform from October 2024 to December 2024 using simulated order data. I cleaned data, constructed features, and conducted cohort analysis with Python, calculating retention, repurchase, and average order value. I later classified users into frequent/essential, price-sensitive, promotion-driven, and silent churn groups, providing coupon targeting and membership benefits optimization suggestions. Finally, I created a Tableau dashboard and presented a 15-minute report in class.\n\nAnother project was an RFM user segmentation from March 2024 to May 2024 using recency, frequency, and monetary values to score user value, then clustering with K-means. This was more methodological practice; I designed a recall strategy and simulated an A/B test plan measuring click-through rate, repurchase rate, and conversion cost.\n\nIn extracurriculars, from September 2022 to June 2023, I led the university’s business analysis association data team, organizing sharing sessions on instant retail, content e-commerce, and membership operations. I also led a 5-person team conducting campus coffee consumption surveys collecting over 300 questionnaires and produced a user persona report.\n\nSkills include SQL, Python, Excel, Tableau, PowerPoint. Methodologies covered: A/B testing, RFM, K-means, cohort analysis, user segmentation, funnel analysis, business analysis, and PRD writing.")


DEMO_JD = localized('数据分析实习生\n\n岗位职责：\n1. 支持用户增长、会员运营和产品迭代相关的数据分析工作。\n2. 使用 SQL / Python 处理业务数据，搭建日常指标看板和分析报告。\n3. 参与用户分层、活动复盘、A/B 测试和转化漏斗分析。\n4. 与产品、运营和市场团队沟通，基于数据洞察提出优化建议。\n\n任职要求：\n1. 熟悉 SQL，具备 Python 或 R 数据分析经验。\n2. 理解基础统计方法，能清晰解释分析过程和结论。\n3. 有用户增长、产品运营、市场分析或商业分析项目经验优先。\n4. 具备良好的沟通能力和结构化表达能力。\n', 'Data Analyst Intern\n\nJob Responsibilities:\n1. Support data analysis related to user growth, membership operations, and product iteration.\n2. Use SQL/Python to process business data, build daily metric dashboards, and analysis reports.\n3. Participate in user segmentation, event retrospectives, A/B testing, and conversion funnel analysis.\n4. Communicate with product, operations, and marketing teams to propose optimization suggestions based on data insights.\n\nQualifications:\n1. Familiar with SQL and experienced in Python or R data analysis.\n2. Understand basic statistical methods and can clearly explain analysis processes and conclusions.\n3. Prior project experience in user growth, product operations, market analysis, or business analysis is preferred.\n4. Good communication skills and ability for structured expression.')


@st.cache_data(show_spinner=False)
def load_default_inputs(language: str) -> tuple[str, str]:
    return DEMO_EXPERIENCE.strip(), DEMO_JD.strip()


def reset_demo_session_inputs() -> None:
    default_experience, default_jd = load_default_inputs("en" if is_english() else "zh")
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

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(paragraphs)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>
    </w:sectPr>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    output = BytesIO()
    with ZipFile(output, "w") as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/document.xml", document_xml)
    return output.getvalue()


def ensure_session_defaults() -> None:
    default_experience, default_jd = load_default_inputs("en" if is_english() else "zh")
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
        raise RuntimeError(localized('解析 PDF 需要安装 pypdf：D:/Python313/python.exe -m pip install pypdf', 'PDF parsing requires pypdf. Install it with: python -m pip install pypdf')) from error
    reader = PdfReader(BytesIO(raw))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page).strip()


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
        raise RuntimeError(localized('图片解析需要接入 OCR 或视觉模型；当前版本请先粘贴图片中的文字。', 'Image parsing requires integration with OCR or vision models; currently please paste text from the image first.'))
    raise RuntimeError((f"Unsupported file type: {suffix or uploaded_file.name}" if is_english() else f"暂不支持的文件类型：{suffix or uploaded_file.name}"))


def progress_writer(message: str) -> None:
    st.session_state.progress_log.append(message)


def visible_progress_writer(message: str) -> None:
    progress_writer(message)


def run_timed_step(label: str, fn):
    start = time.perf_counter()
    visible_progress_writer((f"{label} start" if is_english() else f"{label} 开始"))
    result = fn()
    elapsed = time.perf_counter() - start
    visible_progress_writer((f"{label} finished · {elapsed:.1f}s" if is_english() else f"{label} 完成 · {elapsed:.1f}s"))
    return result


def page_title_for_step(step_key: str) -> str:
    return next((english for key, _, english in STEPS if key == step_key), "Workspace")


def status_for_step(step_key: str) -> str:
    state = st.session_state.workflow_state
    if step_key == "experience":
        return localized('经历库已就绪', 'Experience database ready') if st.session_state.experience_text else localized('等待经历库', 'Waiting for experience database')
    if step_key == "jd":
        return localized('JD 已分析', 'JD analyzed') if state and state.jd_analysis else localized('等待分析 JD', 'Waiting for JD analysis')
    if step_key == "match":
        return localized('匹配摘要已生成', 'Match summary generated') if state and state.fit_verdict else localized('等待匹配', 'Waiting for matching')
    if step_key == "followup":
        if state and state.followup_plan:
            questions = get_prioritized_questions(state)
            if questions:
                handled = min(len(answered_question_ids(state)), len(questions))
                if handled >= len(questions):
                    return localized('追问已处理', 'Follow-up handled')
                return (f"AI Follow-up {handled}/{len(questions)}" if is_english() else f"AI 追问 {handled}/{len(questions)}")
            return localized('AI 追问进行中', 'AI Follow-up in progress')
        return localized('等待追问', 'Waiting for follow-up')
    if step_key == "resume":
        return localized('草稿已生成', 'Draft generated') if state and state.resume_markdown else localized('等待生成草稿', 'Waiting for draft generation')
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
        f"""
        <div class="ca-topbar">
            <div class="ca-brand">
                <span class="ca-logo">C</span>
                <span>CariAgent</span>
            </div>
            <div class="ca-top-title">{safe_text(page_title_for_step(step))}</div>
            <div class="ca-status">
                <span class="ca-status-dot"></span>{safe_text(status_for_step(step))}
            </div>
        </div>
        """,
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
        and st.session_state.get("experience_sections_cache_text") == st.session_state.experience_text
    ):
        experience_sections = st.session_state.experience_sections_cache
    labels = {
        "profile": localized('个人简介', 'Personal Summary'),
        "education": localized('教育经历', 'Education'),
        "work_experience": localized('工作经历', 'Work Experience'),
        "internship_experience": localized('实习经历', 'Internship Experience'),
        "project_experience": localized('项目经历', 'Project Experience'),
        "campus_experience": localized('校园经历', 'Campus Experience'),
        "club_experience": localized('社团活动', 'Club Activities'),
        "volunteer_experience": localized('志愿服务', 'Volunteer Service'),
        "awards": localized('获奖经历', 'Awards'),
        "skills": localized('技能', 'Skills'),
        "certifications": localized('证书认证', 'Certifications'),
        "basic_information": localized('基本信息', 'Basic Information'),
        "hobbies": localized('个人爱好', 'Personal Interests'),
        "other": localized('其他', 'Others'),
    }
    display_order = [
        localized('个人简介', 'Personal Summary'),
        localized('基本信息', 'Basic Information'),
        localized('教育经历', 'Education'),
        localized('工作经历', 'Work Experience'),
        localized('实习经历', 'Internship Experience'),
        localized('项目经历', 'Project Experience'),
        localized('校园经历', 'Campus Experience'),
        localized('社团活动', 'Club Activities'),
        localized('志愿服务', 'Volunteer Service'),
        localized('获奖经历', 'Awards'),
        localized('技能', 'Skills'),
        localized('证书认证', 'Certifications'),
        localized('个人爱好', 'Personal Interests'),
        localized('其他', 'Others'),
    ]
    counts = {label: 0 for label in display_order}
    if not experience_sections:
        return counts
    for section in experience_sections.get("experience_sections", []):
        key = section.get("section_key", "")
        label = labels.get(key, section.get("section_name") or key or localized('其他', 'Others'))
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
        questions,
        key=lambda item: item.get("question_priority_score", 0),
        reverse=True,
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
    state: simple_mvp.WorkflowState,
    questions: list[dict],
) -> tuple[dict | None, int]:
    answered_ids = answered_question_ids(state)
    for index, question in enumerate(questions, start=1):
        if question.get("id") not in answered_ids:
            return question, index
    return None, len(questions)


def merge_reviewed_answer(
    state: simple_mvp.WorkflowState,
    reviewed_item: dict,
    updated_notes: list[str] | None,
    stop_reason: str,
) -> None:
    previous_items = reviewed_answer_items(state)
    previous_notes = []
    if state.reviewed_answers:
        previous_notes = state.reviewed_answers.get("updated_experience_notes", []) or []

    state.reviewed_answers = {
        "reviewed_answers": [*previous_items, reviewed_item],
        "updated_experience_notes": [*previous_notes, *(updated_notes or [])],
        "stop_reason": stop_reason,
        "estimated_readiness_score_after_followups": round(
            state.readiness_score.get("overall_readiness_score", 0),
            3,
        ),
    }


def set_reviewed_answers_from_question(
    client,
    state: simple_mvp.WorkflowState,
    question: dict,
    answer_text: str,
) -> None:
    normalized = simple_mvp.normalize_user_control_text(answer_text)
    if normalized in simple_mvp.SKIP_WORDS or not answer_text.strip():
        reviewed_item = simple_mvp.build_pass_review_item(
            question,
            "User skipped this question in the Streamlit demo.",
        )
        merge_reviewed_answer(
            state,
            reviewed_item,
            [],
            "streamlit_user_skipped_followup",
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
        {
            "question": question,
            "review": reviewed_item,
            "source": "streamlit_demo",
        }
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
        progress_writer(localized('复用缓存：JD 拆解结果', 'Reuse cache: JD breakdown results'))
        return

    with st.status(localized('CariAgent 正在拆解当前 JD...', 'CariAgent is breaking down the current JD...'), expanded=True) as status:
        status.update(label=localized('CariAgent 正在准备运行环境...', 'CariAgent is preparing the running environment...'))
        st.write(localized('1/3 准备运行环境', '1/3 Preparing running environment'))
        client = run_timed_step(localized('初始化 OpenAI client', 'Initializing OpenAI client'), simple_mvp.initialize_workflow_runtime)
        status.update(label=localized('CariAgent 正在读取输入...', 'CariAgent is reading input...'))
        st.write(localized('2/3 读取经历库与目标 JD', '2/3 Reading experience database and target JD'))
        state = run_timed_step(
            localized('读取经历库与 JD', 'Reading experience database and JD'),
            lambda: simple_mvp.create_workflow_state(
                st.session_state.experience_text,
                st.session_state.jd_text,
            ),
        )
        if (
            st.session_state.experience_sections_cache
            and st.session_state.experience_sections_cache_text == st.session_state.experience_text
        ):
            state.experience_sections = st.session_state.experience_sections_cache

        status.update(label=localized('CariAgent 正在拆解目标 JD...', 'CariAgent is breaking down the target JD...'))
        st.write(localized('3/3 拆解 JD 要求', '3/3 Decomposing JD requirements'))
        state = run_timed_step(
            localized('JD 结构化拆解', 'JD structured breakdown'),
            lambda: simple_mvp.run_jd_analysis_workflow(client, state),
        )
        st.session_state.workflow_state = state
        st.session_state.openai_client = client
        st.session_state.analysis_done = True
        st.session_state.workflow_cache[cache_key] = state
        status.update(label=localized('JD 拆解完成', 'JD breakdown completed'), state="complete")


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
        progress_writer(localized('复用缓存：匹配摘要', 'Reuse cache: match summary'))
        return

    with st.status(localized('CariAgent 正在检索证据并生成匹配摘要...', 'CariAgent is retrieving evidence and generating the match summary...'), expanded=True) as status:
        status.update(label=localized('CariAgent 正在检索相关经历证据...', 'CariAgent is retrieving relevant experience evidence...'))
        st.write(localized('1/4 检索经历证据', '1/4 Retrieving experience evidence'))
        state = run_timed_step(
            localized('经历库分段 + RAG 检索', 'Experience database segmentation + RAG retrieval'),
            lambda: simple_mvp.run_retrieval_workflow(
                client,
                state,
                progress_callback=visible_progress_writer,
            ),
        )
        status.update(label=localized('CariAgent 正在整理证据并判断覆盖等级...', 'CariAgent is organizing evidence and judging coverage levels...'))
        st.write(localized('2/4 整理 evidence atoms 并判断覆盖等级', '2/4 Organizing evidence atoms and judging coverage level'))
        state = run_timed_step(
            localized('Atoms 抽取 + 匹配 + Fit 判断', 'Atoms extraction + matching + Fit judgment'),
            lambda: simple_mvp.run_matching_workflow(
                client,
                state,
                progress_callback=visible_progress_writer,
            ),
        )

        status.update(label=localized('CariAgent 正在生成追问计划...', 'CariAgent is generating follow-up plan...'))
        st.write(localized('3/4 生成追问计划', '3/4 Generate follow-up plan'))
        state = run_timed_step(
            localized('追问计划生成', 'Follow-up plan generation'),
            lambda: simple_mvp.run_followup_planning_workflow(state),
        )
        st.write(localized('4/4 保存匹配摘要', '4/4 Save match summary'))

        st.session_state.workflow_state = state
        st.session_state.openai_client = client
        if state.experience_sections:
            st.session_state.experience_sections_cache = state.experience_sections
            st.session_state.experience_sections_cache_text = state.experience_text
        st.session_state.workflow_cache[cache_key] = state
        status.update(label=localized('匹配摘要已生成', 'Match summary generated'), state="complete")


def render_page_heading(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="ca-page">
            <div class="ca-page-title">{safe_text(title)}</div>
            <div class="ca-page-subtitle">{safe_text(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_experience_page() -> None:
    render_page_heading(
        localized('经历库', 'Experience Database'),
        localized('维护你的真实职业经历。CariAgent 会从这里提取证据来匹配每一个岗位。', 'Maintain your authentic professional experience. CariAgent will extract evidence from here to match every role.'),
    )
    counts = get_section_counts()
    st.markdown(
        "".join(
            f'<span class="ca-pill">{safe_text(name)} {count if count else ""}</span>'
            for name, count in counts.items()
        ),
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        localized('导入简历 / 文档', 'Import Resume/Document'),
        type=["txt", "md", "docx", "pdf", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            uploaded_text = decode_uploaded_file(uploaded)
            if uploaded_text:
                st.session_state.experience_text = uploaded_text
                st.session_state.workflow_state = None
                st.success(localized('已读取上传内容，可继续编辑。', 'Uploaded content read, can continue editing.'))
        except Exception as error:
            st.warning(str(error))

    st.text_area(
        localized('纯文本编辑（Markdown 格式）', 'Plain Text Editing (Markdown Format)'),
        key="experience_text",
        height=430,
    )
    st.markdown(
        (f"""
        <div class="ca-soft-card">
            <span class="ca-success">✓ Experience database ready</span><br>
            <span class="ca-muted">Evidence Source · {len(st.session_state.experience_text)} characters</span>
        </div>
        """ if is_english() else f"""
        <div class="ca-soft-card">
            <span class="ca-success">✓ 经历库已就绪</span><br>
            <span class="ca-muted">Evidence Source · {len(st.session_state.experience_text)} 字符</span>
        </div>
        """),
        unsafe_allow_html=True,
    )
    _, right = st.columns([3, 1])
    if right.button(localized('继续填写目标 JD  →', 'Continue filling in the target JD  →'), type="primary", use_container_width=True):
        st.session_state.current_step = "jd"
        st.rerun()


def render_jd_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        localized('目标 JD', 'Target JD'),
        localized('粘贴一个你感兴趣的岗位描述，CariAgent 将提炼核心要求。', 'Paste a job description you are interested in, CariAgent will extract the core requirements.'),
    )

    if state and state.jd_analysis:
        jd = state.jd_analysis
        st.markdown(
            (f"""
            <div class="ca-card">
                <div class="ca-label">Target Role</div>
                <h2>{safe_text(jd.get("role_title", "Target Role"))}</h2>
                <p>{safe_text(jd.get("job_goal", ""))}</p>
            </div>
            """ if is_english() else f"""
            <div class="ca-card">
                <div class="ca-label">目标岗位</div>
                <h2>{safe_text(jd.get("role_title", "目标岗位"))}</h2>
                <p>{safe_text(jd.get("job_goal", ""))}</p>
            </div>
            """),
            unsafe_allow_html=True,
        )
        st.markdown(localized('#### 核心要求', '#### Core Requirements'))
        for item in (jd.get("core_responsibilities", []) or [])[:5]:
            st.write(f"- {item}")
        keywords = jd.get("keywords_to_mirror", []) or []
        if keywords:
            st.markdown(localized('#### 关键词', '#### Keywords'))
            st.markdown(
                "".join(f'<span class="ca-pill">{safe_text(item)}</span>' for item in keywords[:12]),
                unsafe_allow_html=True,
            )
        with st.expander(localized('查看完整 JD 解析详情', 'View full JD parsing details'), expanded=False):
            st.json(jd, expanded=False)
        left, right = st.columns([1, 1])
        if left.button(localized('← 重新粘贴 JD', '← Paste JD again')):
            st.session_state.workflow_state = None
            st.rerun()
        if right.button(localized('查看匹配摘要  →', 'View Match Summary  →'), type="primary"):
            if not state.fit_verdict:
                try:
                    run_match_from_session()
                except Exception as error:
                    st.error((f"Match analysis failed: {type(error).__name__}: {error}" if is_english() else f"匹配分析失败：{type(error).__name__}: {error}"))
                    return
            st.session_state.current_step = "match"
            st.rerun()
        return

    uploaded = st.file_uploader(
        localized('上传 JD 文件', 'Upload JD File'),
        type=["txt", "md", "docx", "pdf", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            uploaded_text = decode_uploaded_file(uploaded)
            if uploaded_text:
                st.session_state.jd_text = uploaded_text
                st.success(localized('已读取上传 JD，可继续编辑。', 'Uploaded JD read, can continue editing.'))
        except Exception as error:
            st.warning(str(error))

    st.text_area(localized('岗位描述（JD）', 'Job Description (JD)'), key="jd_text", height=420)
    st.caption((f"{len(st.session_state.jd_text)} characters" if is_english() else f"{len(st.session_state.jd_text)} 字符"))
    _, right = st.columns([3, 1])
    if right.button(localized('分析 JD', 'Analyze JD'), type="primary", use_container_width=True):
        try:
            run_jd_parse_from_session()
            st.rerun()
        except Exception as error:
            st.error((f"Run failed: {type(error).__name__}: {error}" if is_english() else f"运行失败：{type(error).__name__}: {error}"))


def score_to_display(score) -> tuple[int, float]:
    if not isinstance(score, (int, float)):
        return 0, 0.0
    percent = int(round(score * 100))
    return percent, max(0.0, min(1.0, float(score)))


def short_items(items: list[str], limit: int = 3) -> list[str]:
    return [str(item) for item in (items or [])[:limit]]


def render_summary_card(title: str, items: list[str], icon_class: str, icon: str) -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        display_items = short_items(items, 3)
        if not display_items:
            st.caption(localized('暂无可展示条目', 'No entries available for display'))
            return
        for item in display_items:
            st.markdown(
                f'<div class="ca-summary-item"><span class="{icon_class}">{icon}</span>'
                f'<span class="ca-summary-item-text">{safe_text(item)}</span></div>',
                unsafe_allow_html=True,
            )


def render_match_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        localized('匹配摘要', 'Match Summary'),
        localized('基于你的经历库与目标 JD 的 RAG 检索结果。', 'Based on your experience database and the RAG retrieval results of the target JD.'),
    )
    if not state or not state.fit_verdict:
        st.info(localized('还没有匹配摘要。请先在目标 JD 页面运行分析。', 'No match summary yet. Please run analysis first on the target JD page.'))
        c1, c2 = st.columns([1, 1])
        if c1.button(localized('去填写目标 JD', 'Go fill target JD')):
            st.session_state.current_step = "jd"
            st.rerun()
        if state and state.jd_analysis and c2.button(localized('开始匹配分析', 'Start Matching Analysis'), type="primary"):
            try:
                run_match_from_session()
                st.rerun()
            except Exception as error:
                st.error((f"Match analysis failed: {type(error).__name__}: {error}" if is_english() else f"匹配分析失败：{type(error).__name__}: {error}"))
        return

    percent, progress = score_to_display(state.readiness_score.get("overall_readiness_score", 0))
    col_score, col_fit = st.columns(2)
    with col_score:
        st.markdown(
            (f"""
            <div class="ca-card">
                <div class="ca-label">Readiness Score</div>
                <span class="ca-big-score">{percent}</span><span class="ca-score-denom"> /100</span>
                <p class="ca-muted">Based on RAG retrieval experience coverage</p>
            </div>
            """ if is_english() else f"""
            <div class="ca-card">
                <div class="ca-label">Readiness Score</div>
                <span class="ca-big-score">{percent}</span><span class="ca-score-denom"> /100</span>
                <p class="ca-muted">基于 RAG 检索的经历覆盖率</p>
            </div>
            """),
            unsafe_allow_html=True,
        )
        render_score_bar(progress)
    with col_fit:
        st.markdown(
            f"""
            <div class="ca-card">
                <div class="ca-label">Fit Verdict</div>
                <span class="ca-pill">{safe_text(fit_level_label(state.fit_verdict.get("fit_level", "-")))}</span>
                <p>{safe_text(state.fit_verdict.get("fit_summary", ""))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col_match, col_gap = st.columns(2)
    with col_match:
        render_summary_card(localized('TOP 匹配', 'TOP Matches'), state.fit_verdict.get("major_matches", []), "ca-check", "✓")
    with col_gap:
        render_summary_card(localized('TOP 缺口', 'TOP Gaps'), state.fit_verdict.get("major_gaps", []), "ca-warn", "⚠")

    with st.expander(localized('查看 RAG Evidence', 'View RAG Evidence'), expanded=False):
        chunks = state.retrieval_result.get("selected_chunks", [])
        st.caption(f"Selected evidence chunks: {len(chunks)}")
        for index, chunk in enumerate(chunks[:20], start=1):
            with st.expander((f"Evidence {index}: {chunk.get('experience_title', 'Unrecognized Source')}" if is_english() else f"Evidence {index}: {chunk.get('experience_title', '未识别来源')}")):
                st.caption(chunk.get("section_group", ""))
                st.write(chunk.get("text", ""))
    with st.expander(localized('查看匹配经历详情', 'View Matching Experience Details'), expanded=False):
        st.json(state.match_result, expanded=False)
    with st.expander(localized('查看 Workflow Trace', 'View Workflow Trace'), expanded=False):
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
                elapsed_text = f" · {elapsed:.1f}s" if isinstance(elapsed, (int, float)) else ""
                usage = call.get("usage") or {}
                tokens = usage.get("total_tokens")
                token_text = f" · {tokens} tokens" if tokens else ""
                st.write(
                    f"{call.get('call_name', '-')}: {call.get('model', '-')}"
                    f"{elapsed_text}{token_text}"
                )

    left, right = st.columns([1, 1])
    if left.button(localized('← 返回目标 JD', '← Return to Target JD')):
        st.session_state.current_step = "jd"
        st.rerun()
    if right.button(localized('继续 AI 追问  →', 'Continue AI Follow-up  →'), type="primary"):
        st.session_state.current_step = "followup"
        st.rerun()


def generate_resume_from_state(state: simple_mvp.WorkflowState) -> None:
    client = st.session_state.openai_client or simple_mvp.initialize_workflow_runtime()
    with st.spinner(localized('正在生成简历草稿...', 'Generating resume draft...')):
        state = simple_mvp.run_resume_generation_workflow(client, state)
        simple_mvp.save_workflow_trace(state)
        st.session_state.workflow_state = state
        st.session_state.resume_done = True
    st.session_state.current_step = "resume"
    st.rerun()


def render_followup_page() -> None:
    state = st.session_state.workflow_state
    render_page_heading(
        localized('AI 追问', 'AI Follow-up'),
        localized('优先处理最有价值的证据缺口。', 'Prioritize addressing the most valuable evidence gaps.'),
    )
    if not state:
        st.info(localized('请先运行 JD 分析。', 'Please run JD analysis first.'))
        return
    st.markdown(
        localized('<div class="ca-footnote">* 本次回答只用于当前简历生成。</div>', '<div class="ca-footnote">* This answer is only for the current resume generation.</div>'),
        unsafe_allow_html=True,
    )

    questions = get_prioritized_questions(state)
    question, question_index = next_unanswered_question(state, questions)
    if question:
        question_count = len(questions)
        st.markdown(
            (f"""
            <div class="ca-card">
                <div class="ca-label">CariAgent Follow-up · {question_index} / {question_count}</div>
                <div class="ca-question-text">{safe_text(question.get("question", ""))}</div>
            </div>
            """ if is_english() else f"""
            <div class="ca-card">
                <div class="ca-label">CariAgent 追问 · {question_index} / {question_count}</div>
                <div class="ca-question-text">{safe_text(question.get("question", ""))}</div>
            </div>
            """),
            unsafe_allow_html=True,
        )
        with st.expander(localized('为什么要提问这个问题？', 'Why ask this question?'), expanded=False):
            col_reason, col_exp = st.columns(2)
            with col_reason:
                st.caption(localized('提问原因', 'Reason for question'))
                st.write(question.get("why_ask", ""))
                st.caption(localized('缺失证据类型', 'Missing evidence type'))
                st.write(question.get("target_requirement", ""))
            with col_exp:
                st.caption(localized('关联经历', 'Related Experience'))
                st.write(question.get("related_experience_name", ""))
    else:
        if questions:
            st.success(localized('本轮候选追问已处理完，可以生成简历草稿。', 'This round of candidate follow-up questions completed, resume draft can be generated.'))
        else:
            st.info(localized('当前没有候选追问，可以直接生成简历草稿。', 'No candidate follow-up questions currently, can generate resume draft directly.'))

    if question:
        answer_text = st.text_area(
            localized('你的回答', 'Your Answer'),
            key=f"followup_answer_{question.get('id', question_index)}",
            height=180,
            placeholder=localized('在这里输入你的回答，尽量包含具体细节、数据或决策过程。', 'Enter your answer here, try to include concrete details, data, or decision processes.'),
        )
        skip_col, submit_col, resume_col = st.columns([1, 1, 1])
        with skip_col:
            if st.button(localized('跳过', 'Skip'), key="followup_skip"):
                set_reviewed_answers_from_question(
                    st.session_state.openai_client,
                    state,
                    question,
                    "",
                )
                st.rerun()
        with submit_col:
            if st.button(localized('提交回答', 'Submit Answer'), key="followup_submit", type="primary"):
                client = st.session_state.openai_client or simple_mvp.initialize_workflow_runtime()
                try:
                    set_reviewed_answers_from_question(client, state, question, answer_text)
                    st.session_state.followup_done = True
                    st.rerun()
                except Exception as error:
                    st.error((f"Follow-up answer interpretation failed: {type(error).__name__}: {error}" if is_english() else f"追问回答理解失败：{type(error).__name__}: {error}"))
        with resume_col:
            if st.button(localized('生成简历草稿  →', 'Generate Resume Draft  →'), key="followup_generate_inline", type="primary"):
                try:
                    generate_resume_from_state(state)
                except Exception as error:
                    st.error((f"Resume generation failed: {type(error).__name__}: {error}" if is_english() else f"简历生成失败：{type(error).__name__}: {error}"))
    elif state.reviewed_answers:
        items = reviewed_answer_items(state)
        info = items[-1] if items else {}
        usable = "；".join(info.get("usable_information", []) or []) or localized('已记录本轮回答。', 'This round of answers recorded.')
        st.markdown(
            (f"""
            <div class="ca-card">
                <span class="ca-success">✓ Processed {len(items)} follow-up questions</span>
                <p>{safe_text(usable)}</p>
            </div>
            """ if is_english() else f"""
            <div class="ca-card">
                <span class="ca-success">✓ 已处理 {len(items)} 个追问</span>
                <p>{safe_text(usable)}</p>
            </div>
            """),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="ca-followup-actions-spacer"></div>', unsafe_allow_html=True)
    nav_col, _, resume_col = st.columns([1, 1, 1])
    with nav_col:
        if st.button(localized('← 返回匹配摘要', '← Return to Match Summary'), key="followup_back"):
            st.session_state.current_step = "match"
            st.rerun()
    if not question:
        with resume_col:
            if st.button(localized('生成简历草稿  →', 'Generate Resume Draft  →'), key="followup_generate_bottom", type="primary"):
                try:
                    generate_resume_from_state(state)
                except Exception as error:
                    st.error((f"Resume generation failed: {type(error).__name__}: {error}" if is_english() else f"简历生成失败：{type(error).__name__}: {error}"))


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
        localized('简历草稿', 'Resume Draft'),
        localized('基于经历库 + RAG 检索 + AI 追问回答生成。', 'Generated based on experience database + RAG retrieval + AI follow-up answers.'),
    )
    if not state:
        st.info(localized('请先运行 JD 分析。', 'Please run JD analysis first.'))
        return
    if not state.resume_markdown:
        st.info(localized('简历草稿还没有生成。', 'Resume draft has not been generated yet.'))
        if st.button(localized('去 AI 追问 / 生成草稿', 'Go to AI Follow-up / Generate Draft')):
            st.session_state.current_step = "followup"
            st.rerun()
        return

    left, right = st.columns([2.2, 1])
    with left:
        with st.container(border=True):
            st.markdown(state.resume_markdown)
    with right:
        with st.container(border=True):
            st.markdown(localized('#### 使用的经历', '#### Experiences Used'))
            for name in experiences_used(state):
                st.write(f"✓ {name}")
            st.markdown("---")
            st.markdown(localized('#### 最强证据', '#### Strongest Evidence'))
            for item in short_items(state.fit_verdict.get("major_matches", []), 2):
                st.write(f"- {item}")

    md_col, docx_col = st.columns([1, 1])
    with md_col:
        st.download_button(
            localized('下载 Markdown', 'Download Markdown'),
            data=state.resume_markdown,
            file_name="cariagent_resume_en.md" if is_english() else "cariagent_resume_draft.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with docx_col:
        st.download_button(
            localized('下载 Word (.docx)', 'Download Word (.docx)'),
            data=markdown_to_docx_bytes(state.resume_markdown),
            file_name="cariagent_resume_en.docx" if is_english() else "cariagent_resume_draft.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    if state.improvement_suggestions_markdown:
        with st.expander(localized('简历优化建议（不包含在下载文件中）', 'Resume Improvement Suggestions (Not Included in Downloaded File)'), expanded=True):
            st.markdown(state.improvement_suggestions_markdown)


def display_last_run() -> None:
    state = st.session_state.get("workflow_state")
    if not state or not any([state.fit_verdict, state.readiness_score, state.resume_markdown]):
        st.info(localized('当前会话还没有可展示的历史运行。', 'No historical runs available for display in the current session.'))
        return
    score = "-"
    if isinstance(state.readiness_score.get("overall_readiness_score"), (int, float)):
        score = f"{state.readiness_score.get('overall_readiness_score'):.3f}"
    fit_level = fit_level_label((state.fit_verdict or {}).get("fit_level", "-"))
    recommendation = (state.fit_verdict or {}).get("recommendation", "-")
    st.markdown(
        (f"""
        <div class="ca-history-row">
            <div>
                <div class="ca-history-title">Current Session</div>
                <div class="ca-history-meta">Readiness {safe_text(score)} · {safe_text(fit_level)}</div>
            </div>
            <div class="ca-history-meta">{safe_text(recommendation)}</div>
        </div>
        """ if is_english() else f"""
        <div class="ca-history-row">
            <div>
                <div class="ca-history-title">当前会话</div>
                <div class="ca-history-meta">Readiness {safe_text(score)} · {safe_text(fit_level)}</div>
            </div>
            <div class="ca-history-meta">{safe_text(recommendation)}</div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    with st.expander(localized('查看简历草稿', 'View Resume Draft'), expanded=False):
        st.markdown(state.resume_markdown or localized('暂无简历输出', 'No resume output yet'))


def display_sidebar_experience_bank() -> None:
    try:
        counts = get_section_counts()
    except Exception as error:
        st.caption((f"Experience database summary temporarily unavailable: {type(error).__name__}" if is_english() else f"经历库摘要暂时不可用：{type(error).__name__}"))
        counts = {}
    st.caption((f"Current experience database: {len(st.session_state.experience_text)} characters" if is_english() else f"当前经历库：{len(st.session_state.experience_text)} 字符"))
    visible_counts = [f"{name} {count}" for name, count in counts.items() if count]
    if visible_counts:
        st.caption(" · ".join(visible_counts))
    else:
        st.caption(localized('尚未完成结构化解析，当前保存的是原始文本。', 'Structured parsing not yet completed, current saved text is raw.'))
    if st.button(localized('打开经历库', 'Open Experience Database'), use_container_width=True):
        st.session_state.current_step = "experience"
        st.rerun()


def main() -> None:
    ensure_session_defaults()
    render_topbar()
    render_step_nav()

    st.sidebar.title("CariAgent")
    st.sidebar.write("OpenAI API Key")
    if os.getenv("OPENAI_API_KEY"):
        st.sidebar.success(localized('已配置', 'Configured'))
    else:
        st.sidebar.warning(localized('未配置', 'Not Configured'))
    st.sidebar.caption(localized('公开部署时请使用 Streamlit Secrets。', 'Use Streamlit Secrets for public deployment.'))
    with st.sidebar.expander(localized('个人经历库', 'Personal Experience Database'), expanded=True):
        display_sidebar_experience_bank()
    with st.sidebar.expander(localized('历史运行', 'History'), expanded=False):
        display_last_run()
        if st.button(localized('重置当前会话', 'Reset Current Session'), use_container_width=True):
            reset_demo_session_inputs()
            st.session_state.history_clear_message = localized('已重置当前会话，并恢复虚拟测试用例。本地 outputs 文件不会被删除。', 'Current session reset, and virtual test cases restored. Local outputs folder will not be deleted.')
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
