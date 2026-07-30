"""All LLM prompt templates used by the application."""

PAPER_MATCH_PROMPT = """\
你是一个专业的学术论文筛选助手。你的任务是判断给定的论文是否符合我正在寻找的研究内容。

请仔细阅读以下论文的标题和摘要：
标题：{title}
摘要：{abstract}

我正在寻找的研究内容（paper_to_hunt）：
{criteria}

---

请分析这篇论文的内容是否与我寻找的研究内容相符。在分析时，请考虑：
1. 研究主题的相关性
2. 论文的关键概念与我的研究描述的匹配程度

如果符合，请只回答“Yes”；如果不符合，请只回答“No”。
"""

ABSTRACT_TRANSLATION_PROMPT = """\
请将下面的学术论文摘要翻译为中文：
{abstract}

注意：
- 中文语境中常用的英文学术术语可以保留英文原文，例如 Transformer。
- 其他关键学术术语可以中英文对照，例如：后门攻击（Backdoor Attack）。
- 直接给出翻译结果，不需要解释或任何其他内容。
"""


def paper_match_prompt(title: str, abstract: str, criteria: str) -> str:
    return PAPER_MATCH_PROMPT.format(title=title, abstract=abstract, criteria=criteria)


def abstract_translation_prompt(abstract: str) -> str:
    return ABSTRACT_TRANSLATION_PROMPT.format(abstract=abstract)
