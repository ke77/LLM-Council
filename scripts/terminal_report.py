"""
LLM Council — a free, runnable implementation
Based on Andrej Karpathy's LLM Council concept.

WHAT THIS SCRIPT DOES:
1. Sends your idea to multiple AI models, one after another (Stage 1)
2. Hides each model's identity and asks every model to critique
   and rank the others' answers (Stage 2 — anonymized peer review)
3. Sends everything to a "Chairman" model, which writes one final
   verdict that summarizes agreement, disagreement, and a
   recommended next step (Stage 3)
4. Saves the whole thing as a clean HTML report you can open in any
   browser

HOW TO USE IT:
1. Get a free API key at https://openrouter.ai (no credit card needed)
2. Paste your key into OPENROUTER_API_KEY below
3. Change IDEA to describe whatever you want the council to review
4. Run the script: python llm_council.py
5. Open the generated llm_council_report.html file in your browser

COST: $0. Every model below uses OpenRouter's free tier (the ":free"
models). Free models are rate-limited (about 20 requests/minute) but
that's far more than this script needs for one run.
"""

import requests
import time
import re


# STEP 1: PASTE YOUR OPENROUTER API KEY HERE
OPENROUTER_API_KEY = "sk-or-v1-PASTE-YOUR-KEY-HERE"

# STEP 2: DESCRIBE THE IDEA YOU WANT THE COUNCIL TO REVIEW
IDEA = """
We want to build a mobile app where households in urban Accra scan
recyclable items with their phone camera, earn points, and redeem
those points for mobile data or airtime. We partner with informal
waste collectors to handle pickup.
"""


# COUNCIL CONFIGURATION
# Each entry is one "expert." You can swap the model names for any
# other free model on openrouter.ai/models (filter by "free").

# NOTE ON MODEL NAMES: OpenRouter's free model lineup changes over time
# (models get added, renamed, or retired). The slugs below were live and
# free at the time this script was written. If you get a "model not
# found" or "404" error, go to https://openrouter.ai/models, filter by
# "Free", and swap in whatever current free model slug you like — the
# rest of the script doesn't need to change.
COUNCIL = [
    {
        "name": "Venture Capitalist",
        "model": "openai/gpt-oss-120b:free",
        "persona": (
            "You are a notoriously skeptical venture capitalist. You have "
            "personally lost money on three failed marketplace startups. "
            "Evaluate the idea's market size, unit economics, and whether "
            "it can become a venture-scale business or is just a nice "
            "lifestyle business. Be direct about flaws. Do not be polite "
            "for the sake of politeness."
        ),
    },
    {
        "name": "Skeptical Customer",
        "model": "z-ai/glm-4.5-air:free",
        "persona": (
            "You are a realistic potential user of this product, in the "
            "actual target market. You've heard a hundred pitches and have "
            "limited patience, money, and trust. In your own voice, explain "
            "the top 3 reasons you would NOT adopt this, and what would "
            "have to change for you to actually use or pay for it."
        ),
    },
    {
        "name": "Senior Engineer",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "persona": (
            "You are a senior software engineer reviewing this idea for "
            "technical feasibility. Identify the single hardest technical "
            "problem in this idea, explain why it's hard, and describe "
            "what breaks first if this had to scale to 10x its initial "
            "size."
        ),
    },
    {
        "name": "Security Engineer",
        "model": "openai/gpt-oss-20b:free",
        "persona": (
            "You are a security engineer threat-modeling this idea. List "
            "the top 3 concrete abuse vectors or data risks specific to "
            "this exact idea (not generic security advice). For each one, "
            "describe the realistic worst case."
        ),
    },
    {
        "name": "Competitor",
        "model": "google/gemma-4-31b-it:free",
        "persona": (
            "You run a well-funded company that could easily compete with "
            "this idea. Describe exactly how you would respond to this "
            "launch within 90 days, and explain why your response would "
            "hurt the original idea's chances."
        ),
    },
]

# The Chairman reads everything and writes the final verdict.
# It does not have to be one of the council members.
CHAIRMAN_MODEL = "openai/gpt-oss-120b:free"


# CORE FUNCTION: call one model on OpenRouter
def call_model(model: str, system_prompt: str, user_prompt: str) -> str:
    """
    Sends one request to OpenRouter and returns the model's text reply.
    If something goes wrong (rate limit, bad key, etc.) it returns a
    readable error message instead of crashing the whole script.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",  # required by OpenRouter
        "X-Title": "LLM Council Script",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)

        if response.status_code == 401:
            return ("[ERROR: Your API key was rejected. Double-check you "
                     "pasted it correctly into OPENROUTER_API_KEY at the "
                     "top of the script, with no extra spaces.]")

        if response.status_code == 404:
            return (f"[ERROR: The model '{model}' was not found. Free "
                     f"model names change over time — go to "
                     f"https://openrouter.ai/models, filter by 'Free', "
                     f"and swap in a current free model slug.]")

        if response.status_code == 429:
            return ("[ERROR: Rate limit hit. Free models allow about 20 "
                     "requests per minute. Wait a minute and try again, "
                     "or increase the time.sleep() value in this script.]")

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as error:
        return f"[ERROR calling {model}: {error}]"



# STAGE 1: Independent reviews
def stage1_independent_reviews(idea: str) -> dict:
    print("\n=== STAGE 1: Collecting independent reviews ===")
    responses = {}
    for member in COUNCIL:
        print(f"  Asking {member['name']} ({member['model']})...")
        answer = call_model(member["model"], member["persona"], idea)
        responses[member["name"]] = answer
        time.sleep(2)  # small pause to stay comfortably under rate limits
    return responses



# STAGE 2: Anonymize + peer review
def anonymize(responses: dict) -> tuple:
    """Strips names so models can't favor themselves or each other."""
    labels = {}
    anonymized_text = ""
    for i, (name, text) in enumerate(responses.items()):
        label = f"Response {chr(65 + i)}"  # Response A, B, C...
        labels[label] = name
        anonymized_text += f"\n\n--- {label} ---\n{text}"
    return anonymized_text, labels


