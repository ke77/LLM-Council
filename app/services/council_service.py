# This file contains every function that actually runs the council:
# calling models, anonymizing responses, running peer review, getting
# the chairman's verdict, and building the final HTML report.



import requests
import time
import re
 
# ----------------------------------------------------------------------
# MODEL SELECTION
# ----------------------------------------------------------------------
# Hardcoding specific free model slugs (like "openai/gpt-oss-120b:free")
# is fragile -- OpenRouter's free model lineup changes week to week, and
# a slug that's live today can 404 next week. "openrouter/free" sidesteps
# this entirely: it's a router OpenRouter manages themselves that picks
# a live, working free model for every single request automatically.
# This is the single setting that keeps this app genuinely $0 and
# working without you having to babysit model names.
DEFAULT_MODEL = "openrouter/free"
 
# ----------------------------------------------------------------------
# ROLE LIBRARY
# ----------------------------------------------------------------------
# Every persona the council can use. The user picks which ones actually
# run for their specific idea -- this is what fixes the "I got a
# Security Engineer reviewing a non-software idea" problem. Each role
# is tagged so the frontend can show sensible defaults based on what
# kind of idea was submitted, without forcing irrelevant roles every time.
ROLE_LIBRARY = {
    "venture_capitalist": {
        "name": "Venture Capitalist",
        "description": "Market size, unit economics, and venture scalability.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a notoriously skeptical venture capitalist. You have "
            "personally lost money on three failed startups. Evaluate the "
            "idea's market size, unit economics, and whether it can become "
            "a venture-scale business or is just a nice lifestyle business. "
            "Be direct about flaws. Do not be polite for the sake of "
            "politeness."
        ),
    },
    "skeptical_customer": {
        "name": "Skeptical Customer",
        "description": "The realistic end user who has heard a hundred pitches.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a realistic potential user of this product or idea, "
            "in its actual target market. You've heard a hundred pitches "
            "and have limited patience, money, and trust. In your own "
            "voice, explain the top 3 reasons you would NOT adopt this, "
            "and what would have to change for you to actually use or pay "
            "for it."
        ),
    },
    "senior_engineer": {
        "name": "Senior Engineer",
        "description": "Technical feasibility and what breaks at scale. Best for software/product ideas.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a senior software engineer reviewing this idea for "
            "technical feasibility. Identify the single hardest technical "
            "problem in this idea, explain why it's hard, and describe "
            "what breaks first if this had to scale to 10x its initial "
            "size."
        ),
    },
    "security_engineer": {
        "name": "Security Engineer",
        "description": "Data risks and abuse vectors. Best for software/product ideas handling user data.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a security engineer threat-modeling this idea. List "
            "the top 3 concrete abuse vectors or data risks specific to "
            "this exact idea (not generic security advice). For each one, "
            "describe the realistic worst case."
        ),
    },
    "competitor": {
        "name": "Competitor",
        "description": "A well-funded rival deciding how to respond.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You run a well-funded company that could easily compete with "
            "this idea. Describe exactly how you would respond to this "
            "launch within 90 days, and explain why your response would "
            "hurt the original idea's chances."
        ),
    },
    "product_manager": {
        "name": "Product Manager",
        "description": "Scope and sequencing -- what the smallest version looks like.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a product manager reviewing this idea. Focus on "
            "scope and sequencing: what is the smallest version of this "
            "that could be tested or launched, what should explicitly be "
            "left out of a first version, and what's the biggest scope "
            "risk you see."
        ),
    },
    "marketing_strategist": {
        "name": "Marketing Strategist",
        "description": "Who hears about this, through what channel, and why they'd care.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a blunt marketing strategist. Identify exactly who "
            "would realistically hear about this idea, through what "
            "channel, and whether the positioning is differentiated or "
            "generic. Call out if this relies on 'build it and they will "
            "come' thinking."
        ),
    },
    "economist": {
        "name": "Economist",
        "description": "System-level incentives and second-order effects.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are an economist analyzing this idea at the system "
            "level. Who benefits, who is left out, and what does the "
            "equilibrium look like once everyone adapts to it? Identify "
            "the most likely second-order effect the founder hasn't "
            "considered."
        ),
    },
    "domain_expert": {
        "name": "Domain Expert",
        "description": "A generalist subject-matter expert in whatever field the idea actually belongs to.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a deeply experienced subject-matter expert in "
            "whatever specific field or industry this idea belongs to "
            "(infer the field from the idea itself -- it may not be "
            "software). Evaluate the idea on the merits and realities "
            "specific to that field, not generic startup advice. Be "
            "direct about flaws specific to that domain."
        ),
    },
    "legal_regulatory": {
        "name": "Legal & Regulatory Reviewer",
        "description": "Compliance, liability, and regulatory exposure.",
        "model": DEFAULT_MODEL,
        "persona": (
            "You are a legal and regulatory reviewer. Identify the most "
            "significant compliance, liability, or regulatory exposure "
            "this idea creates, and explain in plain language why it "
            "matters and what mitigates it. You are not a lawyer and "
            "should say so, but give the most informed read you can."
        ),
    },
}
 
