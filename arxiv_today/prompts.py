"""All LLM prompt templates used by the application."""

RELATED_PROMPT = """\
你是学术论文相关性筛选器。只根据给出的标题、摘要和研究关注范围判断相关性。
不要使用作者、机构、引用量或外部知识补充论文内容。

标题：{title}
摘要：{abstract}

研究关注范围：
{criteria}

仅输出合法 JSON，不要输出 Markdown 或解释：
{{"related": true}}
"""

QUALITY_PROMPT = """\
你是严谨的学术论文质量评估器。请根据标题、摘要和作者名单评分。

标题：{title}
作者：{authors}
摘要：{abstract}

评分维度与上限：
- novelty: 创新性，0-25
- technical_depth: 技术深度，0-25
- experimental_credibility: 实验可信度，0-20
- potential_impact: 潜在影响，0-20
- author_signal: 作者信号，0-10

作者规则：
- 只能使用提供的姓名；禁止虚构作者机构、履历、引用量或代表作。
- 如果无法可靠识别作者，author_signal 必须给中性分 5。

仅输出合法 JSON，不要输出总分、Markdown 或额外字段：
{{
  "novelty": 0,
  "technical_depth": 0,
  "experimental_credibility": 0,
  "potential_impact": 0,
  "author_signal": 5,
  "one_sentence": "一句中文评价",
  "reason": "简短中文评分理由"
}}
"""

READING_CHUNK_PROMPT = """\
请从下面的论文全文片段提取精读笔记。必须忠于原文；未出现的信息不要推断。
关注动机、贡献、方法与公式、实验设置与结论、局限、复现细节。
这是全文的第 {chunk_index}/{chunk_count} 个片段。

论文标题：{title}
全文片段：
{chunk}

直接输出中文笔记，保留必要的英文方法名、数据集名和符号。
"""

READING_SYNTHESIS_PROMPT = """\
请基于下面的论文材料生成 1500-2500 中文字符的简版精读。
必须客观、来源可追溯，不得添加材料中没有的结论。缺失信息明确写“论文材料未说明”。

论文标题：{title}
作者：{authors}
原始摘要：{abstract}
材料来源：{source_label}

论文材料：
{material}

使用以下 Markdown 结构：
### 一句话摘要
### 核心贡献
### 方法
### 实验结论
### 局限与适用边界
### 复现性
"""


def related_prompt(title: str, abstract: str, criteria: str) -> str:
    return RELATED_PROMPT.format(title=title, abstract=abstract, criteria=criteria)


def quality_prompt(title: str, abstract: str, authors: tuple[str, ...]) -> str:
    return QUALITY_PROMPT.format(
        title=title,
        abstract=abstract,
        authors=", ".join(authors) or "Unknown",
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
