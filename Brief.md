# HireWise — Complete Interview Preparation Guide

---

## PART 1 — THE QUICK BRIEF (explain this in 30 seconds)

HireWise is a job offer scam detection web app. A user pastes an offer letter they received, and the app tells them whether it looks real or fake. It gives them a risk score from 0 to 95, a list of red flags found in the letter, and a ready-to-send verification message they can forward to the employer.

It uses three layers to make that decision:
1. A machine learning model trained on 62,000+ job postings
2. A rule engine that checks for payment requests, urgency language, fake domains etc.
3. An AI review via OpenRouter (optional, uses a language model for a written summary)

It also checks if the email domain is brand new (using WHOIS) and compares it against a blocklist of known scam domains.

---

## PART 2 — DETAILED EXPLANATION

### The Big Picture — How It All Works Together

Think of HireWise like a security scanner at an airport. When a user pastes an offer letter:

1. The text goes to the Flask backend
2. The backend runs it through 6 checks in order
3. Each check either adds a penalty (bad sign) or a bonus (good sign)
4. Those penalties and bonuses are combined with the ML model's opinion
5. The result is a score from 0–95, a verdict (green/yellow/red), and a list of flags
6. The user sees all of this in the frontend with animations

---

### The Tech Stack

**Frontend** — Pure HTML, CSS, and vanilla JavaScript. No React, no Vue, nothing fancy. Just three files.

**Backend** — Python with Flask. One file (`app.py`) handles all the logic.

**ML Model** — scikit-learn. TF-IDF converts text to numbers, Logistic Regression classifies it as scam or legit.

**Database** — Supabase (Postgres). Stores user feedback (was this a scam or not?) so the model can be retrained later.

**WHOIS** — WhoisXML API. Checks how old a domain is. Brand new domains are suspicious.

**AI Review** — OpenRouter API. Sends the offer text to an LLM which writes a 3-bullet summary.

**Deployment** — Backend on Render (free tier). Frontend on Vercel (static).

---

### The Backend in Detail (`app.py`)

#### Step 1 — Input comes in

The frontend sends a POST request to `/api/analyze` with this JSON:
```json
{ "offerText": "Dear Candidate, pay registration fee..." }
```

The backend first validates it:
- Is it JSON? If not, return 400
- Is it empty? Return 400
- Is it over 10,000 characters? Return 400

#### Step 2 — Text is normalized

```python
def normalize_text(text):
    text = text.strip()
    text = re.sub(r"\s+", " ", text)  # collapse multiple spaces/newlines into one
    return text
```

This is important because the ML model was trained on clean text. If the user pastes something with weird spacing, the model needs it cleaned first.

#### Step 3 — Email and domain are extracted

```python
def extract_email(text):
    match = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", text)
    return match.group(0) if match else None
```

This uses a regular expression (regex) to find an email address anywhere in the text. A regex is basically a pattern matcher — it looks for something that has characters, then @, then more characters, then a dot, then more characters.

`extract_domain` then just takes everything after the `@` symbol.

#### Step 4 — Scam domain blocklist check

```python
if detected_domain and detected_domain in SCAM_DOMAIN_BLOCKLIST:
    flags.append({...})
    risk_penalty += 45
```

Simple set lookup. If the domain is in a hardcoded set of known bad domains (like `isro-careers.in` or `tcs-careers.net`), it immediately adds 45 points of penalty. This is the most decisive check — a domain on the blocklist is a near-certain scam.

#### Step 5 — WHOIS domain age check

```python
def check_domain_age(domain):
    resp = requests.get("https://www.whoisxmlapi.com/whoisserver/WhoisService", 
                        params={...})
    created_at = data["WhoisRecord"]["createdDate"]
    age_months = (now.year - created_dt.year) * 12 + (now.month - created_dt.month)
    return {"age_months": age_months, "is_new": age_months < 6}
```

WHOIS is a public database that tells you when a domain was registered. Scammers register cheap domains like `tcs-hiring-2026.in` to fool people. If a domain is less than 6 months old, it gets flagged. The calculation converts the creation date to "months old" by comparing year and month.

#### Step 6 — Rule engine

Five separate checks using keyword lists:

