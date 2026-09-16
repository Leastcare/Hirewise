# HireWise

A job-offer scam detection tool. Paste (or upload) an offer letter and HireWise runs it through a rule engine, a trained ML model, and an optional LLM review to produce a risk score, a list of red flags, and a ready-to-send verification message.

---

## How it works

1. **Rule engine** — checks for payment requests, urgency language, suspicious phrases, public email domains, and positive legitimacy signals.
2. **ML model** — TF-IDF + Logistic Regression trained on labelled job-posting datasets. Provides a scam probability that is blended with the rule score (weight 0.55).
3. **LLM review** (optional) — calls OpenRouter to generate a 3-bullet narrative review and a discrete risk signal that nudges the final score.

---

## Project structure

```
Hirewise/
├── backend/
│   ├── app.py              # Flask API
│   ├── model_train.py      # Model training script
│   ├── requirements.txt    # Pinned Python dependencies
│   └── model/
│       └── scam_detector.pkl
├── frontend/
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   └── README.md
├── fake_job_postings.csv
└── processed_labeled_dataset_without_encoding.xlsx
```

---

## Backend

### Requirements

- Python 3.11+
- Dependencies listed in `backend/requirements.txt` (all pinned)

### Setup

```bash
cd backend
pip install -r requirements.txt
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | No | Enables the AI narrative review. Without it the analysis still works — the AI review section shows a fallback message. |

### Running locally

```bash
cd backend
python app.py
```

For production, use gunicorn (already in `requirements.txt`):

```bash
gunicorn app:app --workers 2 --bind 0.0.0.0:5000
```

### API

#### `GET /api/ping`
Lightweight health-check / wake-up endpoint. Returns `{"status": "ok"}`.

#### `POST /api/analyze`
Rate-limited: **10 requests per minute per IP**.

Request body:
```json
{ "offerText": "..." }
```

- Maximum input: **10,000 characters**. Returns 400 if exceeded.

Response:
```json
{
  "verdict":             { "label": "...", "color": "green|yellow|red" },
  "confidenceScore":     72,
  "flags":               [{ "title": "...", "detail": "...", "severity": "high|medium|low|safe" }],
  "detectedEmail":       "hr@example.com",
  "detectedDomain":      "example.com",
  "verificationMessage": "...",
  "aiReview":            "...",
  "aiSignal":            "low_risk|mixed|high_risk|unavailable"
}
```

#### `POST /api/extract`
Rate-limited: **10 requests per minute per IP**.

Accepts a multipart form upload with a `.pdf` or `.txt` file (max 2 MB).
Returns `{ "text": "extracted text..." }`.

---

## Frontend

See `frontend/README.md`.

---

## Retraining the model

```bash
cd backend
python model_train.py
```

The script reads `fake_job_postings.csv` and `processed_labeled_dataset_without_encoding.xlsx` from the project root, trains a TF-IDF + Logistic Regression pipeline, prints accuracy and a classification report, and saves the model to `backend/model/scam_detector.pkl`.

---

## Deployment

The backend is deployed on [Render](https://render.com). The free tier spins down after inactivity; the frontend sends a `GET /api/ping` on page load to wake it up before the user clicks Analyze.

Set `OPENROUTER_API_KEY` as an environment variable in your Render service settings to enable the AI review feature.
