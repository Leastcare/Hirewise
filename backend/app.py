from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import re
import os
import requests

app = Flask(__name__)
CORS(app)

with open("model/scam_detector.pkl", "rb") as f:
    model = pickle.load(f)

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "aol.com", "proton.me", "protonmail.com"
}

SCAM_KEYWORDS = [
    "registration fee", "security deposit", "processing fee", "payment",
    "deposit", "pay immediately", "advance fee", "training fee",
    "registration amount", "refundable fee", "pay before joining",
    "screening fee", "onboarding fee", "pay the amount"
]

URGENCY_KEYWORDS = [
    "urgent", "immediately", "within 24 hours", "as soon as possible",
    "limited time", "today itself", "next 2 hours", "act now",
    "final deadline", "respond today", "confirm immediately"
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
    "employment is contingent"
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
    "kindly pay"
]

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None

def extract_domain(email):
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].lower()

def has_salary_info(text):
    salary_patterns = [
        r'rs\.?\s?[\d,]+',
        r'inr\s?[\d,]+',
        r'ctc',
        r'annual compensation',
        r'per annum',
        r'per year',
        r'salary'
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in salary_patterns)

def has_job_role(text):
    role_keywords = [
        "software engineer", "developer", "analyst", "associate", "manager",
        "executive", "intern", "consultant", "engineer", "specialist",
        "coordinator", "designer", "support", "administrator", "data entry"
    ]
    text_lower = text.lower()
    return any(role in text_lower for role in role_keywords)

def has_person_name_greeting(text):
    patterns = [
        r"dear\s+[A-Z][a-z]+\s+[A-Z][a-z]+",
        r"dear\s+[A-Z][a-z]+"
    ]
    return any(re.search(pattern, text) for pattern in patterns)

def has_company_style_signoff(text):
    signoff_patterns = [
        "best regards",
        "regards",
        "sincerely",
        "hiring team",
        "human resources",
        "hr team",
        "talent acquisition",
        "recruitment team"
    ]
    text_lower = text.lower()
    return any(p in text_lower for p in signoff_patterns)

def seems_company_domain(domain):
    if not domain:
        return False
    if domain in PUBLIC_EMAIL_DOMAINS:
        return False
    return "." in domain and len(domain.split(".")) >= 2

def clamp_score(value, low=0, high=95):
    return max(low, min(high, round(value)))

def get_verdict(score):
    if score >= 75:
        return {
            "label": "Likely legitimate offer",
            "color": "green"
        }
    elif score >= 40:
        return {
            "label": "Needs review before you trust it",
            "color": "yellow"
        }
    else:
        return {
            "label": "High scam risk detected",
            "color": "red"
        }

