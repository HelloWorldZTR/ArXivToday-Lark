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

> ArXiv Today: Get arXiv daily papers right in your Lark (飞书) via bot.

**ArXivToday-Lark** is a lightweight tool that automates the process of fetching the latest papers from [arXiv](https://arxiv.org) and delivers them directly to your [Lark](https://www.feishu.cn) group chats using a custom bot. Designed for research enthusiasts and academic professionals, this project simplifies daily paper discovery with customizable features, seamless integration, and extendable functionality.

Key highlights include automated scheduling, LLM relevance filtering, structured paper quality scoring, and collapsible full-paper reading cards. Every new related paper appears in the digest, while the highest-quality papers receive a separate in-depth reading card.

## Demo

![Demo](images/demo.png)

![Demo-Dark](images/demo-dark.png)

## Workflow

1. On the first run, initialize a date baseline without sending existing papers.
2. On later runs, fetch unseen papers published after that baseline.
3. Let the relatedness model inspect each title and abstract.
4. Show every related paper in the digest card.
5. Score related papers for novelty, technical depth, experimental credibility, potential impact, and author signal.
6. Download and read the PDF for up to five highest-scoring important papers, then send one collapsible reading card per paper.

There is no enrichment retry queue. PDF failures fall back to the abstract, while malformed relatedness results are logged and treated as unrelated.

## Usage

### Prerequisite

1. Clone this repository.

   ```sh
   git clone https://github.com/InfinityUniverse0/ArXivToday-Lark.git
   ```

2. Create and activate conda environment.

   ```sh
   conda create -n arxiv
   conda activate arxiv
   ```

3. Install the required Python packages.

   ```sh
   cd ArXivToday-Lark
   pip install -r requirements.txt
   ```

### Deployment

In [Lark](https://www.feishu.cn), add a **[Custom Bot](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)** to a group chat. Deploy and run this project to fetch the latest relevant papers from arXiv daily and push them to the group via the bot.

#### Add a Lark Custom Bot

Follow the steps in [this guide](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot) to add a custom bot to your group chat in Lark.

#### Lark Cards

The digest uses the published `ArXivToday.card` template, while reading messages use raw Card JSON 2.0 for collapsible content. Import and publish the template in CardKit, then configure its template ID and version.

#### Configure Script Parameters

In `config.yaml`, modify the grouped parameters based on the results of the previous steps:

1. `lark`: webhook URL, digest template ID/version, and batch size.
2. `paper`: arXiv categories, seen-paper state, legacy history, and the relatedness criteria file.
3. `llm`: model configuration (supports Ollama and other OpenAI SDK-compatible services).
    - `model`
    - `base_url`: When using Ollama, set this to the `OLLAMA_HOST` URL followed by '/v1'
    - `api_key`: When using Ollama, this can be set to any non-empty string (Ollama does not require authentication)
    - `related_model`, `quality_model`, `reading_model`: optional per-stage overrides
4. `quality`: important-paper threshold and maximum reading cards per run.
5. `reading`: PDF timeout and full-text chunk size.

Adjust these settings according to your specific setup.

For deployments, secrets can remain outside YAML by setting
`ARXIVTODAY_WEBHOOK_URL`, `ARXIVTODAY_LLM_API_KEY`,
`ARXIVTODAY_LLM_BASE_URL`, and optionally `ARXIVTODAY_LLM_MODEL`,
`ARXIVTODAY_RELATED_MODEL`, `ARXIVTODAY_QUALITY_MODEL`, and
`ARXIVTODAY_READING_MODEL`.

#### Run the Script

Run the script using Python:

```sh
python main.py
```

To run the script periodically, you can use the `crontab` command in Linux or the `schedule` library.

##### Run Periodically with crontab

> Requires a Linux system

For example, to fetch arXiv papers and push them via the Lark bot at 12:24 PM every weekday, follow these steps:

1. Open the `crontab` editor with the following command:

   ```sh
   crontab -e
   ```

2. Add the following line and save it:

   ```sh
   24 12 * * 1-5 /absolute/path/to/your/python/interpreter /absolute/path/to/ArXivToday-Lark/main.py
   ```

> [!NOTE]
>
> ⚠️ Ensure to provide **absolute paths** for both the Python interpreter and the script.

3. Verify the crontab task setup with this command:

   ```sh
   crontab -l
   ```

##### Run Periodically with the schedule Library

1. Install the dependency:

   ```sh
   pip install schedule
   ```

2. Create a small scheduler script and call the public `task` entry point:

    ```python
    import time
    import schedule
    from main import task

    schedule.every().day.at("10:17").do(task)
    while True:
        schedule.run_pending()
        time.sleep(1)
    ```

## Project Structure

- `main.py`: minimal command-line entry point.
- `arxiv_today/config.py`: typed configuration classes and YAML loading.
- `arxiv_today/pipeline.py`: complete fetch-to-delivery workflow.
- `arxiv_today/prompts.py`: centralized LLM prompt templates.
- `arxiv_today/papers.py`, `llm.py`, `reading.py`, and `lark.py`: focused domain services.

## Extension

This project can be extended to meet custom requirements. For instance:

- You can design your own message card styles or use other message types.
- You can integrate a [Lark App Bot](https://open.feishu.cn/document/client-docs/bot-v3/bot-overview) (might require additional permissions) to implement more complex workflows.

## License

This project is under the [GPL-3.0 License](LICENSE).

## Contact

For any questions, suggestions, or feedback, feel free to reach out:

- **Email**: wtxInfinity@outlook.com
- **GitHub Issues**: [Issues Page](https://github.com/InfinityUniverse0/ArXivToday-Lark/issues)

Feel free to contribute, report issues, or suggest improvements!

## Contributors

- [@InfinityUniverse0](https://github.com/InfinityUniverse0)
    - **E-mail**: [wtxInfinity@outlook.com](mailto:wtxInfinity@outlook.com)
- [@lxmliu2002](https://github.com/lxmliu2002)
    - **E-mail**: [lxmliu2002@126.com](mailto:lxmliu2002@126.com)

<a href="https://github.com/InfinityUniverse0/ArXivToday-Lark/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=InfinityUniverse0/ArXivToday-Lark"/>
</a>
