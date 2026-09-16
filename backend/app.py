import io
import logging
import os
import pickle
import re
import uuid
from datetime import datetime, timezone

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
# Model
# ---------------------------------------------------------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "scam_detector.pkl")
try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    logger.info("Model loaded from %s", MODEL_PATH)
except Exception as exc:
    logger.critical("Failed to load model: %s", exc)
    raise

# ---------------------------------------------------------------------------
# Supabase client (lazy — only active when env vars are set)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vkqkjeeztypqjpzxhsfc.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")   # set sb_secret_... on Render

def supabase_insert(table: str, row: dict) -> bool:
    """Insert a row into a Supabase table via the REST API. Returns True on success."""
    if not SUPABASE_KEY:
        logger.warning("SUPABASE_KEY not set — feedback not persisted")
        return False
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type":  "application/json",
                "Prefer":        "return=minimal",
            },
            json=row,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return True
        logger.error("Supabase insert failed %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.error("Supabase error: %s", exc)
        return False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_INPUT_CHARS   = 10_000
WHOIS_API_KEY     = os.getenv("WHOIS_API_KEY", "at_4iqZXp4JUPrP3YHO7NDNPUNdlKnx4")
DOMAIN_AGE_MONTHS = 6          # domains younger than this get flagged

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "aol.com", "proton.me", "protonmail.com",
    "rediffmail.com", "ymail.com",
}

# Known scam / impersonation domains reported in India job-offer fraud cases.
# Sourced from public cybercrime advisories (I4C, CERT-In reports).
SCAM_DOMAIN_BLOCKLIST = {
    # Fake government / PSU impersonators
    "isro-careers.in", "isro-recruitment.com", "drdo-careers.net",
    "ongc-jobs.in", "bel-recruitment.com", "hal-hiring.in",
    "railwayrecruitment.in", "ntpc-careers.net", "bhel-jobs.com",
    # Fake MNC impersonators
    "tcs-careers.net", "infosys-careers.net", "wipro-jobs.in",
    "amazon-hiring.in", "google-jobs.in", "microsoft-hiring.in",
    "accenture-careers.net", "ibm-recruitment.in",
    # Generic scam domains
    "jobsoffer.in", "hiringjobs.in", "workfromhomejobs.co.in",
    "onlinejobs.net.in", "quickhire.co.in", "easyjob.net.in",
    "instantjobs.co.in", "jobsalert.co.in", "governmentjobs.co.in",
    "privatejobs.net.in", "fresherjobs.co.in", "freejobalert.net.in",
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
    "we are pleased to offer", "please review", "for any questions",
    "human resources", "hiring team", "offer of employment",
    "subject to company policy", "payroll deductions", "joining date",
    "reporting manager", "employment is contingent",
]

