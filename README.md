# Sales Agent

A multilingual sales agent that remembers leads, briefs the rep, continues the call in the lead's language, and drafts outreach.

## Run locally

```sh
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8787. The page shows formatted English briefs side by side: one grounded in Alex Rivera's memory and one from an empty bank. It also loads outreach drafts, shows raw recalled facts, and lets you enter a lead reply. The default language follows remembered preferences; you can also select a language.

Configuration is loaded from this repository's `.env`, regardless of your current directory. Required settings: `HINDSIGHT_API_URL`, `HINDSIGHT_API_KEY`, `GROQ_API_KEY`, and `GROQ_MODEL`. For a fresh setup, create a virtual environment and copy `.env.example` to `.env`, then fill in your existing credentials. Never commit credentials.

## How it works

- `brief_rep` recalls `lead-alex-rivera` and reflects an English rep brief. `compare_briefs` also reads `lead-alex-rivera-empty`, which receives no retained facts or lead history.
- `continue_call` recalls context, generates a Groq reply in the lead's language, then retains both turns in Hindsight. The page reports whether saving succeeded.
- `draft_outbound` recalls context and uses Groq to draft an email, a LinkedIn note, and an X message. Nothing is sent.
- The facts panel shows the unmodified recall response used for the most recent action. After a reply is saved, reload the brief or regenerate drafts to use the updated memory.
- Explicitly confirmed meeting times are saved and shown as a new fact, then both briefs refresh. Use the meeting confirmation form or a clear confirmation in the lead's reply. A requested meeting remains a request until confirmed. No calendar invitation is sent; timezone is unspecified.

`setup_alex.py` was used to create the two banks and retain the rep-provided history: Alex Rivera, operations lead at Clínica Norte, prefers Spanish, evaluating a sales assistant, follow-up requested for 10 November 2026 at 16:30 with the finance director. Setup does not run on page reload. The earlier smoke-check script remains isolated in its original bank.

The server binds only to localhost. Calls to the configured Hindsight and Groq services happen when you load the page or use its actions. Errors are reported without displaying credentials or upstream exception details.

## Memory smoke check

`prove_memory.py` uses the earlier `sales-agent-demo` bank, which the app no longer reads. It can retain demo data, recall it, and reflect on it:

```sh
python prove_memory.py --run
```

This explicitly writes demo data and calls Hindsight. Without `--run`, the script makes no API calls. Do not rerun it just to open the web page.

## Local checks

```sh
python -m unittest discover -s tests
```

These checks use mocked services and make no API calls.