# Sensible defaults if the user submits without picking any roles --
# kept general-purpose rather than software-specific, since this app
# isn't limited to software ideas.
DEFAULT_ROLE_KEYS = [
    "venture_capitalist",
    "skeptical_customer",
    "domain_expert",
    "competitor",
    "economist",
]
 
# The Chairman reads everything and writes the final verdict.
# It does not have to be one of the council members.
CHAIRMAN_MODEL = DEFAULT_MODEL
 
 
def get_council_for_roles(role_keys: list) -> list:
    """
    Takes a list of role keys the user selected (e.g. from checkboxes in
    the frontend) and returns the actual council member definitions.
    Falls back to DEFAULT_ROLE_KEYS if the list is empty or invalid, so
    the app never runs a council with zero members.
    """
    if not role_keys:
        role_keys = DEFAULT_ROLE_KEYS
 
    council = [ROLE_LIBRARY[key] for key in role_keys if key in ROLE_LIBRARY]
 
    if not council:
        council = [ROLE_LIBRARY[key] for key in DEFAULT_ROLE_KEYS]
 
    return council
 
 
# ----------------------------------------------------------------------
# CORE FUNCTION: call one model on OpenRouter
# ----------------------------------------------------------------------
def call_model(api_key: str, model: str, system_prompt: str, user_prompt: str, retries: int = 2) -> str:
    """
    Sends one request to OpenRouter and returns the model's text reply.
    If something goes wrong (rate limit, bad key, etc.) it returns a
    readable error message instead of crashing.
 
    retries: free models occasionally return a 429 (rate limit) under
    real traffic, even well under the per-minute cap, because OpenRouter
    is balancing load across many users sharing the same free pool. A
    short wait-and-retry clears most of these without any code changes
    on your end -- this is normal free-tier behavior, not a bug.
 
    Note this takes api_key as an argument instead of reading a global
    constant -- that's what makes this function safe to reuse in a web
    server, where the key has to come from somewhere other than a
    hardcoded line at the top of the file.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",  # required by OpenRouter
        "X-Title": "LLM Council App",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
 
    for attempt in range(retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
 
            if response.status_code == 401:
                return ("[ERROR: Your API key was rejected. Double-check it "
                         "was entered correctly, with no extra spaces.]")
 
            if response.status_code == 404:
                return (f"[ERROR: The model '{model}' was not found. If "
                         f"you changed DEFAULT_MODEL away from "
                         f"'openrouter/free', check https://openrouter.ai/models "
                         f"for a current free slug.]")
 
            if response.status_code == 429:
                if attempt < retries:
                    time.sleep(5 * (attempt + 1))  # back off a bit longer each retry
                    continue
                return ("[ERROR: Rate limit hit and retries exhausted. "
                         "Free models are shared across many users -- wait "
                         "a minute and try again.]")
 
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            if attempt < retries:
                continue
            return f"[ERROR: {model} timed out after {retries + 1} attempts.]"
        except Exception as error:
            return f"[ERROR calling {model}: {error}]"
 
    return "[ERROR: Unexpected retry loop exit.]"
 
 
# ----------------------------------------------------------------------
# STAGE 1: Independent reviews
# ----------------------------------------------------------------------
def stage1_independent_reviews(api_key: str, idea: str, council: list, on_progress=None) -> dict:
    """
    on_progress is an optional function we call after each step, so
    whatever is using this (a terminal script, a web server) can show
    live progress. If you don't pass one, it's simply skipped — that's
    what `if on_progress:` means below.
 
    council: the list of role dicts to actually run, e.g. from
    get_council_for_roles(). Passed in explicitly rather than read off
    a global, since different requests can now use different roles.
    """
    responses = {}
    for member in council:
        if on_progress:
            on_progress(f"Consulting the {member['name']}...")
        answer = call_model(api_key, member["model"], member["persona"], idea)
        responses[member["name"]] = answer
        time.sleep(2)  # small pause to stay comfortably under rate limits
    return responses
 
 
# ----------------------------------------------------------------------
# STAGE 2: Anonymize + peer review
# ----------------------------------------------------------------------
def anonymize(responses: dict) -> tuple:
    """Strips names so models can't favor themselves or each other."""
    labels = {}
    anonymized_text = ""
    for i, (name, text) in enumerate(responses.items()):
        label = f"Response {chr(65 + i)}"  # Response A, B, C...
        labels[label] = name
        anonymized_text += f"\n\n--- {label} ---\n{text}"
    return anonymized_text, labels
 
 
