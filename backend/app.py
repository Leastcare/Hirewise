import io
import logging
import os
import pickle
import re

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pdfminer.high_level import extract_text as pdf_extract_text

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hirewise")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "30 per hour"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# Model load (fail loudly at startup — not silently at request time)
# ---------------------------------------------------------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "scam_detector.pkl")
try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    logger.info("Scam detector model loaded from %s", MODEL_PATH)
except Exception as exc:
    logger.critical("Failed to load model from %s: %s", MODEL_PATH, exc)
    raise

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_INPUT_CHARS = 10_000

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "aol.com", "proton.me", "protonmail.com",
}

SCAM_KEYWORDS = [
    "registration fee", "security deposit", "processing fee", "payment",
    "deposit", "pay immediately", "advance fee", "training fee",
    "registration amount", "refundable fee", "pay before joining",
    "screening fee", "onboarding fee", "pay the amount",
]

URGENCY_KEYWORDS = [
    "urgent", "immediately", "within 24 hours", "as soon as possible",
    "limited time", "today itself", "next 2 hours", "act now",
    "final deadline", "respond today", "confirm immediately",
]

POSITIVE_PHRASES = [
    "we are pleased to offer",
    "please review",
    "for any questions",
    "human resources",
    "hiring team",
    "offer of employment",
    "subject to company policy",
    "payroll deductions",
    "joining date",
    "reporting manager",
    "employment is contingent",
]

