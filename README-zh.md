# ArXiv Today

<p align="center">
    <a href="README.md">
        <img src="https://img.shields.io/badge/README-English-blue" alt="README">
    </a>
    <a href="README-zh.md">
        <img src="https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-red" alt="README-zh">
    </a>
    <img src="https://img.shields.io/badge/License-GPL--3.0-yellow" alt="License">
</p>

> ArXiv Today：通过飞书（Lark）机器人，每日获取 arXiv 上的最新论文。

**ArXivToday-Lark** 是一个轻量级工具，可以自动从 [arXiv](https://arxiv.org) 获取最新论文，并通过自定义机器人直接推送到您的 [飞书](https://www.feishu.cn) 群聊中。该项目专为科研爱好者和学术专业人士设计，通过可定制的功能、无缝的集成以及可扩展的特性，简化了每日论文的获取过程。

其主要特点包括自动化调度、LLM 相关性筛选、结构化论文质量评分，以及可折叠的全文精读卡片。所有新发现的 related 论文都会进入日报，质量较高的论文还会收到单独的精读卡片。

## Demo

![Demo](images/demo.png)

![Demo-Dark](images/demo-dark.png)

## 工作流程

1. 首次运行只建立日期基线，不发送启动前已有论文。
2. 后续抓取基线日期之后发布且尚未记录在 `seen_papers.json` 中的论文。
3. related 模型只根据标题和摘要判断相关性。
4. 所有 related 论文进入主卡表格。
5. 从创新性、技术深度、实验可信度、潜在影响和作者信号五个维度评分。
6. 对评分最高且达到阈值的论文下载 PDF，每次最多生成五张独立的可折叠精读卡。

增强流程不维护重试队列。PDF 失败会自动降级为摘要精读；related 输出异常则记录错误并当作 unrelated。

## 使用方法

### 前置条件

1. 克隆此仓库。

   ```sh
   git clone https://github.com/InfinityUniverse0/ArXivToday-Lark.git
   ```

2. 创建并激活 conda 环境。

   ```sh
   conda create -n arxiv
   conda activate arxiv
   ```

3. 安装所需的 Python 包。

   ```sh
   cd ArXivToday-Lark
   pip install -r requirements.txt
   ```

### 部署

在 [飞书](https://www.feishu.cn) 中，将 **[自定义机器人](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)** 添加到群聊，部署并运行本项目，即可通过机器人每日自动获取 arXiv 最新相关论文并推送到群聊。

#### 添加飞书自定义机器人

参考 [这里](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot) 的文档操作步骤，在飞书中添加群聊机器人。

#### 飞书卡片

日报使用已发布的 `ArXivToday.card` 模板，精读消息使用 raw Card JSON 2.0 实现折叠内容。请先在 CardKit 中导入并发布模板，再配置模板 ID 和版本。

#### 配置脚本参数

在 `config.yaml` 中按分组修改配置：

1. `lark`：飞书机器人 Webhook URL、日报模板 ID/版本和分批大小。
2. `paper`：arXiv 分类、已见论文状态、旧历史记录和相关性筛选条件文件。
3. `llm`：模型配置（支持 Ollama 以及其他与 OpenAI SDK 兼容的服务）。
    - `model`
    - `base_url`: 若使用 Ollama，则该项为 `OLLAMA_HOST` URL 后面拼接 '/v1'
    - `api_key`: 若使用 Ollama，则该项可设置为任意非空字符串（Ollama 不进行鉴权）
    - `related_model`、`quality_model`、`reading_model`：可选的分阶段模型覆盖
4. `quality`：重要论文阈值和每次运行最多生成的精读卡数量。
5. `reading`：PDF 下载超时和全文分块大小。

按照你的实际情况进行修改。

部署时可以通过 `ARXIVTODAY_WEBHOOK_URL`、`ARXIVTODAY_LLM_API_KEY`、
`ARXIVTODAY_LLM_BASE_URL` 和可选的 `ARXIVTODAY_LLM_MODEL` 环境变量覆盖配置，
也可分别设置 `ARXIVTODAY_RELATED_MODEL`、`ARXIVTODAY_QUALITY_MODEL` 和
`ARXIVTODAY_READING_MODEL`，避免将凭据写入 YAML。

#### 运行脚本

使用 Python 运行 `main.py` 即可运行该脚本。

```sh
python main.py
```

但是为了让该脚本周期性地运行，你可以采用 Linux 系统的 `crontab` 命令，也可以使用 `schedule` 库来定期运行任务。

##### 使用 crontab 命令周期性运行

> 需要 Linux 系统

例如，若要在每个工作日（weekday）的12:24（24小时制）查询 arXiv 论文并通过飞书机器人推送，可以：

1. 使用如下命令打开 `crontab` 编辑器

    ```sh
    crontab -e
    ```

2. 添加如下内容并保存

    ```sh
    24 12 * * 1-5 /absolute/path/to/your/python/interpreter /absolute/path/to/ArXivToday-Lark/main.py
    ```

> [!NOTE]
>
> ⚠️ 注意，这里需要填写**绝对路径**

3. 可以通过如下命令检查 `cron` 任务是否正确设置

    ```sh
    crontab -l
    ```

##### 使用 schedule 库周期性运行

1. 安装依赖

   ```sh
   pip install schedule
   ```

2. 新建一个轻量调度脚本，调用公开的 `task` 入口：

    ```python
    import time
    import schedule
    from main import task

    schedule.every().day.at("10:17").do(task)
    while True:
        schedule.run_pending()
        time.sleep(1)
    ```

## 项目结构

- `main.py`：精简的命令行入口。
- `arxiv_today/config.py`：类型化配置类和 YAML 加载。
- `arxiv_today/pipeline.py`：从抓取到推送的完整流程。
- `arxiv_today/prompts.py`：集中管理 LLM prompt 模板。
- `arxiv_today/papers.py`、`llm.py`、`reading.py` 和 `lark.py`：各自独立的领域服务。

## 自定义扩展

可以在本项目的基础上进行自定义扩展。比如：

- 你可以自行定义消息卡片的样式，或采用其他消息类型。
- 可以使用飞书的 [应用机器人](https://open.feishu.cn/document/client-docs/bot-v3/bot-overview)（可能需要一些权限等），以实现更复杂的工作流。

## 许可证

本项目基于 [GPL-3.0 许可证](LICENSE)。

## 联系方式

如有任何问题、建议或反馈，欢迎联系：

- **电子邮箱**: wtxInfinity@outlook.com
- **GitHub 问题反馈**: [问题页面](https://github.com/InfinityUniverse0/ArXivToday-Lark/issues)

欢迎贡献代码、报告问题或提出改进建议！

## 贡献者

- [@InfinityUniverse0](https://github.com/InfinityUniverse0)
    - **E-mail**: [wtxInfinity@outlook.com](mailto:wtxInfinity@outlook.com)
- [@lxmliu2002](https://github.com/lxmliu2002)
    - **E-mail**: [lxmliu2002@126.com](mailto:lxmliu2002@126.com)

<a href="https://github.com/InfinityUniverse0/ArXivToday-Lark/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=InfinityUniverse0/ArXivToday-Lark"/>
</a>