def stage2_peer_review(api_key: str, idea: str, anonymized_text: str, council: list, on_progress=None) -> dict:
    review_instructions = (
        "You are reviewing several independent expert critiques of an "
        "idea. The critiques are anonymized as Response A, Response B, "
        "etc. For each response, briefly note its strongest point and "
        "its weakest point. Then end with a section titled "
        "'FINAL RANKING:' listing the responses from strongest to "
        "weakest critique, like:\n"
        "FINAL RANKING:\n1. Response C\n2. Response A\n3. Response B"
    )
    user_prompt = (
        f"ORIGINAL IDEA:\n{idea}\n\n"
        f"CRITIQUES TO REVIEW:{anonymized_text}"
    )
 
    reviews = {}
    for member in council:
        if on_progress:
            on_progress(f"{member['name']} is reviewing the council's answers...")
        review = call_model(api_key, member["model"], review_instructions, user_prompt)
        reviews[member["name"]] = review
        time.sleep(2)
    return reviews
 
 
# ----------------------------------------------------------------------
# STAGE 3: Chairman synthesis
# ----------------------------------------------------------------------
def stage3_chairman_synthesis(api_key: str, idea: str, responses: dict, reviews: dict, on_progress=None) -> str:
    if on_progress:
        on_progress("The Chairman is synthesizing the final verdict...")
 
    chairman_instructions = (
        "You are the Chairman of an advisory council. You have been given "
        "an idea, independent expert critiques of it, and peer reviews of "
        "those critiques. Write a final decision report with these exact "
        "sections:\n\n"
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
 
    return call_model(api_key, CHAIRMAN_MODEL, chairman_instructions, combined_text)
 
 
# ----------------------------------------------------------------------
# HTML REPORT HELPERS
# ----------------------------------------------------------------------
def normalize_unicode_punctuation(text: str) -> str:
    """
    Models sometimes write 'fancy' Unicode punctuation -- non-breaking
    hyphens (‑), en/em dashes used as hyphens, curly quotes, etc.
    Browsers render these fine, but they can look inconsistent or odd
    mixed in with normal text (e.g. "30‑day" instead of "30-day"). This
    normalizes the common ones back to their plain ASCII equivalents.
    """
    replacements = {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2026": "...",  # ellipsis
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    return text
 
 
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
 
 
def is_table_row(line: str) -> bool:
    """A markdown table row looks like: | col 1 | col 2 | col 3 |"""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2
 
 
def is_table_separator(line: str) -> bool:
    """The row right under table headers, like: |------|------|"""
    stripped = line.strip()
    if not is_table_row(stripped):
        return False
    inner = stripped.strip("|")
    cells = inner.split("|")
    return all(re.match(r"^:?-+:?$", cell.strip()) for cell in cells if cell.strip())
 
 
def parse_table_row(line: str) -> list:
    """Splits '| a | b | c |' into ['a', 'b', 'c'], trimming whitespace."""
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]
 
 
def render_table(table_lines: list) -> str:
    """
    Converts a block of consecutive markdown table lines into real
    HTML <table> markup. Expects the first line to be headers, the
    second to be the '|---|---|' separator (which we just skip over),
    and every line after that to be a data row.
    """
    if not table_lines:
        return ""
 
    header_cells = parse_table_row(table_lines[0])
    body_lines = table_lines[2:] if len(table_lines) > 1 and is_table_separator(table_lines[1]) else table_lines[1:]
 
    html = ["<table>", "<thead><tr>"]
    for cell in header_cells:
        html.append(f"<th>{inline_format(escape_html(cell))}</th>")
    html.append("</tr></thead><tbody>")
 
    for row_line in body_lines:
        if not is_table_row(row_line):
            continue
        cells = parse_table_row(row_line)
        html.append("<tr>")
        for cell in cells:
            html.append(f"<td>{inline_format(escape_html(cell))}</td>")
        html.append("</tr>")
 
    html.append("</tbody></table>")
    return "".join(html)
 
 
def text_to_html(text: str) -> str:
    """
    Converts a model's plain-text response into clean HTML. Handles the
    patterns LLMs actually produce:
      - **bold** / *italic*
      - numbered lists ("1. like this")
      - bullet lists ("- like this" or "* like this")
      - markdown tables ("| col | col |" blocks)
      - short ALL-CAPS "LABEL:" lines (e.g. "FINAL RANKING:") get turned
        into small headers instead of plain text
      - blank-line-separated paragraphs
 
    Note: escape_html is intentionally NOT called on the raw text up
    front anymore. Table cells and inline text are escaped individually
    inside their own handlers (render_table, inline_format callers)
    instead, since escaping the whole blob first made it impossible to
    reliably detect "|" table syntax afterward in edge cases with
    HTML-like characters inside cells.
    """
    lines = normalize_unicode_punctuation(text.strip()).split("\n")
 
    html_parts = []
    list_buffer = []
    list_type = None  # "ul" or "ol"
    table_buffer = []
 
    def flush_list():
        nonlocal list_buffer, list_type
        if list_buffer:
            html_parts.append(f"<{list_type}>")
            for item in list_buffer:
                html_parts.append(f"<li>{inline_format(escape_html(item))}</li>")
            html_parts.append(f"</{list_type}>")
            list_buffer = []
            list_type = None
 
    def flush_table():
        nonlocal table_buffer
        if table_buffer:
            html_parts.append(render_table(table_buffer))
            table_buffer = []
 
    paragraph_buffer = []
 
    def flush_paragraph():
        if paragraph_buffer:
            joined = " ".join(paragraph_buffer).strip()
            if joined:
                html_parts.append(f"<p>{inline_format(escape_html(joined))}</p>")
            paragraph_buffer.clear()
 
    for raw_line in lines:
        line = raw_line.strip()
 
        if not line:
            flush_paragraph()
            flush_table()
            continue
 
        if is_table_row(line):
            flush_paragraph()
            flush_list()
            table_buffer.append(line)
            continue
        else:
            flush_table()
 
        if re.match(r"^[A-Z][A-Z \-]{2,40}:$", line):
            flush_paragraph()
            flush_list()
            html_parts.append(f"<p class='label'>{inline_format(escape_html(line))}</p>")
            continue
 
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)) + 2, 6)  # ## -> h4, ### -> h5, capped at h6
            heading_text = heading.group(2)
            html_parts.append(f"<h{level}>{inline_format(escape_html(heading_text))}</h{level}>")
            continue
 
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line):
            flush_paragraph()
            flush_list()
            html_parts.append("<hr>")
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
    flush_table()
 
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
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 14px 0;
    font-size: 0.88rem;
  }}
  th, td {{
    text-align: left;
    padding: 6px 10px;
    border: 1px solid #e3e3e3;
  }}
  th {{
    background: #f6f6f6;
    font-weight: 600;
  }}
  h4, h5, h6 {{
    margin: 16px 0 8px 0;
    color: #222;
    font-weight: 600;
  }}
  h4 {{ font-size: 1.0rem; }}
  h5 {{ font-size: 0.95rem; }}
  h6 {{ font-size: 0.9rem; }}
  hr {{
    border: none;
    border-top: 1px solid #e3e3e3;
    margin: 16px 0;
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
 
 
# ----------------------------------------------------------------------
# RUN THE FULL COUNCIL (used by both the terminal script and the web app)
# ----------------------------------------------------------------------
def run_council(api_key: str, idea: str, role_keys: list = None, on_progress=None) -> str:
    """
    Runs all 3 stages back to back and returns the final HTML report as
    a string. on_progress, if given, is called with a short status
    message before each major step — this is what lets the web app
    show live "Consulting the Venture Capitalist..." style updates.
 
    role_keys: which roles (from ROLE_LIBRARY) to actually run. If
    omitted, get_council_for_roles() falls back to DEFAULT_ROLE_KEYS.
    """
    council = get_council_for_roles(role_keys)
 
    responses = stage1_independent_reviews(api_key, idea, council, on_progress)
    anonymized_text, _ = anonymize(responses)
    reviews = stage2_peer_review(api_key, idea, anonymized_text, council, on_progress)
    verdict = stage3_chairman_synthesis(api_key, idea, responses, reviews, on_progress)
 
    if on_progress:
        on_progress("Building your report...")
 
    return build_html_report(idea, responses, reviews, verdict)