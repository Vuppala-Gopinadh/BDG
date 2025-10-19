from fastapi import FastAPI
from database import collection
import asyncio, datetime, aiohttp, time 
from model_updater import update_model # Keep this if model_updater is needed for API processing

# --- Helper to use the stable UTC time ---
def get_utc_now():
    return datetime.datetime.now(datetime.UTC)

# --- FastAPI Initialization (Crucially, without the lifespan handler) ---
app = FastAPI(title="Live Betting Predictor") 

# --- NOTE: All unstable background task definitions (fetch_bdg_round, fetch_loop) must be removed. ---

# -------------------- API Endpoints (Final Structure) --------------------

@app.get("/latest_prediction")
async def latest_prediction():
    """Fetches the latest prediction round."""
    latest = await collection.find().sort("timestamp", -1).limit(1).to_list(1)
    if latest:
        return latest[0]
    return {"message": "No data yet."}

@app.get("/history")
async def history(limit: int = 20):
    """Fetches the N most recent raw rounds."""
    data = await collection.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return data

@app.get("/latest_data")
async def latest_data(limit: int = 50):
    """Fetches the N most recent rounds with predictions and calculated accuracy."""
    
    # 1. Fetch latest data from MongoDB
    data = await collection.find(
        {}, 
        {"_id": 0, "period": 1, "color": 1, "size": 1, "number": 1, 
         "prob_red": 1, "prob_green": 1, "prob_violet": 1,
         "prob_size_big": 1, "prob_size_small": 1, "prob_numbers": 1, "timestamp": 1} 
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    # 2. Process and add accuracy flag (for visualization)
    for record in data:
        # Determine the model's color guess
        max_color_prob = max(record.get('prob_red', 0), record.get('prob_green', 0), record.get('prob_violet', 0))
        predicted_color = None
        if max_color_prob == record.get('prob_red'):
            predicted_color = 'Red'
        elif max_color_prob == record.get('prob_green'):
            predicted_color = 'Green'
        elif max_color_prob == record.get('prob_violet'):
            predicted_color = 'Violet'
        else:
            predicted_color = 'Unknown'

        # Determine the model's size guess
        predicted_size = 'Big' if record.get('prob_size_big', 0.5) > 0.5 else 'Small'
        
        # Calculate Match
        record['color_match'] = (predicted_color.lower() == record['color'].lower())
        record['predicted_color'] = predicted_color
        
        record['size_match'] = (predicted_size.lower() == record['size'].lower())
        record['predicted_size'] = predicted_size

    return data

@app.get("/raw_logs")
async def raw_logs(limit: int = 20):
    """Fetches the N most recent raw log/prediction records."""
    data = await collection.find(
        {},
        {"_id": 0} 
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    return data

#      uvicorn main:app --host 0.0.0.0 --port 8000