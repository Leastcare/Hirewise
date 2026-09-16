"""
HireWise — model_train.py
Trains a TF-IDF + Logistic Regression scam detector on three datasets:
  1. fake_job_postings.csv       — structured job posting data (title, description, etc.)
  2. processed_labeled_dataset_without_encoding.xlsx — supplementary labeled dataset
  3. offer_letters_dataset.csv   — synthetic offer-letter samples (real inference domain)

The offer-letter dataset is upweighted 3× during training so the model
learns the vocabulary and patterns that match what users actually paste in.

All text goes through normalize_text() (same function used at inference)
so training and inference distributions are aligned.
"""

import re

import pandas as pd
import pickle
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
import numpy as np


# ── Same normalization used at inference time in app.py ───────────────────────
def normalize_text(text: str) -> str:
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


# ── 1. Job postings CSV ───────────────────────────────────────────────────────
print("Loading fake_job_postings.csv ...")
csv_df = pd.read_csv("../fake_job_postings.csv")
csv_df["text"] = (
    csv_df["title"].fillna("") + " " +
    csv_df["company_profile"].fillna("") + " " +
    csv_df["description"].fillna("") + " " +
    csv_df["requirements"].fillna("") + " " +
    csv_df["benefits"].fillna("")
)
csv_df = csv_df[["text", "fraudulent"]].copy()
csv_df.rename(columns={"fraudulent": "label"}, inplace=True)
csv_df["weight"] = 1.0
print(f"  rows: {len(csv_df)}, scam: {csv_df['label'].sum()}")

# ── 2. Supplementary XLSX ─────────────────────────────────────────────────────
print("Loading processed_labeled_dataset_without_encoding.xlsx ...")
xlsx_df = pd.read_excel("../processed_labeled_dataset_without_encoding.xlsx")
xlsx_df = xlsx_df[["text", "fraudulent"]].copy()
xlsx_df.rename(columns={"fraudulent": "label"}, inplace=True)
xlsx_df["weight"] = 1.0
print(f"  rows: {len(xlsx_df)}, scam: {xlsx_df['label'].sum()}")

# ── 3. Offer-letter dataset (upweighted 3×) ───────────────────────────────────
print("Loading offer_letters_dataset.csv ...")
ol_df = pd.read_csv("offer_letters_dataset.csv")
ol_df = ol_df[["text", "label"]].copy()
ol_df["weight"] = 3.0          # upweight: offer letters match the real inference domain
print(f"  rows: {len(ol_df)}, scam: {ol_df['label'].sum()}")

# ── Combine ───────────────────────────────────────────────────────────────────
df = pd.concat([csv_df, xlsx_df, ol_df], ignore_index=True)
df["text"]  = df["text"].apply(normalize_text)
df["label"] = pd.to_numeric(df["label"], errors="coerce")
df = df.dropna(subset=["label"])
df["label"] = df["label"].astype(int)
df = df[df["text"].str.strip() != ""]
print(f"\nTotal after merge & clean: {len(df)} rows, scam: {df['label'].sum()}")

# ── Train / test split (stratified) ──────────────────────────────────────────
X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
    df["text"],
    df["label"],
    df["weight"],
    test_size=0.2,
    random_state=42,
    stratify=df["label"],
)

# ── Pipeline ──────────────────────────────────────────────────────────────────
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        stop_words="english",
        max_features=35000,          # slightly larger vocabulary
        ngram_range=(1, 2),
        sublinear_tf=True,           # log-scale TF — helps with long documents
        min_df=2,                    # ignore terms appearing in only one doc
    )),
    ("clf", LogisticRegression(
        max_iter=3000,
        class_weight="balanced",
        C=1.5,                       # slightly less regularisation vs default
        solver="lbfgs",
    )),
])

print("\nTraining model...")
model.fit(X_train, y_train, clf__sample_weight=w_train)

# ── Evaluation ────────────────────────────────────────────────────────────────
y_pred      = model.predict(X_test)
y_pred_proba = model.predict_proba(X_test)[:, 1]

print(f"\nAccuracy:  {accuracy_score(y_test, y_pred):.4f}")
print(classification_report(y_test, y_pred, target_names=["Legit", "Scam"]))

# Calibration check on offer-letter test split
ol_mask = w_test == 3.0
if ol_mask.sum() > 0:
    ol_acc = accuracy_score(y_test[ol_mask], y_pred[ol_mask])
    print(f"Offer-letter subset accuracy: {ol_acc:.4f} ({ol_mask.sum()} samples)")

# ── Save ──────────────────────────────────────────────────────────────────────
out_path = "model/scam_detector.pkl"
with open(out_path, "wb") as f:
    pickle.dump(model, f)
print(f"\nModel saved → {out_path}")
