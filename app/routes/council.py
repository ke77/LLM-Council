
import os
import json
from flask import Blueprint, request, Response
 
from app.services import council_service
 
council_bp = Blueprint("council", __name__)
 
 
@council_bp.route("/council", methods=["POST"])
def run_council():
    """
    The frontend's fetch() call hits this route. It streams back one
    small JSON object per line as the council works through its three
    stages, finishing with the complete HTML report.
 
    Each line looks like:
      {"type": "status", "message": "Consulting the Venture Capitalist..."}
      ...
      {"type": "done", "html": "<!DOCTYPE html>..."}
    """
    idea = request.json.get("idea", "").strip()
 
    # os.environ.get reads whatever load_dotenv() pulled in from your
    # .env file when the app started — the same value, read fresh on
    # every request, the same way you'd read process.env.OPENROUTER_API_KEY
    # in a Next.js API route.
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
 
    if not idea:
        return Response(
            json.dumps({"type": "error", "message": "Please enter an idea to review."}) + "\n",
            mimetype="application/json",
        )
 
    if not api_key:
        return Response(
            json.dumps({
                "type": "error",
                "message": (
                    "No OpenRouter API key found. Add OPENROUTER_API_KEY "
                    "to your .env file and restart the server."
                ),
            }) + "\n",
            mimetype="application/json",
        )
 
    def stream():
        # A generator function — it `yield`s pieces of output one at a
        # time instead of returning everything at once. Flask sends
        # each yielded piece to the browser immediately, which is the
        # actual mechanism behind the live status updates.
        try:
            yield json.dumps({"type": "status", "message": "Starting the council..."}) + "\n"
 
            responses = {}
            for member in council_service.COUNCIL:
                yield json.dumps({
                    "type": "status",
                    "message": f"Consulting the {member['name']}...",
                }) + "\n"
                answer = council_service.call_model(
                    api_key, member["model"], member["persona"], idea
                )
                responses[member["name"]] = answer
 
            yield json.dumps({
                "type": "status",
                "message": "Anonymizing responses for peer review...",
            }) + "\n"
            anonymized_text, _ = council_service.anonymize(responses)
 
            reviews = {}
            review_instructions = (
                "You are reviewing several independent expert critiques of a "
                "startup idea. The critiques are anonymized as Response A, "
                "Response B, etc. For each response, briefly note its "
                "strongest point and its weakest point. Then end with a "
                "section titled 'FINAL RANKING:' listing the responses from "
                "strongest to weakest critique."
            )
            user_prompt = f"ORIGINAL IDEA:\n{idea}\n\nCRITIQUES TO REVIEW:{anonymized_text}"
 
            for member in council_service.COUNCIL:
                yield json.dumps({
                    "type": "status",
                    "message": f"{member['name']} is reviewing the council's answers...",
                }) + "\n"
                review = council_service.call_model(
                    api_key, member["model"], review_instructions, user_prompt
                )
                reviews[member["name"]] = review
 
            yield json.dumps({
                "type": "status",
                "message": "The Chairman is synthesizing the final verdict...",
            }) + "\n"
            verdict = council_service.stage3_chairman_synthesis(
                api_key, idea, responses, reviews
            )
 
            yield json.dumps({"type": "status", "message": "Building your report..."}) + "\n"
            html_report = council_service.build_html_report(idea, responses, reviews, verdict)
 
            yield json.dumps({"type": "done", "html": html_report}) + "\n"
 
        except Exception as error:
            yield json.dumps({
                "type": "error",
                "message": f"Something went wrong: {error}",
            }) + "\n"
 
    return Response(stream(), mimetype="application/json")
 