def get_ai_review_and_signal(offer_text, flags, confidence_score, detected_domain, verdict_label):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not found")
        return None, "unavailable"

    prompt = f"""
You are a cautious job-offer scam review assistant.

Offer text:
{offer_text}

Detected domain:
{detected_domain}

Detected red flags:
{flags}

Current score before AI adjustment:
{confidence_score}

Current verdict:
{verdict_label}

Your tasks:
1. Write a short review in exactly 3 bullet points:
- main concerns
- what looks safe or unsafe
- what the user should verify next

2. At the very end, add one final line in this exact format:
AI_SIGNAL: low_risk
or
AI_SIGNAL: mixed
or
AI_SIGNAL: high_risk

Rules:
- Do not claim the offer is definitely legitimate.
- Keep the whole response under 140 words.
- Be practical and conservative.
"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-OpenRouter-Title": "HireWise"
            },
            json={
                "model": "openrouter/auto",
                "messages": [
                    {
                        "role": "system",
                        "content": "You explain scam risk clearly, conservatively, and briefly."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 220
            },
            timeout=30
        )

        if response.status_code != 200:
            print("OpenRouter error:", response.status_code, response.text)
            return None, "unavailable"

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            print("OpenRouter returned no choices:", data)
            return None, "unavailable"

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            print("OpenRouter returned empty content:", data)
            return None, "unavailable"

        content = content.strip()
        lower_content = content.lower()
        ai_signal = "mixed"

        if "ai_signal: low_risk" in lower_content:
            ai_signal = "low_risk"
        elif "ai_signal: high_risk" in lower_content:
            ai_signal = "high_risk"
        elif "ai_signal: mixed" in lower_content:
            ai_signal = "mixed"

        cleaned_review = re.sub(
            r'AI_SIGNAL:\s*(low_risk|mixed|high_risk)',
            '',
            content,
            flags=re.IGNORECASE
        ).strip()

        return cleaned_review, ai_signal

    except Exception as e:
        print("AI review error:", str(e))
        return None, "unavailable"

@app.route("/")
def home():
    return "HireWise backend is running"

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    offer_text = data.get("offerText", "").strip()

    if not offer_text:
        return jsonify({"error": "No offer text provided"}), 400

    detected_email = extract_email(offer_text)
    detected_domain = extract_domain(detected_email)
    lower_text = offer_text.lower()

    flags = []
    legitimacy_signals = []

    risk_penalty = 0
    legitimacy_bonus = 0

    if any(keyword in lower_text for keyword in SCAM_KEYWORDS):
        flags.append({
            "title": "Payment request detected",
            "detail": "The message asks for money or mentions fees, which is a common scam signal."
        })
        risk_penalty += 34

    if any(keyword in lower_text for keyword in URGENCY_KEYWORDS):
        flags.append({
            "title": "Urgency language detected",
            "detail": "The message creates pressure to act quickly, which is a known risk signal."
        })
        risk_penalty += 14

    if any(phrase in lower_text for phrase in SUSPICIOUS_PHRASES):
        flags.append({
            "title": "Suspicious hiring wording detected",
            "detail": "The message uses wording commonly seen in unsafe or misleading hiring messages."
        })
        risk_penalty += 18

    if detected_domain in PUBLIC_EMAIL_DOMAINS:
        flags.append({
            "title": "Public email domain detected",
            "detail": "The sender uses a public email domain instead of a company domain."
        })
        risk_penalty += 18
    elif seems_company_domain(detected_domain):
        legitimacy_signals.append("The email uses a company-style domain instead of a public mailbox.")
        legitimacy_bonus += 12

    if "congratulations" in lower_text and "selected" in lower_text:
        flags.append({
            "title": "Premature selection language",
            "detail": "The message strongly claims selection early, which can sometimes be suspicious."
        })
        risk_penalty += 8

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

    if any(phrase in lower_text for phrase in POSITIVE_PHRASES):
        legitimacy_signals.append("The message uses professional offer-letter wording.")
        legitimacy_bonus += 5

    scam_probability = model.predict_proba([offer_text])[0][1]
    base_confidence_score = round((1 - scam_probability) * 100)

    score_after_model = (base_confidence_score * 0.72) + 15
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
            "detail": "This letter shows professional structure, useful job details, and fewer common scam patterns."
        })

    ai_review, ai_signal = get_ai_review_and_signal(
        offer_text=offer_text,
        flags=flags,
        confidence_score=pre_ai_score,
        detected_domain=detected_domain,
        verdict_label=verdict["label"]
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

    return jsonify({
        "verdict": verdict,
        "confidenceScore": confidence_score,
        "flags": flags,
        "detectedEmail": detected_email,
        "detectedDomain": detected_domain,
        "verificationMessage": "Hello, I received this offer and would like to verify whether it was officially sent by your company. Please confirm.",
        "aiReview": ai_review,
        "aiSignal": ai_signal,
        "aiAdjustment": ai_adjustment,
        "baseModelScore": base_confidence_score,
        "preAiScore": pre_ai_score,
        "riskPenalty": risk_penalty,
        "legitimacyBonus": legitimacy_bonus,
        "legitimacySignals": legitimacy_signals
    })

if __name__ == "__main__":
    app.run(debug=True)