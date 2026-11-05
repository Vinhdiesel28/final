from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class DiabetesModelService:
    def __init__(self):
        artifact = joblib.load(ROOT / "artifacts/diabetes_model.joblib")
        self.pipeline = artifact["pipeline"]
        self.threshold = float(artifact["threshold"])
        self.model_name = artifact["model_name"]
        self.metadata = json.loads((ROOT / "artifacts/model_metadata.json").read_text(encoding="utf-8"))
        self.reference_pipeline = self.pipeline
        self.reference_threshold = self.threshold
        self.reference_name = self.model_name
        if (ROOT/'artifacts/pytorch_mlp.pt').exists():
            from torch_model import TorchPipeline
            self.pipeline = TorchPipeline(ROOT/'artifacts/pytorch_mlp.pt', joblib.load(ROOT/'artifacts/pytorch_preprocess.joblib'))
            torch_meta=json.loads((ROOT/'artifacts/pytorch_metadata.json').read_text(encoding='utf-8'))
            self.threshold=float(torch_meta['threshold'])
            self.model_name='PyTorch MLP'

    @staticmethod
    def validate(profile: dict) -> list[dict]:
        errors = []
        rules = {"age": (0, 120), "bmi": (10, 80), "hbA1c_level": (2, 20),
                 "blood_glucose_level": (40, 500), "hypertension": (0, 1), "heart_disease": (0, 1)}
        for field, (low, high) in rules.items():
            try:
                value = float(profile[field])
                if not low <= value <= high:
                    errors.append({"field": field, "message": f"Giá trị phải nằm trong khoảng {low}–{high}."})
                elif field in {'hypertension','heart_disease'} and value not in (0,1):
                    errors.append({'field':field,'message':'Chỉ nhận 0 hoặc 1.'})
            except (KeyError, TypeError, ValueError):
                errors.append({"field": field, "message": "Thiếu hoặc không phải số hợp lệ."})
        if str(profile.get("gender", "")) not in {"Female", "Male", "Other"}:
            errors.append({"field": "gender", "message": "Giới tính không thuộc danh sách cho phép."})
        allowed = {"never", "No Info", "current", "former", "ever", "not current"}
        if str(profile.get("smoking_history", "")) not in allowed:
            errors.append({"field": "smoking_history", "message": "Tiền sử hút thuốc không hợp lệ."})
        return errors

    def predict(self, profile: dict) -> dict:
        row = pd.DataFrame([{k: profile[k] for k in self.metadata["features"]}])
        for feature in ["age", "bmi", "hbA1c_level", "blood_glucose_level", "hypertension", "heart_disease"]:
            row[feature] = row[feature].astype(float)
        probability = float(self.pipeline.predict_proba(row)[0, 1])
        reference = float(self.reference_pipeline.predict_proba(row)[0,1])
        level = "low" if probability < self.threshold * .6 else "moderate" if probability < self.threshold else "high"
        impacts = []
        for feature, baseline in self.metadata["baselines"].items():
            changed = row.copy(); changed.loc[0, feature] = baseline
            perturbed = float(self.pipeline.predict_proba(changed)[0, 1])
            impacts.append({"feature": feature, "value": str(profile[feature]), "baseline": str(baseline),
                            "impact": round(probability - perturbed, 5)})
        impacts.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return {"model": self.model_name, "probability": round(probability, 6), "threshold": round(self.threshold, 4),
                "predicted_class": int(probability >= self.threshold), "risk_level": level,
                "feature_impacts": impacts[:6], "model_version": "2.0.0",
                "second_opinion": {'model':self.reference_name,'probability':reference,
                    'threshold':self.reference_threshold,'predicted_class':int(reference>=self.reference_threshold)}}
