import re

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None

def extract_domain(email):
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].lower()

def analyze_offer(text):
    lower = text.lower()
    flags = []

    if any(word in lower for word in ["fee", "deposit", "pay", "registration fee", "laptop fee"]):
        flags.append({
            "title": "Upfront payment request",
            "detail": "The message mentions money-related terms that are common in scam offers."
        })

    if any(word in lower for word in ["urgent", "immediately", "within 24 hours", "within 2 hours"]):
        flags.append({
            "title": "Urgency pressure",
            "detail": "The message uses urgency language, which is a common pressure tactic."
        })

    if any(word in lower for word in ["dear applicant", "dear candidate"]):
        flags.append({
            "title": "Generic greeting",
            "detail": "The message uses a generic greeting instead of a personalized one."
        })

    email = extract_email(text)
    domain = extract_domain(email)

    if domain in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}:
        flags.append({
            "title": "Unofficial email domain",
            "detail": f"The sender uses {domain}, which is not a company domain."
        })

    score = 90 - len(flags) * 20
    if score >= 80:
        verdict = {"label": "Likely legitimate, but verify independently", "color": "green"}
    elif score >= 50:
        verdict = {"label": "Caution: some suspicious signals found", "color": "yellow"}
    else:
        verdict = {"label": "High scam risk detected", "color": "red"}

    return {
        "verdict": verdict,
        "confidenceScore": max(0, score),
        "flags": flags,
        "detectedEmail": email,
        "detectedDomain": domain,
        "verificationMessage": (
            "Hello,\n\n"
            "I received your offer letter and would like to verify that it was officially issued by your company. "
            "Could you please confirm this through your official domain or HR contact?\n\n"
            "Thank you."
        )
    }