import numpy as np
import joblib

# Dummy Prediction Model

class RoadModel:
    
    def predict(self, image):
        
        condition = np.random.choice([
            "Good",
            "Moderate",
            "Poor",
            "Very Poor"
        ])

        severity = np.random.choice([
            "Low",
            "Medium",
            "High",
            "Critical"
        ])

        maintenance = np.random.choice([
            "No Maintenance",
            "Routine Maintenance",
            "Repair Required",
            "Immediate Repair"
        ])

        priority = np.random.choice([
            "Low",
            "Medium",
            "High",
            "Critical"
        ])

        confidence = round(np.random.uniform(80, 98), 2)

        crack_density = round(np.random.uniform(0.1, 0.9), 2)

        return {
            "condition": condition,
            "severity": severity,
            "maintenance": maintenance,
            "priority": priority,
            "confidence": confidence,
            "crack": crack_density
        }


# Save Model
model = RoadModel()
joblib.dump(model, "model/road_model.pkl")

print("Model Saved Successfully")