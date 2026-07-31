"""All LLM prompt templates used by the application."""

import json

from .models import Paper

RELATED_BATCH_PROMPT = """\
你是具身智能与机器人学习方向的高召回学术论文筛选器。只根据标题、摘要和研究关注范围，
逐篇判断下面这批论文。不要使用作者、机构、引用量或外部知识补充论文内容。

研究关注范围：
{criteria}

判断标签：
- related：论文的主要问题、核心方法或关键实验直接推进关注方向。
- possible：可能相关，或使用了新颖/陌生术语而无法排除；为保护 OOD 论文，疑似相关时选此项。
- unrelated：核心问题明确不属于关注方向。

判断规则：
- 优先识别 VLA、WAM/world model、humanoid/whole-body control、motion generation、
  dexterous hand 和 loco-manipulation，也要接受未列出的新范式和近义表达。
- 区分机器人感知—决策—行动闭环与纯语言、自然视频、人物动画、自动驾驶预测或纯 3D 感知。
- 仅在引言或应用展望中提到 embodied/robot 不足以判为 related。
- 不因 SOTA、模型规模或展示效果放宽相关性，但不要把术语陌生当作无关。

论文列表（JSON）：
{papers}

必须为每个输入 ID 输出且只输出一次。仅输出合法 JSON，不要 Markdown 或解释：
{{"results":[{{"id":"2601.00001","relevance":"related"}}]}}
"""

RECOMMENDATION_PROMPT = """\
你是严谨的具身智能与机器人学习论文推荐编辑。请横向比较候选论文，从中选择真正值得今天推荐的论文。
最多选择 {limit} 篇；质量不足时可以少选或返回空列表，禁止为了凑数而入选。

研究关注范围：
{criteria}

入选准则：
- 核心学习、控制或系统方法具有实质新意，而非只替换骨干、扩大数据或拼接已有模块。
- 摘要能提供机器人动作、物理交互、闭环控制或可信物理仿真的直接证据。
- 优先考虑强基线、消融、跨任务/场景/本体泛化、sim-to-real、实时性或真实部署价值。
- possible/OOD 论文与其他论文平等比较，不能仅因术语陌生而拒绝。
- 不得推断摘要未说明的真实机器人实验、统计结果、作者背景、代码开放或 SOTA 可信度。

候选论文（JSON）：
{papers}

每篇入选论文生成一句不超过 60 个中文字符的中性摘要，只概括标题和摘要明确陈述的内容，
不要写“值得关注”“潜力巨大”等评价。仅输出合法 JSON，不要 Markdown、理由或额外字段：
{{"recommendations":[{{"id":"2601.00001","summary":"论文提出……并在……任务上进行验证。"}}]}}
"""

READING_CHUNK_PROMPT = """\
请从下面的论文全文片段提取精读笔记。必须忠于原文；未出现的信息不要推断。
面向具身智能研究，重点提取：
- 任务定义、机器人本体、观测/动作空间、传感器、控制频率与软硬件系统；
- 模型架构、world/action model、策略或控制层级、损失函数、训练算法与推理流程；
- 数据来源/规模/组成，仿真与真实数据比例，预训练、后训练和 sim-to-real 方法；
- 真实机器人或仿真实验、基线、指标、消融、泛化、鲁棒性、失败案例和安全约束；
- 局限、复现所需超参数、计算资源、硬件细节、代码/数据/模型开放情况。
这是全文的第 {chunk_index}/{chunk_count} 个片段。

论文标题：{title}
全文片段：
{chunk}

直接输出中文笔记，保留必要的英文方法名、数据集名和符号。
"""

READING_SYNTHESIS_PROMPT = """\
请基于下面的论文材料生成 1500-2500 中文字符的简版精读。
必须客观、来源可追溯，不得添加材料中没有的结论。缺失信息明确写“论文材料未说明”。
不要把仿真结果表述为真实机器人结果，也不要把 open-loop/offline 指标表述为闭环执行能力。

论文标题：{title}
作者：{authors}
原始摘要：{abstract}
材料来源：{source_label}

论文材料：
{material}

使用以下 Markdown 结构：
### 一句话摘要
### 任务与具身设定
### 核心贡献与方法
### 数据与训练
### 实验、泛化与真实部署
### 局限与适用边界
### 复现性
"""


def _paper_payload(paper: Paper) -> dict[str, str]:
    return {
        "id": paper["id"],
        "title": paper["title"],
        "abstract": paper["abstract"],
    }


def related_batch_prompt(papers: list[Paper], criteria: str) -> str:
    return RELATED_BATCH_PROMPT.format(
        criteria=criteria,
        papers=json.dumps(
            [_paper_payload(paper) for paper in papers],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )


def recommendation_prompt(
    papers: list[Paper],
    criteria: str,
    *,
    limit: int,
) -> str:
    return RECOMMENDATION_PROMPT.format(
        criteria=criteria,
        limit=limit,
        papers=json.dumps(
            [_paper_payload(paper) for paper in papers],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )


def reading_chunk_prompt(
    title: str,
    chunk: str,
    chunk_index: int,
    chunk_count: int,
) -> str:
    return READING_CHUNK_PROMPT.format(
        title=title,
        chunk=chunk,
        chunk_index=chunk_index,
        chunk_count=chunk_count,
    )


def reading_synthesis_prompt(
    *,
    title: str,
    authors: tuple[str, ...],
    abstract: str,
    material: str,
    source_label: str,
) -> str:
    return READING_SYNTHESIS_PROMPT.format(
        title=title,
        authors=", ".join(authors) or "Unknown",
        abstract=abstract,
        material=material,
        source_label=source_label,
    )
