"""Train reproducible diabetes classifiers and export one deployable pipeline."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "diabetes_prediction_dataset.csv"
ART = ROOT / "artifacts"
RES = ROOT / "results"
TARGET = "diabetes"
NUMERIC = ["age", "bmi", "hbA1c_level", "blood_glucose_level", "hypertension", "heart_disease"]
CATEGORICAL = ["gender", "smoking_history"]
FEATURES = CATEGORICAL + NUMERIC


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_row(name: str, model, X, y, threshold: float, seconds: float) -> dict:
    probability = model.predict_proba(X)[:, 1]
    prediction = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()
    return {
        "model": name, "threshold": round(float(threshold), 4), "accuracy": accuracy_score(y, prediction),
        "precision": precision_score(y, prediction, zero_division=0),
        "recall": recall_score(y, prediction, zero_division=0),
        "f1": f1_score(y, prediction, zero_division=0),
        "roc_auc": roc_auc_score(y, probability), "pr_auc": average_precision_score(y, probability),
        "brier": brier_score_loss(y, probability), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "train_seconds": round(seconds, 3),
    }


def choose_threshold(model, X_val, y_val) -> float:
    probability = model.predict_proba(X_val)[:, 1]
    candidates = np.linspace(0.10, 0.80, 141)
    values = [f1_score(y_val, probability >= t) for t in candidates]
    return float(candidates[int(np.argmax(values))])


def main():
    ART.mkdir(exist_ok=True); RES.mkdir(exist_ok=True)
    df = pd.read_csv(DATA)
    df = df.drop_duplicates().reset_index(drop=True)
    X, y = df[FEATURES].copy(), df[TARGET].astype(int)
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=.30, stratify=y, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=.50, stratify=y_temp, random_state=42)
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    preprocess = ColumnTransformer([("num", numeric, NUMERIC), ("cat", categorical, CATEGORICAL)])
    models = {
        "Logistic Regression": LogisticRegression(max_iter=800, class_weight="balanced", C=.8, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=180, min_samples_leaf=3, class_weight="balanced_subsample",
                                                 n_jobs=-1, random_state=42),
        "MLP": MLPClassifier(hidden_layer_sizes=(32, 16), alpha=.001, batch_size=512, max_iter=80,
                             early_stopping=True, validation_fraction=.12, n_iter_no_change=8, random_state=42),
    }
    rows, trained = [], {}
    for name, estimator in models.items():
        pipe = Pipeline([("preprocess", preprocess), ("model", estimator)])
        started = time.perf_counter(); pipe.fit(X_train, y_train); seconds = time.perf_counter() - started
        threshold = choose_threshold(pipe, X_val, y_val)
        validation = metric_row(name, pipe, X_val, y_val, threshold, seconds)
        test = metric_row(name, pipe, X_test, y_test, threshold, seconds)
        rows.append({"validation": validation, "test": test}); trained[name] = (pipe, threshold)
        joblib.dump({"pipeline": pipe, "threshold": threshold, "features": FEATURES}, ART / f"{name.lower().replace(' ', '_')}.joblib")
    best_name = max(rows, key=lambda row: row["validation"]["f1"])["validation"]["model"]
    best_model, best_threshold = trained[best_name]
    joblib.dump({"pipeline": best_model, "threshold": best_threshold, "features": FEATURES,
                 "model_name": best_name}, ART / "diabetes_model.joblib")
    baselines = {c: float(X_train[c].median()) for c in NUMERIC}
    baselines.update({c: str(X_train[c].mode().iloc[0]) for c in CATEGORICAL})
    gender = []
    best_prob = best_model.predict_proba(X_test)[:, 1]
    best_pred = best_prob >= best_threshold
    for value in sorted(X_test.gender.astype(str).unique()):
        mask = X_test.gender.astype(str).eq(value).to_numpy()
        if mask.sum():
            gender.append({"group": value, "n": int(mask.sum()), "recall": recall_score(y_test.to_numpy()[mask], best_pred[mask], zero_division=0),
                           "positive_rate": float(best_pred[mask].mean())})
    metadata = {
        "dataset": {"path": "data/diabetes_prediction_dataset.csv", "sha256": file_sha256(DATA),
                    "raw_rows": int(pd.read_csv(DATA, usecols=[TARGET]).shape[0]), "deduplicated_rows": int(len(df)),
                    "positive_rate": float(y.mean())},
        "features": FEATURES, "numeric": NUMERIC, "categorical": CATEGORICAL,
        "splits": {"train": len(X_train), "validation": len(X_val), "test": len(X_test)},
        "selection": {"criterion": "validation F1", "model": best_name, "threshold": best_threshold},
        "baselines": baselines, "gender_audit": gender, "models": rows,
        "notice": "Educational risk score; not a diagnosis or treatment recommendation.",
    }
    (ART / "model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame([{**r["test"], "split": "test"} for r in rows]).to_csv(RES / "model_comparison.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({"best": best_name, "threshold": best_threshold, "test_f1": max(rows, key=lambda r:r['validation']['f1'])['test']['f1']}, ensure_ascii=False))


if __name__ == "__main__":
    main()