| Check | Keywords | Penalty |
|---|---|---|
| Payment request | "registration fee", "deposit", "pay immediately" | +34 |
| Urgency language | "urgent", "within 24 hours", "act now" | +14 |
| Suspicious phrases | "selected without interview", "whatsapp only" | +18 |
| Public email domain | gmail.com, yahoo.com, etc. | +18 |
| Premature selection | "congratulations" + "selected" together | +8 |

Legitimacy bonuses:

| Check | Bonus |
|---|---|
| Personalized name greeting (e.g. "Dear Aditi Sharma") | +8 |
| Salary info (INR, CTC, per annum) | +8 |
| Job role mentioned | +6 |
| Professional sign-off (Best regards, HR Team) | +6 |
| Standard offer letter phrases | +5 |

#### Step 7 — ML model runs

```python
scam_prob = model.predict_proba([normalized])[0][1]
base_score = round((1 - scam_prob) * 100)
score_after_model = (base_score * 0.55) + 20
```

`predict_proba` returns two numbers — the probability of being legit (index 0) and the probability of being a scam (index 1). We take the scam probability, subtract from 1 to get the "legitimacy" score, multiply by 100 to get a 0–100 number.

We then scale it: `* 0.55 + 20`. This compresses the range and adds a floor. Why 0.55 instead of something higher? Because the model was trained on job postings, not offer letters. They're slightly different in vocabulary. Reducing the weight accounts for that uncertainty.

#### Step 8 — Scores are combined

```python
score_after_rules = score_after_model - risk_penalty + legitimacy_bonus
```

Simple addition and subtraction. The model gives a base, the rules push it up or down.

Two edge case adjustments:
- If total penalty is very high (≥45) and legitimacy is low (≤10), push down by 10 more — it's really bad
- If legitimacy is high (≥28) and zero risk — push up by 8 — it looks really clean

Then clamp to 0–95:
```python
def clamp_score(value, low=0, high=95):
    return max(low, min(high, round(value)))
```

We never go above 95 on purpose — even a perfect offer should still get manually verified.

#### Step 9 — AI review

The offer text, detected flags, and current score are sent to OpenRouter (an LLM gateway). The LLM writes 3 bullet points and then outputs one of three signals: `low_risk`, `mixed`, or `high_risk`. That signal adjusts the final score by +3, -1, or -5.

#### Step 10 — Response is returned

```json
{
  "analysisId": "uuid-here",
  "verdict": {"label": "High scam risk detected", "color": "red"},
  "confidenceScore": 12,
  "flags": [{"title": "...", "detail": "...", "severity": "high"}],
  "detectedEmail": "fake@gmail.com",
  "detectedDomain": "gmail.com",
  "domainAgeMonths": null,
  "verificationMessage": "Hello, I received this offer...",
  "aiReview": "• Main concern: ...",
  "aiSignal": "high_risk"
}
```

---

### The ML Model (`model_train.py`)

**What is TF-IDF?**
TF-IDF stands for Term Frequency–Inverse Document Frequency. It's a way to convert text into numbers. Each word in the offer gets a score based on:
- How often it appears in this offer (TF — more = higher score)
- How rare it is across all offers (IDF — rarer = higher score)

So a word like "registration fee" that appears a lot in scam offers but rarely in legit ones gets a very high TF-IDF score in a scam offer.

**What is Logistic Regression?**
Despite the word "regression" it's a classification algorithm. It takes all those TF-IDF word scores and learns a set of weights — like "if you see 'registration fee', add +5 to the scam score; if you see 'per annum', add -3". After training, it can say "this text is 87% likely to be a scam".

**Training data:**
- `fake_job_postings.csv` — 17,880 rows of real job postings from Kaggle, labeled 0 (legit) or 1 (scam)
- `processed_labeled_dataset_without_encoding.xlsx` — 54,391 more labeled samples
- `offer_letters_dataset.csv` — 200 synthetic offer letters we generated ourselves

The offer letters are upweighted 3x because that's what real users actually paste — the model needs to be especially good on that type of text.

**Why normalize at training time?**
We apply `normalize_text()` to the training data too. This means training and inference see the same kind of text. If we didn't, the model might never have seen text with extra spaces or newlines, and it would behave differently at inference.

**Result:** 99.49% accuracy overall, 100% on the offer-letter subset.

---

### The Feedback Loop

