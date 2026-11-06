# Sales Agent

A multilingual sales agent that remembers leads, briefs the rep, continues the call in the lead's language, and drafts outreach.

## Run locally

```sh
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8787 for Helio's sales desk. Click Alex Rivera, Mei Chen, Luis Ortega, or Hana Okonkwo to load their formatted English memory brief beside an empty-bank brief. Each lead has an isolated memory bank. Readable fact lines sit beside the call box, meeting confirmation form, and email/LinkedIn/X drafts. Raw JSON is collapsed behind **Show recall**. The default language follows remembered preferences or past conversation language; unknown languages fall back to English.

Configuration is loaded from this repository's `.env`, regardless of your current directory. Required settings: `HINDSIGHT_API_URL`, `HINDSIGHT_API_KEY`, `GROQ_API_KEY`, and `GROQ_MODEL`. For a fresh setup, create a virtual environment and copy `.env.example` to `.env`, then fill in your existing credentials. Never commit credentials.

## How it works

- `brief_rep` recalls the selected bank (`lead-alex-rivera`, `lead-mei-chen`, `lead-luis-ortega`, or `lead-hana-okonkwo`) and reflects an English rep brief. `compare_briefs` also reads `lead-alex-rivera-empty`, which receives no retained facts or lead history.
- `continue_call` recalls context, generates a Groq reply in the lead's language, then retains both turns in Hindsight. The page reports whether saving succeeded.
- `draft_outbound` recalls context and uses Groq to draft an email, a LinkedIn note, and an X message. Nothing is sent.
- The facts panel shows the unmodified recall response used for the most recent action. After a reply is saved, reload the brief or regenerate drafts to use the updated memory.
- Explicitly confirmed meeting times are saved and shown as a new fact, then both briefs refresh. Use the meeting confirmation form or a clear confirmation in the lead's reply. A requested meeting remains a request until confirmed. No calendar invitation is sent; timezone is unspecified.

`seed_leads.py` was used to retain the four rep-provided histories. Alex's meeting is confirmed for 10 November 2026 at 16:30 with the finance director required. Mei has one Mandarin call and an annual-price objection, with no meeting. Luis has only a name and company, with no conversation. Hana prefers English and email and went quiet after a generic follow-up. Setup never runs on page reload. The original setup and smoke-check scripts are historical utilities; do not run them to open the desk.

The server binds only to localhost. Calls to the configured Hindsight and Groq services happen when you load the page or use its actions. Errors are reported without displaying credentials or upstream exception details.

## Add a lead

Open **Add lead** below the lead list and enter a name, company, language, and one note. The app creates a dedicated Hindsight bank and retains these details before listing the lead. It then selects the new lead and recalls that bank for both the brief and facts, alongside the existing empty-bank comparison and outreach drafts. Listen and Speak use the new lead's language too.

Added leads persist in the local `leads.sqlite3` registry across reloads and server restarts; their actual memory remains in Hindsight. This database is ignored by Git and is never served by the app. Failed saves keep the form intact and do not publish a lead; retrying reuses the reserved bank. Adding the same name and company again is rejected.

## Pipeline, CSV, and queued outreach

The top pipeline shows live **New, Contacted, Responded, Meeting, Won** counts. New and imported leads begin as New. Existing leads initially reflect their supplied history (Alex: Meeting; Mei: Responded; Hana: Contacted; Luis: New). The rep can explicitly change a stage using the stage selector; that change is retained in memory.

Upload a UTF-8 CSV containing `name,company,language,note`, with or without the header. Quoted commas and multiline notes are supported. Files are limited to 100 leads / 500 KB. The entire CSV is validated before creating banks; valid rows are then retained independently. The result reports any duplicate or failed rows. Retry a partially successful import safely: existing leads are skipped and failed pending rows reuse their reserved banks. `sample-leads.csv` contains three clearly labeled import-check leads.

Each draft has **Queue … in Helio**. Queueing retains the exact draft as an outbound transcript in the selected lead's Hindsight bank, then records Contacted. This queue exists only inside the app: no email, LinkedIn, X, or carrier connection is present, and no external delivery is claimed.

**Generate & remember reply** retains both call turns, records Responded, and exposes the transcript before browser speech playback. Confirming a meeting retains the confirmation and records Meeting. A failed Hindsight save does not advance the stage. Saved transcripts remain visible after reload through a local index of successfully retained activity. The pipeline follows the latest action, so a new reply can move an existing meeting lead to Responded.

The **Key notes** card uses Hindsight structured reflect to show the remembered objection, language, next step, and advice on what the rep should do differently next time. Advice is distinguished from confirmed lead facts. Refreshing a lead reloads its notes, briefs, transcripts, and drafts.

## Listen and Speak

In **Continue the call**, **Listen** uses the browser's speech recognition and microphone permission to put a transcript into the lead reply box. Review it, then click **Generate & remember reply**. After both turns are successfully retained in Hindsight, the assistant reply is automatically read aloud. **Speak** replays that saved reply. A failed save prevents playback and keeps the typed/transcribed input for retry.

Browser speech defaults are Spanish (`es-ES`) for Alex, Mandarin (`zh-CN`) for Mei, and English (`en-US`) for Hana and Luis. Explicit recalled preferences and subsequent saved reply languages update these defaults. The conversation language selector can override the next turn. Switching leads stops recording/playback and clears the previous lead's replay.

All speech controls use browser APIs; the app adds no audio upload, transcription service, login, or sending. Speech support and voices depend on the browser; its speech recognition may use the browser vendor's service. If speech is unsupported or microphone access is denied, typing and saving still work. If automatic playback is blocked, click **Speak** after saving.

## Memory smoke check

`prove_memory.py` uses the earlier `sales-agent-demo` bank, which the app no longer reads. It can retain demo data, recall it, and reflect on it:

```sh
python prove_memory.py --run
```

This explicitly writes demo data and calls Hindsight. Without `--run`, the script makes no API calls. Do not rerun it just to open the web page.

## Local checks

```sh
python -m unittest discover -s tests
node --test tests/test_voice.cjs
```

These checks use mocked services and make no API calls.
