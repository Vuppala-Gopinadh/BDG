# model_updater.py (UPGRADE MODEL ARCHITECTURE - FINAL STABLE VERSION)

from river import linear_model, preprocessing, optim
from river.multiclass import OneVsRestClassifier
# --- CRITICAL NEW IMPORT: Use the robust Passive Aggressive Classifier ---
from river.linear_model import PAClassifier
# -----------------------------------------------------------------------
from utils import extract_features, get_last_n_rounds
import asyncio

# --- INITIALIZE ALL FOUR PRIMARY MODEL PIPELINES with PAClassifier ---

# 1. COLOR MODEL: Predicts Red vs. Non-Red
color_model_red = preprocessing.StandardScaler() | PAClassifier(
    C=0.01, # Regularization term
    
)

# 2. VIOLET MODEL: Predicts Violet vs. Non-Violet
color_model_violet = preprocessing.StandardScaler() | PAClassifier(
    C=0.01,
    
)

# 3. SIZE MODEL: Predicts Big vs. Small
size_model_big = preprocessing.StandardScaler() | PAClassifier(
    C=0.01,

)

# 4. NUMBER MODEL (Multi-Class: Use Logistic Regression, which is stable)
number_model = preprocessing.StandardScaler() | OneVsRestClassifier(
    classifier=linear_model.LogisticRegression(
        optimizer=optim.AdaGrad(0.05)
    )
)

# ... (the rest of the update_model function remains the same)

# ... (the rest of the update_model function remains the same)

# model_updater.py (Inside async def update_model)

async def update_model(current_round, collection):
    # NOTE: Assuming get_last_n_rounds is set to n=100 in utils.py
    last_rounds = await get_last_n_rounds(100, collection) 
    
    # CRASH PREVENTION: 
    if len(last_rounds) < 5: 
        return {
            "prob_red": 0.5, "prob_green": 0.5, "prob_violet": 0.0,
            "prob_big": 0.5, "prob_small": 0.5,
            "prob_numbers": {str(i): 0.1 for i in range(10)}
        }
    
    x = extract_features(last_rounds, current_round)

    print(f"[ARFC INPUT] Zig-Zag Feature: {x.get('is_alternating_3')}")

    # --- 1. DEFINE OUTCOMES (y) FOR TRAINING ---
    current_color = current_round.get("color", "").lower()
    current_size = current_round.get("size", "").lower()
    current_number = int(current_round.get("number"))
    is_violet = current_round.get("number") in ('0', '5')
    
    y_red = 1 if current_color == "red" else 0
    y_violet = 1 if is_violet else 0
    y_big = 1 if current_size == "big" else 0
    
    # --- 2. PREDICT FOR NEXT ROUND (Round N+1) ---
    pred_red = color_model_red.predict_proba_one(x).get(1, 0.5)
    pred_violet = color_model_violet.predict_proba_one(x).get(1, 0.0)
    pred_big = size_model_big.predict_proba_one(x).get(1, 0.5)
    pred_numbers_raw = number_model.predict_proba_one(x)
    
    # --- 3. TRAIN ALL MODELS with Round N outcome ---
    color_model_red.learn_one(x, y_red)
    color_model_violet.learn_one(x, y_violet)
    size_model_big.learn_one(x, y_big)
    number_model.learn_one(x, current_number)
    
    
    # --- 4. ASSEMBLE FINAL RESULTS (FIXED COLOR NORMALIZATION) ---
    
    # Step 1: Establish raw scores (Green is the inverse of Red's prediction)
    raw_red = pred_red
    raw_violet = pred_violet
    raw_green = 1.0 - pred_red 
    
    # Step 2: Sum the three scores (the normalization factor)
    total_raw = raw_red + raw_green + raw_violet

    # Step 3: Normalize all three probabilities by the total raw score
    # This mathematically ensures P(Red) + P(Green) + P(Violet) = 1.0
    safe_total = max(total_raw, 1e-6)
    
    prob_red_norm = raw_red / safe_total
    prob_green_norm = raw_green / safe_total
    prob_violet_norm = raw_violet / safe_total
    
    # Process Small size
    prob_small = 1.0 - pred_big
    
    # Format Number Probs
    prob_numbers = {str(k): round(v, 3) for k, v in pred_numbers_raw.items()}

    
    return {
        "prob_red": round(prob_red_norm, 3),
        "prob_green": round(prob_green_norm, 3),
        "prob_violet": round(prob_violet_norm, 3),
        "prob_big": round(pred_big, 3),
        "prob_small": round(prob_small, 3),
        "prob_numbers": prob_numbers
    }
