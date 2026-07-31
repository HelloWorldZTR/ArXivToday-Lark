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

**ArXivToday-Lark** 是一个轻量级工具，可以自动从 [arXiv](https://arxiv.org) 获取最新论文，并通过飞书应用机器人推送到群聊中。

项目使用纯 LLM 两层筛选：批量相关性判断保持开放世界召回，二次横向比较只推荐最多五篇论文。日报不自动读取 PDF；用户发送 `/精读 <arXiv ID>` 后才生成并回复全文精读卡片。

## Demo

![Demo](images/demo.png)

![Demo-Dark](images/demo-dark.png)

## 工作流程

1. 首次运行只建立日期基线，不发送启动前已有论文。
2. 后续抓取基线日期之后发布且尚未记录在 `seen_papers.json` 中的论文。
3. 每批十篇进行 `related / possible / unrelated` 语义判断，不使用 embedding 或关键词硬过滤。
4. 将 `related + possible` 交给第二轮 LLM 横向比较，最多推荐五篇，也允许零篇。
5. 推荐论文排在表格前部，下方显示标题、作者和一句话摘要；其他 related 论文仍保留在表格中。
6. 未入选的 possible 论文不展示，unrelated 论文直接排除。
7. 日报不下载 PDF；只有群内 `/精读 2607.27180` 命令会触发精读并缓存结果。

批量相关性响应缺失时只重试缺失论文；再次失败会中止本次日报且不提交已见状态。PDF 获取失败时，按需精读会明确标记为摘要降级版。

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

在 [飞书开放平台](https://open.feishu.cn/) 创建企业自建应用并启用机器人。日报发送和 `/精读` 命令都使用同一个应用机器人。

#### 配置飞书应用机器人

1. 为应用开通机器人发送消息以及接收群聊消息所需权限。
2. 在事件订阅中选择长连接，并订阅 `im.message.receive_v1`。
3. 发布应用并将机器人加入目标群。
4. 从飞书事件日志或消息事件中取得目标群 `chat_id`。

#### 飞书卡片

日报使用 `ArXivToday.card` 模板，精读使用 raw Card JSON 2.0。请在 CardKit 中重新导入并发布当前模板，然后配置模板 ID 和新版本。

#### 配置脚本参数

在 `config.yaml` 中按分组修改配置：

1. `lark`：飞书应用 App ID/App Secret、目标群 chat ID、日报模板 ID/版本和分批大小。
2. `paper`：arXiv 分类、已见论文状态、旧历史记录和相关性筛选条件文件。
3. `llm`：可公网访问的 OpenAI SDK-compatible API、各阶段模型和输出 token 上限。
4. `recommendation`：一筛批大小、二筛批大小和最多推荐数。
5. `reading`：PDF 超时、全文分块大小和精读缓存目录。

按照你的实际情况进行修改。

部署时建议使用 `ARXIVTODAY_LARK_APP_ID`、`ARXIVTODAY_LARK_APP_SECRET`、
`ARXIVTODAY_LARK_CHAT_ID`、`ARXIVTODAY_LLM_API_KEY` 和
`ARXIVTODAY_LLM_BASE_URL` 环境变量。模型可通过 `ARXIVTODAY_LLM_MODEL`、
`ARXIVTODAY_RELATED_MODEL`、`ARXIVTODAY_RECOMMENDATION_MODEL` 和
`ARXIVTODAY_READING_MODEL` 分别覆盖。

#### 运行脚本

运行一次日报：

```sh
python main.py digest
```

常驻运行飞书命令机器人：

```sh
python main.py bot
```

`python main.py` 仍等价于 `python main.py digest`。生产环境应使用 systemd 等进程管理器保持 `bot` 常驻，并用 cron 或 timer 调度 `digest`。

##### 使用 crontab 命令周期性运行

> 需要 Linux 系统

例如，若要在每个工作日（weekday）的12:24（24小时制）查询 arXiv 论文并通过飞书机器人推送，可以：

1. 使用如下命令打开 `crontab` 编辑器

    ```sh
    crontab -e
    ```

2. 添加如下内容并保存

    ```sh
    24 12 * * 1-5 /absolute/path/to/python /absolute/path/to/ArXivToday-Lark/main.py digest
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
- `arxiv_today/bot.py`：飞书长连接、按需精读、缓存与单工作线程。
- `arxiv_today/prompts.py`：集中管理 LLM prompt 模板。
- `arxiv_today/papers.py`、`llm.py`、`reading.py` 和 `lark.py`：各自独立的领域服务。

## 自定义扩展

可以在本项目的基础上进行自定义扩展。比如：

- 你可以自行定义消息卡片的样式，或采用其他消息类型。
- 可以扩展更多只读命令或卡片交互，但应继续限制允许触发付费 LLM 的群聊。

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
