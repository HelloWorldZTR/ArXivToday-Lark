# Paper to Hunt：Embodied Intelligence

我关注具身智能（Embodied Intelligence / Embodied AI）与通用机器人学习。论文的核心贡献应当面向能在物理世界或高保真仿真环境中感知、推理、规划并执行动作的智能体，而不是只在引言或应用展望中提及机器人。

## 最高优先级

### 1. 具身基础模型与机器人世界模型

- Vision-Language-Action Model（VLA）、Language-Conditioned Policy、Generalist Robot Policy、Robot Foundation Model
- World Model、World Action Model（WAM）、Action Model、Video/Latent Predictive Model，以及用于机器人规划与控制的生成式动力学模型
- 从视觉、语言、触觉、本体感知到连续动作的多模态表征、对齐和 action tokenization
- 基于 diffusion、flow matching、autoregressive model、transformer 的机器人策略与动作生成
- 长时程任务中的规划、记忆、推理、反馈纠错和闭环执行
- 跨机器人本体、跨任务、跨场景泛化，以及大规模预训练、后训练和高效适配

### 2. Humanoid 与全身运动/控制

- Humanoid control、Whole-Body Control（WBC）、Whole-Body Planning
- Locomotion、loco-manipulation / locomanipulation、locomanimulation（移动与操作的统一学习）
- 动态行走、跑跳、平衡恢复、接触丰富运动、地形适应和敏捷技能
- Motion Generation、Motion Planning、Motion Imitation、Motion Retargeting、Human-to-Robot Skill Transfer
- 基于强化学习、模仿学习、最优控制、MPC 或混合方法的全身策略
- 上下肢协同、双臂协作、移动操作、全身接触和长时程任务执行

### 3. 灵巧操作与灵巧手

- Dexterous Manipulation、Dexterous Hand、Multi-Fingered Hand、In-Hand Manipulation
- 触觉感知、视触觉融合、接触建模、抓取重定向和手眼协调
- 灵巧手技能学习、双手操作（bimanual manipulation）、工具使用和可变形物体操作
- Sim-to-Real、Real-to-Sim-to-Real、在线适应，以及面向硬件约束的鲁棒控制

## 同样关注的支撑方向

- Robot Learning：Imitation Learning、Reinforcement Learning、Offline RL、Behavior Cloning、Learning from Demonstration
- 机器人数据：遥操作、互联网视频、合成数据、数据混合、数据质量、自动标注与 scalable data collection
- 3D/4D 场景理解、affordance、object-centric representation、spatial reasoning（须服务于机器人决策或控制）
- Embodied Agent、Interactive Agent、Navigation、Mobile Manipulation（须包含物理交互或可执行动作）
- 仿真器、benchmark、评测协议和数据集，尤其关注真实机器人迁移、泛化、鲁棒性、安全性与可复现性
- 机器人系统与硬件协同：实时推理、低层控制、感知延迟、算力/功耗限制和安全约束

## 重点评估信号

- 是否在真实机器人、humanoid、dexterous hand 或可信的物理仿真中进行闭环验证
- 是否与强基线比较，并包含消融实验、失败案例和统计结果
- 是否展示跨任务、跨场景、跨本体或 sim-to-real 泛化，而非只复现单一演示
- 是否公开代码、模型、数据、硬件细节或足以复现的训练与控制配置
- 是否真正改善任务成功率、鲁棒性、样本效率、实时性或长时程执行能力

## 排除或降低优先级

- 纯 LLM/VLM、纯文本 Agent、RAG 或通用多模态研究，且没有机器人动作、物理交互或具身评测
- 只生成自然视频、人物动画或 human motion，未用于机器人控制、retargeting 或具身任务
- 与机器人无关的 world model，例如只用于语言、金融、推荐、自动驾驶预测但不涉及通用具身智能
- 纯 3D 重建、检测、分割、NeRF/3DGS，且没有服务于机器人感知—决策—行动闭环
- 传统路径规划、控制器或机械结构设计，仅做小幅参数优化且缺少学习、泛化或具身智能贡献
- 医疗、工业或自动驾驶论文若只是垂直应用优化，且方法不能迁移到通用机器人学习
- 仅有概念、观点、综述或项目介绍，缺少实质方法与实验；高质量综述或重要 benchmark 可例外保留

相关性判断应看论文的主要问题、方法和实验，而不是关键词命中。VLA、WAM/world model、humanoid control、whole-body control、motion generation、dexterous hand 与 loco-manipulation 是当前最优先方向。
