from unittest import TestCase

from arxiv_today.prompts import (
    reading_chunk_prompt,
    reading_synthesis_prompt,
    recommendation_prompt,
    related_batch_prompt,
)
from tests.test_pipeline import make_paper


class EmbodiedIntelligencePromptTest(TestCase):
    def test_related_prompt_contains_domain_priorities_and_ood_boundary(self) -> None:
        prompt = related_batch_prompt([make_paper("1")], "criteria")

        self.assertIn("VLA", prompt)
        self.assertIn("WAM/world model", prompt)
        self.assertIn("whole-body control", prompt)
        self.assertIn("dexterous hand", prompt)
        self.assertIn("感知—决策—行动闭环", prompt)
        self.assertIn("possible", prompt)
        self.assertIn("保护 OOD", prompt)
        self.assertIn("criteria", prompt)

    def test_recommendation_prompt_requires_comparison_and_evidence(self) -> None:
        prompt = recommendation_prompt(
            [make_paper("1")],
            "criteria",
            limit=5,
        )

        self.assertIn("横向比较", prompt)
        self.assertIn("最多选择 5 篇", prompt)
        self.assertIn("闭环控制", prompt)
        self.assertIn("sim-to-real", prompt)
        self.assertIn("不超过 60 个中文字符", prompt)

    def test_reading_prompts_preserve_embodiment_details(self) -> None:
        chunk = reading_chunk_prompt("Paper", "full text", 1, 2)
        synthesis = reading_synthesis_prompt(
            title="Paper",
            authors=("Author",),
            abstract="Abstract",
            material="Notes",
            source_label="PDF",
        )

        self.assertIn("观测/动作空间", chunk)
        self.assertIn("控制频率", chunk)
        self.assertIn("不要把仿真结果表述为真实机器人结果", synthesis)
        self.assertIn("### 数据与训练", synthesis)
