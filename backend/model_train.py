import pandas as pd
import pickle
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score

csv_df = pd.read_csv("../fake_job_postings.csv")

csv_df["text"] = (
    csv_df["title"].fillna("") + " " +
    csv_df["company_profile"].fillna("") + " " +
    csv_df["description"].fillna("") + " " +
    csv_df["requirements"].fillna("") + " " +
    csv_df["benefits"].fillna("")
)

csv_df = csv_df[["text", "fraudulent"]].copy()
csv_df["label"] = csv_df["fraudulent"]
csv_df = csv_df[["text", "label"]]

xlsx_df = pd.read_excel("../processed_labeled_dataset_without_encoding.xlsx")
xlsx_df = xlsx_df[["text", "fraudulent"]].copy()
xlsx_df["label"] = xlsx_df["fraudulent"]
xlsx_df = xlsx_df[["text", "label"]]

df = pd.concat([csv_df, xlsx_df], ignore_index=True)

df["text"] = df["text"].fillna("").astype(str)
df["label"] = pd.to_numeric(df["label"], errors="coerce")
df = df.dropna(subset=["label"])
df["label"] = df["label"].astype(int)
df = df[df["text"].str.strip() != ""]

X_train, X_test, y_train, y_test = train_test_split(
    df["text"],
    df["label"],
    test_size=0.2,
    random_state=42,
    stratify=df["label"]
)

model = Pipeline([
    ("tfidf", TfidfVectorizer(
        stop_words="english",
        max_features=30000,
        ngram_range=(1, 2)
    )),
    ("clf", LogisticRegression(
        max_iter=3000,
        class_weight="balanced"
    ))
])

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

with open("model/scam_detector.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model saved to model/scam_detector.pkl")