SUSPICIOUS_PHRASES = [
    "selected without interview", "guaranteed job", "instant joining",
    "no interview required", "pay and confirm", "transfer the amount",
    "whatsapp only", "telegram", "kindly pay",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    text = text.strip()
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
    patterns = [r"rs\.?\s?[\d,]+", r"inr\s?[\d,]+", r"ctc",
                r"annual compensation", r"per annum", r"per year", r"salary"]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def has_job_role(text: str) -> bool:
    roles = ["software engineer", "developer", "analyst", "associate", "manager",
             "executive", "intern", "consultant", "engineer", "specialist",
             "coordinator", "designer", "support", "administrator", "data entry"]
    lower = text.lower()
    return any(r in lower for r in roles)


def has_person_name_greeting(text: str) -> bool:
    return any(re.search(p, text) for p in [
        r"dear\s+[A-Z][a-z]+\s+[A-Z][a-z]+",
        r"dear\s+[A-Z][a-z]+",
    ])


def has_company_style_signoff(text: str) -> bool:
    patterns = ["best regards", "regards", "sincerely", "hiring team",
                "human resources", "hr team", "talent acquisition", "recruitment team"]
    lower = text.lower()
    return any(p in lower for p in patterns)


def seems_company_domain(domain: str) -> bool:
    if not domain or domain in PUBLIC_EMAIL_DOMAINS:
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


# ---------------------------------------------------------------------------
# WHOIS domain-age check (WhoisXML API)
# ---------------------------------------------------------------------------

def check_domain_age(domain: str) -> dict:
    """
    Returns {age_months, is_new, error}.
    Domains younger than DOMAIN_AGE_MONTHS months are flagged.
    """
    if not domain or domain in PUBLIC_EMAIL_DOMAINS:
        return {"age_months": None, "is_new": False, "error": "skipped"}

    try:
        resp = requests.get(
            "https://www.whoisxmlapi.com/whoisserver/WhoisService",
            params={
                "apiKey":        WHOIS_API_KEY,
                "domainName":    domain,
                "outputFormat":  "JSON",
                "da":            "2",    # domain availability hint
            },
            timeout=8,
        )
        if resp.status_code != 200:
            logger.warning("WHOIS API %s for %s", resp.status_code, domain)
            return {"age_months": None, "is_new": False, "error": "api_error"}

        data       = resp.json()
        whois_rec  = data.get("WhoisRecord", {})
        created_at = (
            whois_rec.get("createdDate")
            or whois_rec.get("registryData", {}).get("createdDate")
        )

        if not created_at:
            return {"age_months": None, "is_new": False, "error": "no_date"}

        # Parse ISO date (may have trailing timezone text)
        created_str = created_at[:19]
        created_dt  = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        now         = datetime.now(timezone.utc)
        age_months  = (now.year - created_dt.year) * 12 + (now.month - created_dt.month)

        return {
            "age_months": age_months,
            "is_new":     age_months < DOMAIN_AGE_MONTHS,
            "error":      None,
        }

    except Exception as exc:
        logger.warning("WHOIS check error for %s: %s", domain, exc)
        return {"age_months": None, "is_new": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Dynamic verification message
# ---------------------------------------------------------------------------

def build_verification_message(detected_domain, detected_email, flags, verdict_color) -> str:
    flag_titles   = {f["title"] for f in flags}
    has_fee       = "Payment request detected" in flag_titles
    has_dom       = "Public email domain detected" in flag_titles
    has_urgency   = "Urgency language detected" in flag_titles
    has_blocklist = "Known scam domain detected" in flag_titles
    has_new_dom   = "Recently registered domain" in flag_titles

    intro = (
        "Hello,\n\n"
        "I recently received an offer letter / hiring message that appears to "
        "originate from your organisation and would like to verify its authenticity "
        "before proceeding further."
    )

    parts = []

    if has_blocklist:
        parts.append(
            f"The message was sent from a domain ({detected_domain}) that has been "
            "flagged in public cybercrime reports as associated with job offer fraud. "
            "Could you please confirm whether this is genuinely your official domain?"
        )

    if has_new_dom and detected_domain:
        parts.append(
            f"The domain {detected_domain} appears to have been registered very recently. "
            "Could you please confirm how long your organisation has been using this domain "
            "for official communication?"
        )

    if has_dom and detected_email:
        parts.append(
            f"The message was sent from {detected_email}, which is a personal email address "
            "rather than an official company domain. Could you please confirm whether this "
            "email is associated with your HR or recruitment team?"
        )

    if has_fee:
        parts.append(
            "The offer requests an upfront payment (registration fee, security deposit, or similar). "
            "Could you please confirm whether your company requires any payment from candidates "
            "before joining? Legitimate employers do not charge candidates at any stage."
        )

    if has_urgency:
        parts.append(
            "The message urges an urgent response within a very short timeframe. "
            "Could you please confirm the actual deadline for accepting this offer?"
        )

    if not parts:
        parts.append(
            f"The offer was received from a sender at {detected_domain or 'an unknown address'}. "
            "Could you please confirm this is your official contact domain and that the offer is genuine?"
        )

    closing = (
        "I appreciate your time and look forward to a confirmed response "
        "through your official channels.\n\nThank you."
    )

    return intro + "\n\n" + "\n\n".join(parts) + "\n\n" + closing


# ---------------------------------------------------------------------------
# AI review (OpenRouter)
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
        f"Detected red flags: {[f['title'] for f in flags]}\n\n"
        f"Current score before AI adjustment: {confidence_score}\n\n"
        f"Current verdict: {verdict_label}\n\n"
        "Write a short review in exactly 3 bullet points:\n"
        "- main concerns\n- what looks safe or unsafe\n- what the user should verify next\n\n"
        "At the very end add exactly one line:\n"
        "AI_SIGNAL: low_risk  OR  AI_SIGNAL: mixed  OR  AI_SIGNAL: high_risk\n\n"
        "Rules: Do not claim the offer is definitely legitimate. Under 140 words. Be conservative."
    )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://hirewise-backend-r748.onrender.com",
                "X-OpenRouter-Title": "HireWise",
            },
            json={
                "model":    "openrouter/auto",
                "messages": [
                    {"role": "system", "content": "You explain scam risk clearly, conservatively, and briefly."},
                    {"role": "user",   "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens":  220,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error("OpenRouter error %s: %s", resp.status_code, resp.text[:200])
            return None, "unavailable"

        content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            return None, "unavailable"

        lower = content.lower()
        if   "ai_signal: low_risk"  in lower: signal = "low_risk"
        elif "ai_signal: high_risk" in lower: signal = "high_risk"
        else:                                 signal = "mixed"

        cleaned = re.sub(r"AI_SIGNAL:\s*(low_risk|mixed|high_risk)", "", content, flags=re.IGNORECASE).strip()
        return cleaned, signal

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
    return jsonify({"status": "ok"})


@app.route("/api/extract", methods=["POST"])
@limiter.limit("10 per minute")
def extract():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file     = request.files["file"]
    filename = file.filename or ""
    raw      = file.read(2 * 1024 * 1024 + 1)

    if len(raw) > 2 * 1024 * 1024:
        return jsonify({"error": "File too large (max 2 MB)"}), 400

    try:
        text = pdf_extract_text(io.BytesIO(raw)) if filename.lower().endswith(".pdf") \
               else raw.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("Extraction error: %s", exc)
        return jsonify({"error": "Could not extract text from file"}), 500

    return jsonify({"text": text.strip()[:MAX_INPUT_CHARS]})


@app.route("/api/analyze", methods=["POST"])
@limiter.limit("10 per minute")
def analyze():
    payload    = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Request body must be JSON"}), 400

    offer_text = payload.get("offerText", "").strip()
    if not offer_text:
        return jsonify({"error": "No offer text provided"}), 400
    if len(offer_text) > MAX_INPUT_CHARS:
        return jsonify({"error": f"Input too long. Max {MAX_INPUT_CHARS} characters."}), 400

    normalized     = normalize_text(offer_text)
    detected_email = extract_email(offer_text)
    detected_domain= extract_domain(detected_email)
    lower_text     = offer_text.lower()

    flags              = []
    legitimacy_signals = []
    risk_penalty       = 0
    legitimacy_bonus   = 0

    # ── 1. Known scam domain blocklist ───────────────────────────────────────
    if detected_domain and detected_domain in SCAM_DOMAIN_BLOCKLIST:
        flags.append({
            "title":    "Known scam domain detected",
            "detail":   f"The domain {detected_domain} has been flagged in public cybercrime reports "
                        "as associated with job offer fraud. Do not share any documents or money.",
            "severity": "high",
        })
        risk_penalty += 45

    # ── 2. WHOIS domain age check ─────────────────────────────────────────────
    whois_result  = {"age_months": None, "is_new": False, "error": "skipped"}
    domain_age_months = None
    if detected_domain and detected_domain not in PUBLIC_EMAIL_DOMAINS \
            and detected_domain not in SCAM_DOMAIN_BLOCKLIST:
        whois_result = check_domain_age(detected_domain)
        domain_age_months = whois_result.get("age_months")
        if whois_result.get("is_new"):
            age_str = f"{domain_age_months} month{'s' if domain_age_months != 1 else ''}"
            flags.append({
                "title":    "Recently registered domain",
                "detail":   f"The domain {detected_domain} was registered only {age_str} ago. "
                            "Scammers frequently register new domains to impersonate companies. "
                            "Verify this domain on the company's official website.",
                "severity": "high",
            })
            risk_penalty += 28

    # ── 3. Rule-based risk signals ────────────────────────────────────────────
    if any(kw in lower_text for kw in SCAM_KEYWORDS):
        flags.append({
            "title":    "Payment request detected",
            "detail":   "The message asks for money or mentions fees, which is a common scam signal.",
            "severity": "high",
        })
        risk_penalty += 34

    if any(kw in lower_text for kw in URGENCY_KEYWORDS):
        flags.append({
            "title":    "Urgency language detected",
            "detail":   "The message creates pressure to act quickly, which is a known risk signal.",
            "severity": "medium",
        })
        risk_penalty += 14

    if any(ph in lower_text for ph in SUSPICIOUS_PHRASES):
        flags.append({
            "title":    "Suspicious hiring wording detected",
            "detail":   "The message uses wording commonly seen in unsafe or misleading hiring messages.",
            "severity": "high",
        })
        risk_penalty += 18

    if detected_domain in PUBLIC_EMAIL_DOMAINS:
        flags.append({
            "title":    "Public email domain detected",
            "detail":   "The sender uses a public email domain instead of a company domain.",
            "severity": "medium",
        })
        risk_penalty += 18
    elif seems_company_domain(detected_domain):
        legitimacy_signals.append("The email uses a company-style domain instead of a public mailbox.")
        legitimacy_bonus += 12

    if "congratulations" in lower_text and "selected" in lower_text:
        flags.append({
            "title":    "Premature selection language",
            "detail":   "The message strongly claims selection early, which can sometimes be suspicious.",
            "severity": "low",
        })
        risk_penalty += 8

    # ── 4. Legitimacy signals ─────────────────────────────────────────────────
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

    # ── 5. ML model (weight 0.55 — reduced due to training domain gap) ────────
    scam_prob           = model.predict_proba([normalized])[0][1]
    base_score          = round((1 - scam_prob) * 100)
    score_after_model   = (base_score * 0.55) + 20
    score_after_rules   = score_after_model - risk_penalty + legitimacy_bonus

    if risk_penalty >= 45 and legitimacy_bonus <= 10:
        score_after_rules -= 10
    if legitimacy_bonus >= 28 and risk_penalty == 0:
        score_after_rules += 8

    pre_ai_score = clamp_score(score_after_rules)
    verdict      = get_verdict(pre_ai_score)

    if not flags and legitimacy_signals:
        flags.append({
            "title":    "Positive legitimacy signals found",
            "detail":   "This letter shows professional structure, job details, and no common scam patterns.",
            "severity": "safe",
        })

    # Build dynamic verification message
    verification_msg = build_verification_message(
        detected_domain=detected_domain,
        detected_email=detected_email,
        flags=flags,
        verdict_color=verdict["color"],
    )

    # ── 6. AI review ──────────────────────────────────────────────────────────
    ai_review, ai_signal = get_ai_review_and_signal(
        offer_text=offer_text,
        flags=flags,
        confidence_score=pre_ai_score,
        detected_domain=detected_domain,
        verdict_label=verdict["label"],
    )

    ai_adjustment = {"low_risk": 3, "mixed": -1, "high_risk": -5}.get(ai_signal, 0)
    confidence_score = clamp_score(pre_ai_score + ai_adjustment)
    verdict          = get_verdict(confidence_score)

    # Generate a stable analysis ID so the frontend can reference it in feedback
    analysis_id = str(uuid.uuid4())

    logger.info(
        "Analysis %s — score=%d verdict=%s flags=%d domain=%s age=%s",
        analysis_id[:8], confidence_score, verdict["color"],
        len(flags), detected_domain, domain_age_months,
    )

    return jsonify({
        "analysisId":        analysis_id,
        "verdict":           verdict,
        "confidenceScore":   confidence_score,
        "flags":             flags,
        "detectedEmail":     detected_email,
        "detectedDomain":    detected_domain,
        "domainAgeMonths":   domain_age_months,
        "verificationMessage": verification_msg,
        "aiReview":          ai_review,
        "aiSignal":          ai_signal,
        "legitimacySignals": legitimacy_signals,
    })


@app.route("/api/feedback", methods=["POST"])
@limiter.limit("20 per minute")
def feedback():
    """
    Store user feedback on analysis accuracy.
    Body: { analysisId, isScam (bool), verdict, score, detectedDomain,
            flagsCount, aiSignal, offerSnippet }
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "JSON body required"}), 400

    required = ["analysisId", "isScam"]
    for field in required:
        if field not in payload:
            return jsonify({"error": f"Missing field: {field}"}), 400

    row = {
        "analysis_id":    str(payload.get("analysisId", ""))[:36],
        "offer_snippet":  str(payload.get("offerSnippet", ""))[:300],
        "verdict":        str(payload.get("verdict", ""))[:20],
        "score":          int(payload.get("score", 0)),
        "is_scam":        bool(payload.get("isScam")),
        "detected_domain":str(payload.get("detectedDomain", ""))[:100],
        "flags_count":    int(payload.get("flagsCount", 0)),
        "ai_signal":      str(payload.get("aiSignal", ""))[:20],
    }

    saved = supabase_insert("feedback", row)
    logger.info("Feedback received — analysis=%s is_scam=%s saved=%s",
                row["analysis_id"][:8], row["is_scam"], saved)

    return jsonify({"ok": True, "saved": saved})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