When a user sees a result, they get two buttons: "Yes, it was a scam" or "No, it was legit". Clicking either sends a POST to `/api/feedback`:

```python
row = {
    "analysis_id": "uuid",
    "offer_snippet": "first 200 chars of the offer",
    "verdict": "red",
    "score": 12,
    "is_scam": True,
    "detected_domain": "gmail.com",
    "flags_count": 3,
    "ai_signal": "high_risk"
}
```

This gets saved to a Supabase (Postgres) table. Over time, this builds a labeled dataset of real user-submitted offers. We can then retrain the model with real data instead of synthetic data.

---

### The Frontend

Three files:
- `index.html` — structure and layout
- `style.css` — all styling, dark/light theme, animations
- `script.js` — all logic

**Five UI enhancements built from scratch:**

1. **Scan line** — when you click Analyze, a glowing line sweeps top to bottom across the textarea using CSS animation (`@keyframes scanDown`)

2. **Radial SVG gauge** — instead of a progress bar, there's a semicircle SVG with a needle. The needle rotates using `transform: rotate(Xdeg)`, and the arc fills using SVG `stroke-dashoffset` animation

3. **Inline phrase highlighting** — after analysis, the offer text shows red/amber highlights on dangerous phrases. This works by placing a transparent div behind the textarea, parsing the text to find keyword positions, and inserting `<mark>` elements at those positions

4. **Full-page verdict pulse** — when a result appears, the entire background briefly flashes the verdict colour using `position: fixed` overlay with a CSS `@keyframes` opacity animation

5. **Timeline flag cards** — flag cards slide in from the left with staggered delays (80ms apart) using `animation-delay` and the `@keyframes slideInLeft` animation

---

### Security Measures Built In

| Problem | Solution |
|---|---|
| Anyone can spam the API | Flask-Limiter: 10 requests per minute per IP |
| User pastes huge text | Max 10,000 character validation on both frontend and backend |
| XSS attack via flag text | All flag content uses `textContent` not `innerHTML` |
| Debug mode in production | `debug=False` in `app.run()` |
| Model file missing on startup | `try/except` with `logger.critical` and `raise` — server won't start broken |
| Render free tier cold starts | `/api/ping` called on page load to wake the server before the user clicks |
| CORS wildcard | `CORS(app)` — acceptable for a public tool, would lock down with origins list for auth'd app |

---

## PART 3 — INTERVIEW QUESTIONS

### LOW LEVEL (Fresher / Intern)

**Q: What does HireWise do in one sentence?**
It scans a job offer letter and tells you whether it's likely a scam or legitimate, using a combination of machine learning, rule-based checks, and AI review.

**Q: What is Flask?**
Flask is a lightweight Python web framework. It lets you define URL routes (like `/api/analyze`) and write Python functions that run when those URLs are called.

**Q: What is an API?**
An API (Application Programming Interface) is a way for two programs to talk to each other. The frontend sends a request to the backend's API with the offer text, and the API responds with the analysis result.

**Q: What is JSON?**
JSON (JavaScript Object Notation) is a text format for sending structured data. Like `{"name": "Aditi", "score": 72}`. The frontend and backend communicate using JSON.

**Q: What does `POST` mean in the context of HTTP?**
HTTP has different methods (GET, POST, PUT, DELETE). GET is for fetching data. POST is for sending data to the server to be processed. When a user clicks Analyze, the frontend does a POST request with the offer text in the body.

**Q: What is a regex? Give an example from the project.**
A regex (regular expression) is a pattern used to find text. In HireWise, `[\w.\-]+@[\w.\-]+\.\w+` is used to find email addresses. `\w` means any word character (letters/numbers), `+` means one or more, `@` is literal, `\.` is a literal dot.

**Q: What does `model.predict_proba()` return?**
It returns two probabilities for each input — `[prob_legit, prob_scam]`. For example `[0.12, 0.88]` means 12% chance of being legit, 88% chance of being a scam. We use index `[0][1]` to get the scam probability for the first (and only) input.

**Q: What is Logistic Regression?**
A machine learning algorithm that classifies inputs into categories. It learns weights for each feature (word) during training. At prediction time, it multiplies each feature value by its weight, sums them up, and runs through a sigmoid function to output a probability between 0 and 1.

