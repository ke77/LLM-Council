"""
HOW TO USE IT:
1. Get a free API key at https://openrouter.ai (no credit card needed)
2. Either set OPENROUTER_API_KEY in your .env file (recommended, see
   the main README), or paste it directly into API_KEY below
3. Edit IDEA and, optionally, SELECTED_ROLES below
4. Run from the project root: python scripts/terminal_report.py
5. Open the generated llm_council_report.html file in your browser

COST: $0 — uses OpenRouter's free-tier router (see DEFAULT_MODEL in
council_service.py).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from app.services import council_service

load_dotenv()


# CONFIGURE YOUR RUN HERE
API_KEY = os.environ.get("OPENROUTER_API_KEY", "sk-or-v1-PASTE-YOUR-KEY-HERE")

IDEA = """
We want to build a mobile app where households in urban Accra scan
recyclable items with their phone camera, earn points, and redeem
those points for mobile data or airtime. We partner with informal
waste collectors to handle pickup.
"""

# Which roles to run, by key. See council_service.ROLE_LIBRARY for the
# full list (venture_capitalist, skeptical_customer, senior_engineer,
# security_engineer, competitor, product_manager, marketing_strategist,
# economist, domain_expert, legal_regulatory). Leave as None to use
# the general-purpose defaults.
SELECTED_ROLES = None  # e.g. ["venture_capitalist", "domain_expert", "economist"]


def main():
    if not API_KEY or API_KEY == "sk-or-v1-PASTE-YOUR-KEY-HERE":
        print("No API key found. Set OPENROUTER_API_KEY in your .env file,")
        print("or paste a real key into API_KEY at the top of this script.")
        return

    def on_progress(message):
        print(f"  {message}")

    print("Running the council...")
    html_report = council_service.run_council(
        api_key=API_KEY,
        idea=IDEA,
        role_keys=SELECTED_ROLES,
        on_progress=on_progress,
    )

    output_path = "llm_council_report.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    print(f"\nDone. Report saved to {output_path} -- open it in your browser.")


if __name__ == "__main__":
    main()