def stage2_peer_review(idea: str, anonymized_text: str) -> dict:
    print("\n=== STAGE 2: Anonymized peer review ===")
    review_instructions = (
        "You are reviewing several independent expert critiques of a "
        "startup idea. The critiques are anonymized as Response A, "
        "Response B, etc. For each response, briefly note its strongest "
        "point and its weakest point. Then end with a section titled "
        "'FINAL RANKING:' listing the responses from strongest to "
        "weakest critique, like:\n"
        "FINAL RANKING:\n1. Response C\n2. Response A\n3. Response B"
    )
    user_prompt = (
        f"ORIGINAL IDEA:\n{idea}\n\n"
        f"CRITIQUES TO REVIEW:{anonymized_text}"
    )

    reviews = {}
    for member in COUNCIL:
        print(f"  Asking {member['name']} to review the council...")
        review = call_model(member["model"], review_instructions, user_prompt)
        reviews[member["name"]] = review
        time.sleep(2)
    return reviews



# STAGE 3: Chairman synthesis
def stage3_chairman_synthesis(idea: str, responses: dict, reviews: dict) -> str:
    print("\n=== STAGE 3: Chairman synthesis ===")
    chairman_instructions = (
        "You are the Chairman of an advisory council. You have been given "
        "the original idea, independent expert critiques, and peer "
        "reviews of those critiques. Write a final decision report with "
        "these exact sections:\n\n"
        "AGREEMENT ACROSS COUNCIL: (what most experts agree on)\n"
        "KEY DISAGREEMENT: (the most important place experts disagree, "
        "and why)\n"
        "MOST IMPORTANT OPEN QUESTION: (the one thing that, if answered, "
        "would change the verdict most)\n"
        "RECOMMENDATION: (a clear, specific next step — not vague "
        "encouragement)"
    )

    combined_text = f"ORIGINAL IDEA:\n{idea}\n\nINDEPENDENT CRITIQUES:\n"
    for name, text in responses.items():
        combined_text += f"\n--- {name} ---\n{text}\n"
    combined_text += "\nPEER REVIEWS:\n"
    for name, text in reviews.items():
        combined_text += f"\n--- {name}'s review of the others ---\n{text}\n"

    return call_model(CHAIRMAN_MODEL, chairman_instructions, combined_text)