**Q: What is TF-IDF?**
A technique that converts text into numbers. TF (Term Frequency) = how often a word appears in this document. IDF (Inverse Document Frequency) = how rare the word is across all documents. Rare but frequent words get high scores. Common words like "the" get low scores.

**Q: What is a `pickle` file?**
Pickle is Python's way of saving an object to a file. We train the ML model once and save it as `scam_detector.pkl`. When the Flask server starts, it loads the file back into memory with `pickle.load()`. This means we don't have to retrain every time the server restarts.

**Q: What is CORS and why is it needed?**
CORS (Cross-Origin Resource Sharing) is a browser security rule that blocks JavaScript from calling APIs on a different domain. Our frontend is on `vercel.app` but the backend is on `render.com`. Without `flask_cors`, the browser would block all requests. `CORS(app)` adds the necessary headers to allow it.

**Q: What is Supabase?**
Supabase is a hosted Postgres database with a REST API layer. We use it to store user feedback. Instead of writing SQL directly, we send a POST request to Supabase's REST API with the row data and it saves it for us.

**Q: What does `clamp_score` do and why is the max 95 not 100?**
`clamp_score` keeps the score between 0 and 95. `max(0, min(95, round(value)))`. The max is 95 not 100 deliberately — even the cleanest-looking offer should still be verified by the user. A 100 score would imply guaranteed legitimacy, which we can't claim.

**Q: What is the difference between `GET` and `POST`?**
GET retrieves data without changing anything — like `/api/ping` which just returns `{"status": "ok"}`. POST sends data to the server and usually causes something to happen — like `/api/analyze` which processes text and returns a result.

---

### MID LEVEL (Junior Developer / 1-2 years experience)

**Q: Walk me through the full analysis pipeline.**
1. Validate input (JSON, not empty, under 10,000 chars)
2. Normalize text (strip, collapse whitespace)
3. Extract email and domain with regex
4. Check domain against blocklist — +45 penalty if found
5. Run WHOIS domain age check — +28 penalty if under 6 months
6. Rule engine checks (payment keywords, urgency, suspicious phrases, public email, premature selection) — various penalties
7. Legitimacy checks (name greeting, salary, job role, sign-off, positive phrases) — various bonuses
8. ML model runs on normalized text — gives scam probability
9. Blend: `(base_score * 0.55) + 20 - risk_penalty + legitimacy_bonus`
10. Clamp to 0–95
11. Optional AI review via OpenRouter — adjusts score ±3/5
12. Build dynamic verification message
13. Return JSON with all results

**Q: Why is the ML model weight only 0.55?**
The model was trained on structured job posting data (title, description, requirements) but at inference time it receives raw offer letter text. These have different vocabulary and structure. Reducing the weight from the original 0.72 to 0.55 and adding a floor offset of +20 compensates for this calibration gap. The rule engine then anchors the score more reliably.

**Q: How did you fix the domain mismatch problem in the model?**
Three ways:
1. Reduced ML weight from 0.72 to 0.55
2. Applied `normalize_text()` at training time too so training and inference distributions match
3. Added 200 synthetic offer letter samples to the training data, upweighted 3x so the model learns offer-letter vocabulary explicitly

**Q: How does the inline text highlighting work?**
The offer textarea is inside a `.scan-container`. When results come in, we create a new `div.highlight-layer` and position it absolutely behind the textarea. We parse the offer text, find all keyword positions using `indexOf()` in a loop, sort them by position, and insert `<mark>` elements (with red or amber CSS classes) at those positions with regular text nodes in between. The textarea is made transparent (CSS `color: transparent`) so the highlight layer shows through. Scroll is synced between the textarea and the layer via an event listener.

**Q: How do you prevent XSS in the flag cards?**
All flag titles and details come from the backend. Instead of `card.innerHTML = '<h4>' + flag.title + '</h4>'`, we use:
```javascript
const h4 = document.createElement("h4");
h4.textContent = flag.title;  // textContent escapes HTML automatically
```
`textContent` treats the value as plain text, so even if an attacker somehow got `<script>alert(1)</script>` into a flag title, it would just display as literal text, not execute.

**Q: How does rate limiting work?**
Flask-Limiter wraps specific routes with `@limiter.limit("10 per minute")`. It tracks request counts per IP address in memory. When a user exceeds 10 requests in 60 seconds, Flask-Limiter returns a 429 status code before the route function even runs. The frontend detects the 429 and shows a specific message.

