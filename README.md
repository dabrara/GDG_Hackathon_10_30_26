# PlainSight

Understand any confusing document (medical, legal, school, government) in your own language.
FastAPI backend, one vanilla HTML page, local Gemma 4 through Ollama. No cloud AI, database, or analytics.

## Run it

**Windows:** install Python 3.10+, then run `START-PLAINSIGHT.cmd` as administrator. It installs Ollama if missing, picks a Gemma 4 model for your RAM, pulls it, sets up `.venv`, starts the app, and opens http://localhost:8000. Press ENTER in the window to stop.

**macOS/Linux:** install Python 3.10+ and Ollama, start Ollama, then run `bash run.sh` and open http://localhost:8000.

Any local Gemma tag works with `MODEL=` (Gemma 2, 3, 3n, 4). Photos need a vision model: `gemma4:*`, `gemma3n:e2b/e4b`, or `gemma3:4b/12b/27b`. `gemma2:*` and `gemma3:1b/270m` read text only, so the app disables photo upload and asks you to paste text. If a model rejects tool calls (common for Gemma 2/3), Pip still answers but cannot add checklist items. The header speed label is estimated from the parameter count of whichever tag you use.

Automatic model by RAM: `gemma4:e2b` (<16 GiB), `e4b` (16-23), `12b` (24-31), `26b` (32-47), `31b` (48+). Override with `MODEL=gemma4:e4b`.
Other settings: `OLLAMA_URL`, `NUM_CTX` (8192), `KEEP_ALIVE` (30m), `HOST`, `PORT`.
Keep `OLLAMA_URL` local and `HOST` at 127.0.0.1: the app has no authentication. To host it on DigitalOcean see `deploy/DIGITALOCEAN.md`.

## Digital Ocean
Create the Droplet with DigitalOcean’s “AI/ML ready” GPU image so the NVIDIA driver is already installed. Plain Ubuntu works, but the model would run on the CPU and be slow.
Copy the script(digitalocean.txt) to the Droplet (scp deploy-plainsight.sh root@<droplet-ip>:/root/), or paste it into nano deploy-plainsight.sh.
Run sudo bash deploy-plainsight.sh. To also download extra models for the live switcher, run sudo EXTRA_MODELS="gemma3n:e4b gemma3:4b gemma2:9b" bash deploy-plainsight.sh.
When it finishes it prints the https://<ip>.sslip.io link, a username (demo) and a password. The same details are saved in /root/plainsight-credentials.txt.

Installs git, Python and Ollama, then clones dabrara/GDG_Hackathon_10_30_26 (branch main).
Installs the app’s Python requirements and starts it as a background service that restarts if it crashes.
Picks a Gemma 4 model from the GPU’s memory: 12B at 24 GB or more, E4B at 12 GB or more, otherwise E2B. Set MODEL=gemma4:31b to force a bigger one.
Puts HTTPS and a password in front of the site, using a free sslip.io address (or DOMAIN= if you have your own). The app has no login of its own, so this is what keeps it private.
Opens only the SSH and web ports on the firewall, and keeps Ollama private.
Sets the “DigitalOcean GPU Droplet” badge in the page header.

Re-running and options

Run the same command again any time to pull your latest GitHub changes and restart. It keeps the same password unless you set APP_PASS.
You can also set APP_USER, BRANCH and REPO_URL the same way as MODEL.


## What it does

- Upload or photograph one or several pages (or paste text), pick a language and reading level, press **Explain this document**.
- The upload area stays on the page. Every analysis stays below it as its own card that you can minimize, expand, or remove, so you can keep adding documents without refreshing.
- Each card: summary, what it means, key numbers and deadlines (each with a highlighted source quote), checklist with progress, glossary, questions to ask, the original text, a 3-question quiz, read aloud (play/pause, stop, back and forward 10 seconds; seeking is approximate because browsers cannot seek speech), printable summary.
- Switching language is instant: page labels for every language are translated once in the background, stored on disk (`.ui_cache.json`), and loaded in one request. Existing analysis cards are translated in place (quotes, amounts, and dates stay as written) and each translation is kept, so switching back is instant too.
- **Pip**, the side assistant, is a real streaming model chat. Before a document exists it explains how the app works. Press **Ask Pip** on a card to talk about that document (each keeps its own chat). It answers from the document, ends with a source quote, and can search the text, add checklist items, and save questions for a professional. Those changes appear on the page immediately.
- Dark theme by default, with a light theme toggle, a high-contrast mode (follows the OS "increase contrast" setting until you choose), and a larger-text button. The header shows the model in use and whether the expected speed is Fast, Medium, or Slow. RTL layout for Arabic.
- Three synthetic samples (hospital bill, prescription, lease) are one click away.

## Speed

- Responses stream, so text and progress appear as the model produces them.
- The model is loaded at startup and kept in memory (`KEEP_ALIVE`).
- Pasted text skips re-transcription, which is the slowest part of analysis.
- Photos are resized to 1280 px and compressed in the browser; output length is capped per request.
- One reusable connection to Ollama; options a model rejects (`think`, tools) are remembered so they cost one retry, once.
- Motion (scroll reveals, word-by-word headline with a highlighter swipe, a stamp, count-ups, pinned-note cards) uses transform/opacity only and is switched off by the OS "reduce motion" setting.
- "Pick your Gemma" lists Gemma 2, 3, 3n (E2B/E4B) and 4; click an installed size to switch the live model. Set `DEPLOY_HOST` to show a hosting badge.

## Privacy and limits

- Sessions live in server memory (max 50, oldest dropped). "New document" deletes the session; restarting the server clears everything.
- Document text is treated as untrusted in prompts. Number and deadline quotes are checked against the transcript; for photos the transcript comes from the same model, so a matching quote is not independent verification. Always check amounts and dates against the original.
- Not medical or legal advice. Pasted text is limited to 12,000 characters; chat and quiz use the first 6,000. One image per analysis, no PDFs.
- Browser voice input may send audio to the browser vendor; a confirmation appears first.
- Translating an analysis card needs a model call the first time per language; after that it is stored for the session. Translated text is the model's work: check it against the original.
- The very first run pre-translates page labels for 15 languages in the background, which uses the model for a short time.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v   # offline logic, no Ollama needed
python tests/smoke_test.py                                # live: needs the server and a model
```

## Layout

`app/main.py` routes, Ollama streaming adapter, schemas, tools · `static/index.html` the whole UI · `scripts/` model selection and sample generation · `tests/`
