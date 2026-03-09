import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

data = {
    "age":[25,45,50,35,60,40,55,30,65,70],
    "bp":[80,140,150,120,160,130,145,110,170,180],
    "sugar":[90,200,210,110,230,180,195,100,240,250],
    "disease":[0,1,1,0,1,0,1,0,1,1]
}

df = pd.DataFrame(data)

X = df[["age","bp","sugar"]]
y = df["disease"]

model = RandomForestClassifier()

model.fit(X,y)

joblib.dump(model,"disease_model.pkl")

print("Model Saved")