**Q: How does the WHOIS age check work in detail?**
We call the WhoisXML API with the domain name. It returns a JSON object with a `createdDate` field like `2026-08-01T00:00:00`. We parse that into a Python `datetime` object, then calculate:
```python
age_months = (now.year - created_dt.year) * 12 + (now.month - created_dt.month)
```
If `age_months < 6`, the domain is flagged as recently registered. We skip the check for public email domains (Gmail etc.) since we don't need WHOIS for those — they're already flagged by the public domain check.

**Q: Why do you generate a UUID for each analysis?**
`analysis_id = str(uuid.uuid4())` creates a unique identifier for each analysis. When the user submits feedback ("was this a scam?"), they send back this ID. This lets us link the feedback row in Supabase to the specific analysis — so when we later retrain, we know exactly which offer text got what label from the user.

**Q: What is `sample_weight` in the model training?**
Scikit-learn's `fit()` accepts a `sample_weight` parameter. Rows with a higher weight count as if they appeared multiple times in training. We set `weight=3.0` for offer-letter rows, meaning each synthetic offer letter sample counts as 3 job posting samples. This forces the model to pay more attention to offer-letter patterns.

**Q: How does the radial SVG gauge work?**
The gauge is an SVG `<path>` element drawing a semicircle arc. SVG strokes can be animated using `stroke-dasharray` (total line length) and `stroke-dashoffset` (how much to "skip"). A full semicircle has a path length of ~251.2 pixels. Setting `stroke-dashoffset = 251.2` hides the arc completely. Setting it to 0 shows it fully. For a score of 72%: `offset = 251.2 - (0.72 * 251.2) = 70.3`. The needle rotates from -90° (left = 0) to +90° (right = 100). For score 72: `degrees = -90 + (0.72 * 180) = 39.6°`.

**Q: How does the feedback loop improve the model over time?**
User feedback is stored in Supabase with the offer snippet, the score HireWise gave, and whether the user confirmed it was a scam. Over time this builds a labeled dataset of real offer letters. The `model_train.py` script can be updated to load this table as a fourth training dataset. Running it again produces a new `scam_detector.pkl` that knows real-world patterns, not just synthetic ones.

**Q: How is the verification message made dynamic?**
`build_verification_message()` receives the list of detected flags, the domain, and the email. It checks `{f["title"] for f in flags}` (a set, for O(1) lookups). Depending on which flags are present, different paragraphs are added. For example if "Known scam domain detected" is a flag, a specific paragraph about cybercrime reports is added. If "Payment request detected" is a flag, a paragraph about legitimate employers not charging fees is added. This means two offers with different flags get completely different verification messages.

---

### HIGH LEVEL (Senior / System Design)

**Q: What are the biggest limitations of this system?**
1. **Model calibration** — the confidence score isn't a true probability. It's a blended heuristic with magic numbers. Two offers scoring 60 and 65 are not meaningfully different.
2. **Training domain gap** — despite adding synthetic offer letters, the model was primarily trained on job postings. Real offer letter patterns learned from user feedback will significantly improve it.
3. **No state** — Render free tier wipes memory on redeploy. Rate limiting uses in-memory storage. After each deploy, the rate limit counters reset.
4. **Single email extraction** — the regex only finds the first email. An offer with two emails (a legitimate one and a scam one embedded) would only check one.
5. **Language** — the model only works well on English text. Hindi/regional language offers are not handled.
6. **WHOIS reliability** — many domains have private WHOIS registration. The age check returns null silently in those cases.

**Q: How would you scale this if 100,000 users used it daily?**
1. Move from Render free to a proper instance (at minimum)
2. Replace in-memory rate limiting with Redis so it persists across instances and deploys
3. Add a request queue (Celery + Redis) so WHOIS API calls (8s timeout) don't block the Flask thread
4. Cache WHOIS results per domain in Redis with a 24h TTL — the same domain doesn't need to be checked 1000 times
5. Cache identical offer text analysis results with a short TTL
6. Run the LLM call asynchronously — return the rule-based result immediately, stream the AI review separately
7. Move to gunicorn with multiple workers (`--workers 4`)

