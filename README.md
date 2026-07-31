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

**ArXivToday-Lark** fetches the latest papers from [arXiv](https://arxiv.org) and delivers them to a [Lark](https://www.feishu.cn) group through an app bot.

It uses a pure-LLM two-stage filter: batched semantic classification preserves open-world recall, while comparative selection recommends at most five papers. PDFs are only read after a user sends `/精读 <arXiv ID>`.

## Demo

![Demo](images/demo.png)

![Demo-Dark](images/demo-dark.png)

## Workflow

1. On the first run, initialize a date baseline without sending existing papers.
2. On later runs, fetch unseen papers published after that baseline.
3. Classify batches of ten as `related`, `possible`, or `unrelated`, without embeddings or hard keyword gates.
4. Compare `related + possible` papers and recommend at most five; zero is valid.
5. Put recommendations first and show their titles, authors, and one-sentence summaries below the table.
6. Hide unselected possible papers and exclude unrelated papers.
7. Generate and cache a reading only after `/精读 2607.27180`.

Missing batch results are retried once. A second failure aborts the digest without committing seen state. PDF failures produce an explicitly labeled abstract fallback.

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

Create an internal app in the [Lark Developer Console](https://open.feishu.cn/), enable its bot, and use that app for both digests and `/精读`.

#### Configure the Lark App Bot

1. Grant the permissions needed to send bot messages and receive group messages.
2. Select long connection for event delivery and subscribe to `im.message.receive_v1`.
3. Publish the app and add its bot to the target group.
4. Obtain the group's `chat_id` from a message event or the developer-console event log.

#### Lark Cards

The digest uses `ArXivToday.card`; readings use raw Card JSON 2.0. Re-import and publish the current template in CardKit, then configure its template ID and new version.

#### Configure Script Parameters

In `config.yaml`, modify the grouped parameters based on the results of the previous steps:

1. `lark`: app ID/secret, target chat ID, digest template ID/version, and batch size.
2. `paper`: arXiv categories, seen-paper state, legacy history, and the relatedness criteria file.
3. `llm`: a publicly reachable OpenAI SDK-compatible endpoint, stage models, and output limits.
4. `recommendation`: relevance batch size, comparative-selection batch size, and recommendation cap.
5. `reading`: PDF timeout, full-text chunk size, and cache directory.

Adjust these settings according to your specific setup.

Keep secrets outside YAML with `ARXIVTODAY_LARK_APP_ID`,
`ARXIVTODAY_LARK_APP_SECRET`, `ARXIVTODAY_LARK_CHAT_ID`,
`ARXIVTODAY_LLM_API_KEY`, and `ARXIVTODAY_LLM_BASE_URL`. Stage models can
be set with `ARXIVTODAY_LLM_MODEL`, `ARXIVTODAY_RELATED_MODEL`,
`ARXIVTODAY_RECOMMENDATION_MODEL`, and `ARXIVTODAY_READING_MODEL`.

#### Run the Script

Run one digest:

```sh
python main.py digest
```

Run the long-lived command bot:

```sh
python main.py bot
```

`python main.py` remains an alias for `digest`. Keep `bot` alive with a process manager and schedule `digest` with cron or a timer.

##### Run Periodically with crontab

> Requires a Linux system

For example, to fetch arXiv papers and push them via the Lark bot at 12:24 PM every weekday, follow these steps:

1. Open the `crontab` editor with the following command:

   ```sh
   crontab -e
   ```

2. Add the following line and save it:

   ```sh
   24 12 * * 1-5 /absolute/path/to/python /absolute/path/to/ArXivToday-Lark/main.py digest
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
- `arxiv_today/bot.py`: long connection, on-demand readings, cache, and single worker.
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
