# LLM Council

A free, working implementation of Andrej Karpathy's "LLM Council" concept: a chat-style interface where a council of AI models independently reviews your idea, anonymously critiques each other, and a chairman model synthesizes a final verdict — delivered as a downloadable HTML report.

Built with Flask. Uses [OpenRouter](https://openrouter.ai)'s free-tier models, so running this costs $0.

## Project structure

```
llm-council-app/
├── run.py                      # entry point -- start here, like `npm run dev`
├── config.py                   # app-wide settings (not secrets)
├── .env.example                # template for your .env file
├── requirements.txt            # Python dependencies (like package.json)
├── app/
│   ├── __init__.py             # application factory -- builds and configures the app
│   ├── routes/
│   │   ├── pages.py            # serves the chat HTML page
│   │   └── council.py          # the /council API endpoint (streaming)
│   ├── services/
│   │   └── council_service.py  # the actual council logic -- the "brain"
│   ├── templates/
│   │   └── index.html          # the chat page markup
│   └── static/
│       ├── css/style.css       # all styling
│       └── js/chat.js          # frontend logic: streaming, auto-download
└── scripts/
    └── terminal_report.py      # standalone CLI version, no server needed
```

## Setup

1. **Clone and enter the project:**
   ```
   git clone [GITHUB REPO URL]
   cd llm-council-app
   ```

2. **Create a virtual environment** (optional but recommended — keeps this project's dependencies separate from other Python projects on your machine):
   ```
   python3 -m venv venv
   source venv/bin/activate      # Mac/Linux
   venv\Scripts\activate         # Windows
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

## Using it without the web interface

If you just want a one-off HTML report from the command line, without running a server:

```
python scripts/terminal_report.py
```

Edit the `IDEA` variable near the top of that file first.

## How it works

Every idea you submit goes through three stages:

1. **Independent reviews**: five AI personas (VC, skeptical customer, engineer, security engineer, competitor) each review the idea separately, with no visibility into each other's answers.
2. **Anonymized peer review**: each persona's answer is shown to the others with identities stripped, and each one critiques and ranks the rest.
3. **Chairman synthesis**: a final model reads everything and writes one verdict: what the council agreed on, where it disagreed, and a concrete recommendation.

Full technical write-up: [link to hashnode article]