**Q: How would you improve the model accuracy significantly?**
1. Collect real labeled offer letters from user feedback — 500+ real examples would outperform any synthetic data
2. Add feature engineering: domain age as a numeric feature, email domain type (public/corporate) as a binary feature — feed these directly to the classifier alongside TF-IDF
3. Try a Random Forest or Gradient Boosting ensemble on top of TF-IDF features — often outperforms Logistic Regression on imbalanced text
4. Use sentence embeddings (e.g. `sentence-transformers`) instead of TF-IDF for semantic understanding — catches paraphrased scam patterns
5. Calibrate the model's output probability with `CalibratedClassifierCV` so the scores are actual probabilities, not just relative ranks

**Q: What would a proper authentication layer look like?**
Currently CORS is wide open. If you added user accounts:
- Add a login endpoint that issues a JWT token
- All `/api/analyze` and `/api/feedback` requests would require `Authorization: Bearer <token>` header
- Rate limiting would switch from IP-based to user-based
- User history and feedback would be associated with their account, not just sessionStorage
- The Supabase Row Level Security (RLS) policies would enforce that users can only see their own feedback rows

**Q: What are the security risks you explicitly addressed?**
1. **Input bombing** — 10,000 char limit prevents huge TF-IDF computation and LLM cost
2. **API abuse** — Flask-Limiter 10/min per IP prevents automated scraping/testing
3. **XSS** — `textContent` instead of `innerHTML` in all dynamic DOM construction
4. **Debug mode** — `debug=False` so Werkzeug debugger can't be triggered in production
5. **Secret management** — all keys via environment variables, never hardcoded (WHOIS key is the exception — should be moved to env-only)
6. **Model crash** — `try/except` around `pickle.load` with `logger.critical` + `raise` — server fails loudly at startup rather than silently at request time

**Q: How does the feedback data help retrain the model? Walk through the full loop.**
1. User analyzes an offer → backend assigns `analysis_id` (UUID)
2. User clicks "Yes, it was a scam" → frontend POSTs `{analysisId, isScam: true, offerSnippet, score, ...}` to `/api/feedback`
3. Backend saves row to Supabase `feedback` table
4. After collecting 200+ rows, export the table as CSV
5. Add a new block in `model_train.py` to load this CSV as `feedback_df`
6. Set `feedback_df["weight"] = 5.0` (real labels are more valuable than synthetic)
7. Concat with existing training data and retrain
8. New `scam_detector.pkl` replaces the old one
9. Redeploy the backend on Render
10. The live model is now smarter from real-world examples

**Q: Why did you choose Logistic Regression over a neural network?**
For this use case, Logistic Regression is the right choice because:
- It trains in seconds on a CPU — no GPU needed
- It's interpretable — you can inspect the learned weights and see which words the model considers most scammy
- It generalizes well on high-dimensional sparse data (TF-IDF output is exactly that — tens of thousands of mostly-zero features)
- The pickle file is small (~5MB) and loads in milliseconds
- It achieves 99.49% accuracy on this dataset — a neural network wouldn't add meaningful accuracy but would add enormous complexity

**Q: What happens if the OpenRouter API is down?**
The code has a full `try/except` around the OpenRouter call. If it fails for any reason (timeout, 500 error, network issue), `get_ai_review_and_signal()` returns `(None, "unavailable")`. The `ai_adjustment` for `"unavailable"` is 0 (no adjustment to the score). The response includes `aiReview: null` and the frontend shows "AI review is currently unavailable. The rule-based analysis above is still accurate." — so the product still works fully without it.

**Q: How would you add multilingual support?**
1. Detect language using `langdetect` library before analysis
2. For Hindi/regional languages, use a translation API (Google Translate or LibreTranslate) to convert to English first, then run through the existing pipeline
3. Long term: train separate TF-IDF models per language, or use a multilingual sentence-transformer model that understands 50+ languages natively
4. Add language-specific keyword lists (e.g. Hindi equivalents of "registration fee" like "पंजीकरण शुल्क")

---

## PART 4 — KEY FUNCTIONS TO KNOW BY HEART

### `normalize_text(text)`
**What it does:** Strips whitespace from start/end, collapses multiple spaces/newlines into single space.
**Why it matters:** Applied at both training AND inference. Makes sure the model sees the same format during prediction as it did during training.
```python
"  Dear  Candidate,\n\nPay  fee  " → "Dear Candidate, Pay fee"
```