# HTML REPORT HELPERS
def escape_html(text: str) -> str:
    """
    Models sometimes write things like '<', '>', or '&' in their answers.
    Browsers would try to interpret those as HTML tags, which breaks the
    page. This swaps them for safe equivalents before we write any HTML.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def inline_format(line: str) -> str:
    """
    Converts markdown-style emphasis inside a single line into HTML.
    Models write **bold** and *italic* constantly — without this step,
    those asterisks show up as literal characters on the page.
    """
    line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
    line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", line)
    return line


def text_to_html(text: str) -> str:
    """
    Converts a model's plain-text response into clean HTML. Handles the
    patterns LLMs actually produce:
      - **bold** / *italic*
      - numbered lists ("1. like this")
      - bullet lists ("- like this" or "* like this")
      - short ALL-CAPS or Title-Case "LABEL:" lines (e.g. "FINAL RANKING:")
        get turned into small headers instead of plain text
      - blank-line-separated paragraphs
    This is a small, dependency-free markdown-style renderer — not a full
    markdown library, just enough to handle real LLM output cleanly.
    """
    safe_text = escape_html(text.strip())
    lines = safe_text.split("\n")

    html_parts = []
    list_buffer = []
    list_type = None  # "ul" or "ol"

    def flush_list():
        nonlocal list_buffer, list_type
        if list_buffer:
            html_parts.append(f"<{list_type}>")
            for item in list_buffer:
                html_parts.append(f"<li>{inline_format(item)}</li>")
            html_parts.append(f"</{list_type}>")
            list_buffer = []
            list_type = None

    paragraph_buffer = []

    def flush_paragraph():
        if paragraph_buffer:
            joined = " ".join(paragraph_buffer).strip()
            if joined:
                html_parts.append(f"<p>{inline_format(joined)}</p>")
            paragraph_buffer.clear()

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            continue

        # A short ALL-CAPS line ending in ":", e.g. "FINAL RANKING:" or
        # "RECOMMENDATION:" -- treat as a mini-header. Regular sentences
        # that happen to end with a colon (like "because:") are left as
        # normal paragraph text, since they're usually intros to a list
        # below them, not standalone section labels.
        if re.match(r"^[A-Z][A-Z \-]{2,40}:$", line):
            flush_paragraph()
            flush_list()
            html_parts.append(f"<p class='label'>{inline_format(line)}</p>")
            continue

        numbered = re.match(r"^\d+[\.\)]\s+(.*)", line)
        bulleted = re.match(r"^[\-\*]\s+(.*)", line)

        if numbered:
            flush_paragraph()
            if list_type != "ol":
                flush_list()
                list_type = "ol"
            list_buffer.append(numbered.group(1))
            continue

        if bulleted:
            flush_paragraph()
            if list_type != "ul":
                flush_list()
                list_type = "ul"
            list_buffer.append(bulleted.group(1))
            continue

        flush_list()
        paragraph_buffer.append(line)

    flush_paragraph()
    flush_list()

    return "".join(html_parts)


def build_html_report(idea: str, responses: dict, reviews: dict, verdict: str) -> str:
    """Builds one self-contained HTML file — no external CSS or JS needed."""

    council_section = ""
    for name, text in responses.items():
        council_section += f"""
        <div class="card">
          <h3>{escape_html(name)}</h3>
          {text_to_html(text)}
        </div>"""

    review_section = ""
    for name, text in reviews.items():
        review_section += f"""
        <div class="card">
          <h3>{escape_html(name)}'s peer review</h3>
          {text_to_html(text)}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Council Report</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 24px 64px;
    line-height: 1.55;
    color: #222;
    background: #ffffff;
    font-size: 15px;
  }}
  h1 {{
    font-size: 1.5rem;
    margin-bottom: 4px;
  }}
  .subtitle {{
    color: #777;
    font-size: 0.85rem;
    margin-bottom: 28px;
  }}
  .idea-box {{
    background: #f6f6f6;
    border-left: 3px solid #999;
    padding: 14px 18px;
    margin-bottom: 36px;
    border-radius: 4px;
  }}
  .idea-box p {{
    margin: 6px 0 0 0;
  }}
  h2 {{
    font-size: 1.1rem;
    border-bottom: 1px solid #ddd;
    padding-bottom: 6px;
    margin-top: 40px;
    margin-bottom: 16px;
  }}
  .card {{
    margin: 14px 0;
    padding: 14px 18px;
    border: 1px solid #e3e3e3;
    border-radius: 6px;
  }}
  .card h3 {{
    margin-top: 0;
    margin-bottom: 8px;
    font-size: 0.95rem;
    color: #333;
  }}
  p {{
    margin: 0 0 8px 0;
    font-size: 0.93rem;
  }}
  p:last-child {{
    margin-bottom: 0;
  }}
  p.label {{
    font-weight: 600;
    margin-top: 12px;
    margin-bottom: 4px;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #555;
  }}
  ul, ol {{
    margin: 4px 0 10px 0;
    padding-left: 22px;
  }}
  li {{
    margin-bottom: 4px;
    font-size: 0.93rem;
  }}
  strong {{
    font-weight: 600;
  }}
  .verdict-box {{
    background: #fafaf5;
    border: 1px solid #d9d2b0;
    border-radius: 6px;
    padding: 18px 20px;
  }}
  footer {{
    margin-top: 48px;
    font-size: 0.75rem;
    color: #aaa;
    text-align: center;
  }}
</style>
</head>
<body>

  <h1>LLM Council Report</h1>
  <div class="subtitle">Generated by a 3-stage multi-model council, based on Andrej Karpathy's LLM Council concept.</div>

  <div class="idea-box">
    <strong>Idea reviewed:</strong>
    {text_to_html(idea)}
  </div>

  <h2>Stage 1 — Independent Reviews</h2>
  {council_section}

  <h2>Stage 2 — Anonymized Peer Review</h2>
  {review_section}

  <h2>Stage 3 — Chairman's Final Verdict</h2>
  <div class="verdict-box">
    {text_to_html(verdict)}
  </div>

  <footer>Generated with a free, open implementation of the LLM Council pattern.</footer>

</body>
</html>"""
    return html



# RUN THE FULL COUNCIL
def run_council(idea: str):
    responses = stage1_independent_reviews(idea)
    anonymized_text, _ = anonymize(responses)
    reviews = stage2_peer_review(idea, anonymized_text)
    verdict = stage3_chairman_synthesis(idea, responses, reviews)

    print("\n\n" + "=" * 60)
    print("FINAL COUNCIL VERDICT")
    print("=" * 60)
    print(verdict)

    # Save everything as a clean, readable HTML file you can open in
    # any browser, or share with your team.
    html_report = build_html_report(idea, responses, reviews, verdict)
    with open("llm_council_report.html", "w", encoding="utf-8") as f:
        f.write(html_report)

    print("\nFull report saved to llm_council_report.html — open it in your browser.")


if __name__ == "__main__":
    run_council(IDEA)