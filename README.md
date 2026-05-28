# CariAgent

CariAgent 是一个本地运行的 JD 驱动型简历重组 Agent。

核心目标：

> 从用户经历库中召回能证明目标 JD 的真实证据，并生成更匹配岗位的简历草稿。

当前项目用于作品集展示，重点是 RAG、workflow、追问机制和结构化 AI 产品设计。

---

## 当前工作流

```text
1. 读取 exp_bank
2. 读取 JD
3. 拆解 JD
4. 将经历库划分为 sections
5. 按 section 做 RAG 检索
6. 将 selected chunks 结构化为 experience atoms
7. 匹配 JD 与 atoms
8. 基于缺口生成追问
9. 理解用户补充回答
10. 生成 Markdown 简历草稿
```

---

## 核心原则

- 原始经历、RAG selected chunks、用户追问回答是事实来源。
- JD analysis、atoms、match result、score 是标注和判断，不是新的事实。
- 每条证据必须保留 provenance，防止跨经历借证据。
- Follow-up 只用于本轮生成，不写回底层 exp_bank。
- 当前优先保留原始信息，不以极限 token 节省为目标。

---

## 主要文件

```text
core/simple_mvp.py              主流程脚本
core/retrieval.py               RAG 检索逻辑
prompts/system_cariagent.txt    系统原则
prompts/task_*.txt              各步骤 prompt
data/exp_bank.txt               用户经历库
data/sample_jd.txt              目标 JD
outputs/*.json                  中间产物
outputs/result.md               最终输出
```

项目文档：

```text
cari_agent_prd_v_0_2.md
cari_agent_rag_development_log.md
workflow_design_notes.md
```
## 模型配置

默认模型在 `core/simple_mvp.py` 中通过环境变量控制：

```powershell
$env:OPENAI_MODEL="gpt-4.1"
```

也可以按步骤覆盖：

```powershell
$env:OPENAI_MODEL_S3="gpt-4.1"
$env:OPENAI_MODEL_S4="gpt-4.1"
$env:OPENAI_MODEL_S8="gpt-4.1"
```

---

## 当前状态

RAG 主逻辑已阶段性收束。
当前已开始 workflow 重构：

- `WorkflowState` 承接单次运行状态
- 主流程已拆为可复用 workflow functions
- CLI 入口仍保留：`python core/simple_mvp.py`
- 每次运行会生成 `outputs/workflow_trace.md`

下一阶段重点：

1. 设计网页 API；
2. 将 follow-up 改造成网页交互；
3. 增加运行状态展示；
4. 稳定 Step 8 输出格式；
5. 再评估是否引入 LangGraph。
