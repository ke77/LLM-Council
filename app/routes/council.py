import os
import json
from flask import Blueprint, request, Response, jsonify

from app.services import council_service

council_bp = Blueprint("council", __name__)


@council_bp.route("/roles", methods=["GET"])
def get_roles():
    """
    Returns every selectable role so the frontend can render
    checkboxes, along with which ones are selected by default. The
    frontend calls this once when the page loads.
    """
    roles = [
        {
            "key": key,
            "name": role["name"],
            "description": role["description"],
            "default": key in council_service.DEFAULT_ROLE_KEYS,
        }
        for key, role in council_service.ROLE_LIBRARY.items()
    ]
    return jsonify({"roles": roles})


@council_bp.route("/council", methods=["POST"])
def run_council():
    """
    The frontend's fetch() call hits this route. It streams back one
    small JSON object per line as the council works through its three
    stages.

    Each line looks like one of:
      {"type": "status",   "message": "Consulting the Venture Capitalist..."}
      {"type": "rejected", "message": "That doesn't look like an idea..."}
      {"type": "verdict",  "text": "AGREEMENT ACROSS COUNCIL: ..."}
      {"type": "done",     "html": "<!DOCTYPE html>..."}
      {"type": "error",    "message": "..."}

    "rejected" means the idea was caught by validation (gibberish,
    too short, or off-topic) before any model was ever called for the
    actual council -- this is what protects free-tier rate limits from
    being burned on junk input. The frontend shows this as a small
    toast, not a chat message.

    "verdict" carries the chairman's plain-text answer, meant to be
    printed straight into the chat like a normal AI response. "done"
    carries the full HTML report, meant only for the separate download
    button -- the frontend does not print this one into the chat.
    """
    body = request.json or {}
    idea = body.get("idea", "").strip()
    role_keys = body.get("roles", [])  # list of role keys the user checked

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


    # IDEA VALIDATION -- runs BEFORE any council member is called.
    # Layer 1 is instant and free (no network call). If it passes,
    # layer 2 spends exactly ONE cheap model call to catch anything
    # that's coherent text but still not an idea worth reviewing
    # ("what's the weather", "tell me a joke", etc). Either layer
    # rejecting means we never touch the 11+ calls a real council run
    # would cost -- this is the actual rate-limit/cost protection.
    rejection_reason = council_service.layer1_quick_reject(idea)
    if rejection_reason is None:
        rejection_reason = council_service.validate_idea_with_model(api_key, idea)

    if rejection_reason:
        return Response(
            json.dumps({"type": "rejected", "message": rejection_reason}) + "\n",
            mimetype="application/json",
        )

    council = council_service.get_council_for_roles(role_keys)

    def stream():
        try:
            yield json.dumps({"type": "status", "message": "Starting the council..."}) + "\n"

            responses = {}
            for member in council:
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
                "You are reviewing several independent expert critiques of "
                "an idea. The critiques are anonymized as Response A, "
                "Response B, etc. For each response, briefly note its "
                "strongest point and its weakest point. Then end with a "
                "section titled 'FINAL RANKING:' listing the responses from "
                "strongest to weakest critique."
            )
            user_prompt = f"ORIGINAL IDEA:\n{idea}\n\nCRITIQUES TO REVIEW:{anonymized_text}"

            for member in council:
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

            # Send the plain verdict text FIRST, separately from the
            # full HTML report. This is what lets the frontend print
            # it straight into the chat bubble like a normal answer,
            # instead of only ever showing a "your file is ready" card.
            yield json.dumps({"type": "verdict", "text": verdict}) + "\n"

            html_report = council_service.build_html_report(idea, responses, reviews, verdict)
            yield json.dumps({"type": "done", "html": html_report}) + "\n"

        except Exception as error:
            yield json.dumps({
                "type": "error",
                "message": f"Something went wrong: {error}",
            }) + "\n"

    return Response(stream(), mimetype="application/json")