### `extract_email(text)` and `extract_domain(email)`
**What they do:** Find an email address in text using regex, then split at `@` to get the domain.
**Why they matter:** The domain is used for 3 separate checks — blocklist, WHOIS age, and public domain check.
```python
"contact hr@infosys.com now" → "hr@infosys.com" → "infosys.com"
```

### `check_domain_age(domain)`
**What it does:** Calls WhoisXML API, parses creation date, calculates age in months.
**Key logic:** `age_months = (now.year - created.year) * 12 + (now.month - created.month)`
**Why it matters:** Catches domains like `tcs-hiring-2026.in` registered last week.
**Graceful failure:** Returns `{is_new: False, error: "..."}` on any exception so it never crashes the analysis.

### `clamp_score(value, low=0, high=95)`
**What it does:** `max(0, min(95, round(value)))` — forces score into range.
**Why 95 max:** Even a perfect score shouldn't claim 100% certainty. The user should always verify.

### `get_verdict(score)`
**What it does:** Converts a number to a label and color.
- ≥75 → green, "Likely legitimate offer"
- 40–74 → yellow, "Needs review before you trust it"
- <40 → red, "High scam risk detected"

### `build_verification_message(...)`
**What it does:** Builds a tailored email template based on which flags were detected.
**Key design:** Uses a `set` for O(1) flag title lookup. Different flags → different paragraphs. Not a static template.

### `supabase_insert(table, row)`
**What it does:** POSTs a row to Supabase REST API. Returns `True` on 200/201, `False` otherwise.
**Why REST not SQL:** Supabase exposes a REST endpoint (`/rest/v1/tablename`) that accepts JSON inserts. No SQL driver needed. Works from any HTTP client.

### Score blending formula
```python
base_score        = (1 - scam_probability) * 100        # ML model output, 0–100
score_after_model = (base_score * 0.55) + 20            # reduce ML weight, add floor
score_after_rules = score_after_model - risk_penalty + legitimacy_bonus
pre_ai_score      = clamp_score(score_after_rules)      # clamp 0–95
final_score       = clamp_score(pre_ai_score + ai_adjustment)  # AI nudge ±3/5
```

### `buildFlagCard(title, detail, severity, delay)` (JavaScript)
**What it does:** Creates a flag card DOM element safely (no innerHTML).
**Key security:** Uses `h4.textContent = title` — never `.innerHTML`. Prevents XSS.
**Stagger animation:** `el.style.animationDelay = delay + "ms"` — each card appears 80ms after the previous one.

### `setGauge(score, colorClass)` (JavaScript)
**What it does:** Animates the SVG gauge needle and arc.
**Key math:**
```javascript
const ratio   = score / 100
const offset  = 251.2 - (ratio * 251.2)   // how much of the arc to hide
const degrees = -90 + (ratio * 180)        // needle angle: -90° = left, +90° = right
```

### `submitFeedback(isScam)` (JavaScript)
**What it does:** POSTs to `/api/feedback` with the analysis data and user's verdict.
**Key guard:** `feedbackSent` boolean — prevents double-submission if user clicks both buttons.
**Graceful failure:** If the server is unreachable, resets `feedbackSent = false` so user can try again.

---

## PART 5 — THINGS TO SAY IF ASKED "WHAT WOULD YOU DO DIFFERENTLY?"

1. **Use a proper vector database (Pinecone/Qdrant)** — store embeddings of known scam offers and do similarity search instead of keyword matching
2. **Add server-side sessions** — right now history is in `sessionStorage` (browser only, lost on refresh)
3. **Move to a proper database for rate limiting** — Redis instead of in-memory, so limits persist across Render redeploys
4. **Add a staging environment** — currently there's only production. Any code push immediately affects live users
5. **Add monitoring** — no Sentry, no uptime monitoring, no error alerting. A silent crash would go unnoticed
6. **CI/CD pipeline** — add GitHub Actions to run tests automatically before every push
7. **The synthetic training data** — 200 samples is minimal. The feedback loop collecting real labeled offers is the most impactful next step

---

*This document covers every line of code in HireWise. Read it once before any interview and you'll be able to answer questions at any level.*
