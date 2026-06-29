# LLM Council

<img width="1600" height="1013" alt="llm-council-illustration" src="https://github.com/user-attachments/assets/8bbbf278-8cec-4b18-887d-21092bdb8fb0" />


A free, working implementation of Andrej Karpathy's "LLM Council" concept: a chat-style interface where a council of AI models independently reviews your idea, anonymously critiques each other, and a chairman model synthesizes a final verdict — printed straight into the chat, with a standalone button to download the full report as HTML.

Built with Flask. Uses [OpenRouter](https://openrouter.ai)'s free-tier router, so running this costs $0.
Better responses will always be preferred, of course. You can access paid models for this setup for as low as %5 on OpenRouter

## Project structure

```
llm-council/
├── run.py                      
├── config.py                   
├── .env.example              
├── requirements.txt            
├── app/
│   ├── __init__.py             
│   ├── routes/
│   │   ├── pages.py            
│   │   └── council.py          # GET /roles + POST /council (streaming)
│   ├── services/
│   │   └── council_service.py  # the actual council logic 
│   ├── templates/
│   │   └── index.html          # the chat page markup
│   └── static/
│       ├── css/style.css       # all styling
│       └── js/chat.js          # frontend logic: roles, streaming, download
└── scripts/
    └── terminal_report.py      # standalone CLI version, no server needed here
```

## Setup

1. **Clone and enter the project:**
   ```
   git clone https://github.com/ke77/LLM-Council
   cd llm-council
   ```

2. **Create a virtual environment** (optional but recommended — keeps this project's dependencies separate from other Python projects on your machine):
   ```
   python3 -m venv venv
   source venv/bin/activate      # Mac/Linux (and for Git Bash on Windows)
   venv\Scripts\activate         # Windows (CMD)
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Set up your environment variables:**
   ```
   cp .env.example .env
   ```
   Then open `.env` and paste in a free API key from [openrouter.ai](https://openrouter.ai).

5. **Run it:**
   ```
   python run.py
   ```

6. Open `http://localhost:5000` in your browser.

## Choosing council roles

By default, the app shows 11 selectable personas (Venture Capitalist, Skeptical Customer, Senior Engineer, Security Engineer, Competitor, Product Manager, Marketing Strategist, Economist, Domain Expert, Legal & Regulatory Reviewer). Click "Council roles" above the input box to check/uncheck which ones run for your idea.

The defaults (Venture Capitalist, Skeptical Customer, Domain Expert, Competitor, Economist) are general-purpose, since not every idea is software-related. Software-specific roles (Senior Engineer, Security Engineer) are available but unchecked by default — turn them on for technical product ideas.

New roles can be added in `app/services/council_service.py` inside `ROLE_LIBRARY` — each one just needs a `name`, a short `description` (shown in the picker), and a `persona` instruction.

## On model selection and free-tier limits

This app uses `openrouter/free` — a router OpenRouter manages themselves that automatically picks a working free model for every request, instead of hardcoding a specific model name. This matters because OpenRouter's free model lineup changes week to week; hardcoded slugs go stale and start 404ing. If you want to pin a specific model instead, change `DEFAULT_MODEL` at the top of `council_service.py`.

Free models are rate-limited (around 20 requests/minute, with daily caps that are tighter on brand-new accounts with $0 ever added). `call_model()` automatically retries once or twice with a short backoff if it hits a rate limit, which clears most transient 429s without any action from you. If a model call still fails, the report shows a readable `[ERROR: ...]` in that section instead of crashing the whole run.

## Using it without the web interface

If you just want a one-off HTML report from the command line, without running a server:

```
python scripts/terminal_report.py
```

Edit `IDEA` (and optionally `SELECTED_ROLES`) near the top of that file first. It reuses the exact same logic as the web app via `app/services/council_service.py`, so any fix made there applies here too.

## How it works

Every idea you submit goes through three stages:

1. **Independent reviews** — your selected personas each review the idea separately, with no visibility into each other's answers.
2. **Anonymized peer review** — each persona's answer is shown to the others with identities stripped, and each one critiques and ranks the rest.
3. **Chairman synthesis** — a final model reads everything and writes one verdict: what the council agreed on, where it disagreed, and a concrete recommendation. This prints directly into the chat, with a standalone "Download full report" button underneath for the complete HTML version (including every individual response and peer review).

Find the full technical write-up here: https://kobbycodes.hashnode.dev/building-an-llm-council