SUSPICIOUS_PHRASES = [
    "selected without interview",
    "guaranteed job",
    "instant joining",
    "no interview required",
    "pay and confirm",
    "transfer the amount",
    "whatsapp only",
    "telegram",
    "kindly pay",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Light normalization applied at inference time to bridge the
    training-data / offer-letter domain gap."""
    text = text.strip()
    # Collapse excessive whitespace / newlines
    text = re.sub(r"\s+", " ", text)
    return text


def extract_email(text: str):
    match = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", text)
    return match.group(0) if match else None


def extract_domain(email: str):
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].lower()


def has_salary_info(text: str) -> bool:
    salary_patterns = [
        r"rs\.?\s?[\d,]+",
        r"inr\s?[\d,]+",
        r"ctc",
        r"annual compensation",
        r"per annum",
        r"per year",
        r"salary",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in salary_patterns)


def has_job_role(text: str) -> bool:
    role_keywords = [
        "software engineer", "developer", "analyst", "associate", "manager",
        "executive", "intern", "consultant", "engineer", "specialist",
        "coordinator", "designer", "support", "administrator", "data entry",
    ]
    lower = text.lower()
    return any(role in lower for role in role_keywords)


def has_person_name_greeting(text: str) -> bool:
    patterns = [
        r"dear\s+[A-Z][a-z]+\s+[A-Z][a-z]+",
        r"dear\s+[A-Z][a-z]+",
    ]
    return any(re.search(p, text) for p in patterns)


def has_company_style_signoff(text: str) -> bool:
    signoff_patterns = [
        "best regards", "regards", "sincerely",
        "hiring team", "human resources", "hr team",
        "talent acquisition", "recruitment team",
    ]
    lower = text.lower()
    return any(p in lower for p in signoff_patterns)


def seems_company_domain(domain: str) -> bool:
    if not domain:
        return False
    if domain in PUBLIC_EMAIL_DOMAINS:
        return False
    return "." in domain and len(domain.split(".")) >= 2


def clamp_score(value, low=0, high=95) -> int:
    return max(low, min(high, round(value)))


def get_verdict(score: int) -> dict:
    if score >= 75:
        return {"label": "Likely legitimate offer", "color": "green"}
    if score >= 40:
        return {"label": "Needs review before you trust it", "color": "yellow"}
    return {"label": "High scam risk detected", "color": "red"}


def build_verification_message(
    detected_domain, detected_email, flags, verdict_color
) -> str:
    """
    Compose a verification message tailored to the detected signals.
    The message is always polite and professional; specific paragraphs
    are added when particular risk signals are present.
    """
    flag_titles = {f["title"] for f in flags}
    has_fee_flag = "Payment request detected" in flag_titles
    has_domain_flag = "Public email domain detected" in flag_titles
    has_urgency_flag = "Urgency language detected" in flag_titles

    intro = (
        "Hello,\n\n"
        "I recently received an offer letter / hiring message that appears to "
        "originate from your organisation and would like to verify its authenticity "
        "before proceeding further."
    )

    body_parts = []

    if has_domain_flag and detected_email:
        body_parts.append(
            f"The message was sent from {detected_email}, which is a personal "
            "email address rather than an official company domain. Could you please "
            "confirm whether this email address is associated with your HR or "
            "recruitment team?"
        )

    if has_fee_flag:
        body_parts.append(
            "The offer requests an upfront payment (registration fee, security "
            "deposit, or similar). Could you please confirm whether your company "
            "policy requires any payment from candidates before joining? Legitimate "
            "employers typically do not charge candidates at any stage."
        )

    if has_urgency_flag:
        body_parts.append(
            "The message urges an urgent response within a very short timeframe. "
            "Could you please confirm the actual deadline for accepting this offer?"
        )

    if not body_parts:
        if detected_domain:
            body_parts.append(
                f"The offer was received from a sender at {detected_domain}. "
                "Could you please confirm this is your official contact domain and "
                "that the offer is genuine?"
            )
        else:
            body_parts.append(
                "Could you please confirm that this offer was officially issued "
                "by your organisation and provide an official point of contact for "
                "any follow-up questions?"
            )

    closing = (
        "I appreciate your time and look forward to a confirmed response "
        "through your official channels.\n\n"
        "Thank you."
    )

    return intro + "\n\n" + "\n\n".join(body_parts) + "\n\n" + closing


# ---------------------------------------------------------------------------
# AI review
# ---------------------------------------------------------------------------

def get_ai_review_and_signal(offer_text, flags, confidence_score, detected_domain, verdict_label):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set — skipping AI review")
        return None, "unavailable"

    prompt = (
        f"You are a cautious job-offer scam review assistant.\n\n"
        f"Offer text:\n{offer_text}\n\n"
        f"Detected domain: {detected_domain}\n\n"
        f"Detected red flags: {flags}\n\n"
        f"Current score before AI adjustment: {confidence_score}\n\n"
        f"Current verdict: {verdict_label}\n\n"
        "Your tasks:\n"
        "1. Write a short review in exactly 3 bullet points:\n"
        "   - main concerns\n"
        "   - what looks safe or unsafe\n"
        "   - what the user should verify next\n\n"
        "2. At the very end, add one final line in this exact format:\n"
        "AI_SIGNAL: low_risk\n"
        "or\nAI_SIGNAL: mixed\n"
        "or\nAI_SIGNAL: high_risk\n\n"
        "Rules:\n"
        "- Do not claim the offer is definitely legitimate.\n"
        "- Keep the whole response under 140 words.\n"
        "- Be practical and conservative."
    )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://hirewise-backend-r748.onrender.com",
                "X-OpenRouter-Title": "HireWise",
            },
            json={
                "model": "openrouter/auto",
                "messages": [
                    {
                        "role": "system",
                        "content": "You explain scam risk clearly, conservatively, and briefly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error("OpenRouter error %s: %s", resp.status_code, resp.text)
            return None, "unavailable"

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            logger.error("OpenRouter returned no choices: %s", data)
            return None, "unavailable"

        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            logger.error("OpenRouter returned empty content: %s", data)
            return None, "unavailable"

        lower_content = content.lower()
        if "ai_signal: low_risk" in lower_content:
            ai_signal = "low_risk"
        elif "ai_signal: high_risk" in lower_content:
            ai_signal = "high_risk"
        else:
            ai_signal = "mixed"

        cleaned_review = re.sub(
            r"AI_SIGNAL:\s*(low_risk|mixed|high_risk)", "", content, flags=re.IGNORECASE
        ).strip()

        return cleaned_review, ai_signal

    except Exception as exc:
        logger.error("AI review error: %s", exc)
        return None, "unavailable"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return "HireWise backend is running"


@app.route("/api/ping")
def ping():
    """Lightweight wake-up endpoint used by the frontend on page load."""
    return jsonify({"status": "ok"})


@app.route("/api/extract", methods=["POST"])
@limiter.limit("10 per minute")
def extract():
    """Accept a PDF or plain-text file and return its extracted text."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename or ""

    if file.content_length and file.content_length > 2 * 1024 * 1024:
        return jsonify({"error": "File too large (max 2 MB)"}), 400

    raw = file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        return jsonify({"error": "File too large (max 2 MB)"}), 400

    try:
        if filename.lower().endswith(".pdf"):
            text = pdf_extract_text(io.BytesIO(raw))
        else:
            text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("File extraction error: %s", exc)
        return jsonify({"error": "Could not extract text from file"}), 500

    text = text.strip()[:MAX_INPUT_CHARS]
    logger.info("Extracted %d chars from uploaded file '%s'", len(text), filename)
    return jsonify({"text": text})


@app.route("/api/analyze", methods=["POST"])
@limiter.limit("10 per minute")
def analyze():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Request body must be JSON"}), 400

    offer_text = payload.get("offerText", "").strip()

    if not offer_text:
        return jsonify({"error": "No offer text provided"}), 400

    if len(offer_text) > MAX_INPUT_CHARS:
        return jsonify({
            "error": f"Input too long. Please limit to {MAX_INPUT_CHARS} characters."
        }), 400

    # Normalize for inference — bridges the training/offer-letter domain gap
    normalized = normalize_text(offer_text)

    detected_email = extract_email(offer_text)
    detected_domain = extract_domain(detected_email)
    lower_text = offer_text.lower()

    flags = []
    legitimacy_signals = []
    risk_penalty = 0
    legitimacy_bonus = 0

    # --- Risk signals ---
    if any(kw in lower_text for kw in SCAM_KEYWORDS):
        flags.append({
            "title": "Payment request detected",
            "detail": "The message asks for money or mentions fees, which is a common scam signal.",
            "severity": "high",
        })
        risk_penalty += 34

    if any(kw in lower_text for kw in URGENCY_KEYWORDS):
        flags.append({
            "title": "Urgency language detected",
            "detail": "The message creates pressure to act quickly, which is a known risk signal.",
            "severity": "medium",
        })
        risk_penalty += 14

    if any(ph in lower_text for ph in SUSPICIOUS_PHRASES):
        flags.append({
            "title": "Suspicious hiring wording detected",
            "detail": "The message uses wording commonly seen in unsafe or misleading hiring messages.",
            "severity": "high",
        })
        risk_penalty += 18

    if detected_domain in PUBLIC_EMAIL_DOMAINS:
        flags.append({
            "title": "Public email domain detected",
            "detail": "The sender uses a public email domain instead of a company domain.",
            "severity": "medium",
        })
        risk_penalty += 18
    elif seems_company_domain(detected_domain):
        legitimacy_signals.append("The email uses a company-style domain instead of a public mailbox.")
        legitimacy_bonus += 12

    if "congratulations" in lower_text and "selected" in lower_text:
        flags.append({
            "title": "Premature selection language",
            "detail": "The message strongly claims selection early, which can sometimes be suspicious.",
            "severity": "low",
        })
        risk_penalty += 8

    # --- Legitimacy signals ---
    if has_person_name_greeting(offer_text):
        legitimacy_signals.append("The letter includes a personalized greeting.")
        legitimacy_bonus += 8

    if has_salary_info(offer_text):
        legitimacy_signals.append("The offer includes compensation details.")
        legitimacy_bonus += 8

    if has_job_role(offer_text):
        legitimacy_signals.append("The letter clearly mentions a job role.")
        legitimacy_bonus += 6

    if has_company_style_signoff(offer_text):
        legitimacy_signals.append("The letter uses a professional closing or HR-style sign-off.")
        legitimacy_bonus += 6

    if any(ph in lower_text for ph in POSITIVE_PHRASES):
        legitimacy_signals.append("The message uses professional offer-letter wording.")
        legitimacy_bonus += 5

    # --- ML model (reduced weight: 0.55 vs old 0.72 to compensate for domain mismatch) ---
    scam_probability = model.predict_proba([normalized])[0][1]
    base_confidence_score = round((1 - scam_probability) * 100)

    score_after_model = (base_confidence_score * 0.55) + 20
    score_after_rules = score_after_model - risk_penalty + legitimacy_bonus

    if risk_penalty >= 45 and legitimacy_bonus <= 10:
        score_after_rules -= 10

    if legitimacy_bonus >= 28 and risk_penalty == 0:
        score_after_rules += 8

    pre_ai_score = clamp_score(score_after_rules)
    verdict = get_verdict(pre_ai_score)

    if len(flags) == 0 and len(legitimacy_signals) > 0:
        flags.append({
            "title": "Positive legitimacy signals found",
            "detail": "This letter shows professional structure, useful job details, and fewer common scam patterns.",
            "severity": "safe",
        })

    # Build dynamic verification message before calling AI
    verification_msg = build_verification_message(
        detected_domain=detected_domain,
        detected_email=detected_email,
        flags=flags,
        verdict_color=verdict["color"],
    )

    ai_review, ai_signal = get_ai_review_and_signal(
        offer_text=offer_text,
        flags=flags,
        confidence_score=pre_ai_score,
        detected_domain=detected_domain,
        verdict_label=verdict["label"],
    )

    ai_adjustment = 0
    if ai_signal == "low_risk":
        ai_adjustment = 3
    elif ai_signal == "mixed":
        ai_adjustment = -1
    elif ai_signal == "high_risk":
        ai_adjustment = -5

    confidence_score = clamp_score(pre_ai_score + ai_adjustment)
    verdict = get_verdict(confidence_score)

    logger.info(
        "Analysis complete — score=%d verdict=%s flags=%d",
        confidence_score,
        verdict["color"],
        len(flags),
    )

    return jsonify({
        "verdict": verdict,
        "confidenceScore": confidence_score,
        "flags": flags,
        "detectedEmail": detected_email,
        "detectedDomain": detected_domain,
        "verificationMessage": verification_msg,
        "aiReview": ai_review,
        "aiSignal": ai_signal,
    })


if __name__ == "__main__":
    # Use gunicorn in production; this block is for local dev only.
    app.run(debug=False, port=5000)
