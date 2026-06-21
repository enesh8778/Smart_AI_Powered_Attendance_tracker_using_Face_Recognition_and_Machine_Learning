import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# Sample training data
data = {
    "present_days": [95,90,85,80,75,70,65,60,55,50],
    "late_days": [1,2,3,4,5,6,7,8,9,10],
    "attendance_percentage": [95,90,85,80,75,70,65,60,55,50],
    "risk": [
        "Low",
        "Low",
        "Low",
        "Medium",
        "Medium",
        "Medium",
        "High",
        "High",
        "High",
        "High"
    ]
}

df = pd.DataFrame(data)

X = df[
    [
        "present_days",
        "late_days",
        "attendance_percentage"
    ]
]

y = df["risk"]

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X, y)

joblib.dump(
    model,
    "prediction/attendance_model.pkl"
)

print("Model trained successfully")