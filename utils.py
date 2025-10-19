# utils.py

async def get_last_n_rounds(n=100, collection=None):
    """
    Get the last n rounds for sequence-based features (default n=100).
    Includes CRITICAL PRE-PROCESSING to convert string numbers from MongoDB into integers.
    """
    rounds = await collection.find().sort("timestamp", -1).limit(n).to_list(n)
    
    # CRITICAL PRE-PROCESSING: Convert fields for safe feature engineering
    for r in rounds:
        # Convert 'number' from string (as stored by OCR) to integer for math
        if isinstance(r.get("number"), str) and r.get("number").isdigit():
            r["number"] = int(r["number"])
        # Ensure color/size are lowercase strings for consistent comparison
        r["color"] = r.get("color", "N/A").lower()
        r["size"] = r.get("size", "N/A").lower()
        
    rounds.reverse()
    return rounds


def extract_features(rounds, current_round):
    """
    Build rich features for the model, leveraging up to 100 rounds for stability 
    and deep features, including the Zig-Zag pattern.
    """
    
    current_round_number = current_round.get("number")
    
    # 1. Base Features
    features = {
        "number": current_round_number, 
        "is_big": 1 if current_round.get("size", "").lower() == "big" else 0,
    }
    
    # --- Feature Window Definitions ---
    full_history = rounds
    history_length = len(full_history) 
    medium_history = rounds[-50:]
    short_history = rounds[-10:]
    
    # 2. Lagged Features (Immediate History - Last 5 rounds)
    history_5 = rounds[-5:] 
    
    # --- CRITICAL NEW FEATURE: ZIG-ZAG PATTERN CHECK ---
    is_alternating_3 = 0
    # Check if we have at least 3 historical rounds (for S3, S2, S1)
    if len(history_5) >= 3:
        s1 = history_5[-1]['size'] # Most recent (last one in history)
        s2 = history_5[-2]['size'] # Second most recent
        s3 = history_5[-3]['size'] # Third most recent
        
        # Check for strict alternation (S1 != S2 and S2 != S3)
        if s1 != s2 and s2 != s3:
            # If the pattern is Alternating (Small-Big-Small or Big-Small-Big), set flag to 1
            is_alternating_3 = 1

    features["is_alternating_3"] = is_alternating_3 
    # --- END CRITICAL NEW FEATURE ---

    
    for i, r in enumerate(history_5):
        lag = len(history_5) - i 
        
        features[f"lag_color_{lag}"] = 1 if r["color"] == "red" else 0
        features[f"lag_size_{lag}"] = 1 if r["size"] == "big" else 0
        
        if i > 0:
             features[f"lag_num_diff_{lag}"] = r["number"] - history_5[i-1]["number"]
        else:
             features[f"lag_num_diff_{lag}"] = 0
             
    # 3. Deep Frequency and Ratio Analysis (LONG-TERM CONTEXT)
    if history_length > 10:
        
        red_count_100 = sum(1 for r in full_history if r["color"] == "red")
        big_count_100 = sum(1 for r in full_history if r["size"] == "big")
        
        # Feature 1 & 2: Ratios over the full available history (Stabilizes prediction)
        features["red_ratio_100"] = red_count_100 / history_length
        features["big_ratio_100"] = big_count_100 / history_length
        
        # Feature 3: Medium-term frequency (Last 50 rounds)
        big_count_50 = sum(1 for r in medium_history if r["size"] == "big")
        features["big_freq_50"] = big_count_50 / len(medium_history)

    
    # 4. Short-Term Frequency (Last 10 rounds)
    features["red_freq_10"] = sum(1 for r in short_history if r["color"] == "red")
    features["green_freq_10"] = sum(1 for r in short_history if r["color"] == "green")
    features["big_freq_10"] = sum(1 for r in short_history if r["size"] == "big")
    features["small_freq_10"] = sum(1 for r in short_history if r["size"] == "small")
    
    # 5. Current Streak Length
    current_color = current_round.get("color", "").lower()
    color_streak = 0
    
    for r in reversed(rounds):
        if r["color"] == current_color:
            color_streak += 1
        else:
            break
            
    features["current_color_streak"] = color_streak
    
    return features