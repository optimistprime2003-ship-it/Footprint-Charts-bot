from fastapi import FastAPI, BackgroundTasks
import uvicorn
import os
import logging
import asyncio
from engine import OrderFlowEngine
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="BTC Order Flow Bot")
engine = OrderFlowEngine()

# --- CONFIG ---
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

@app.on_event("startup")
async def startup_event():
    # Run the engine in the background
    asyncio.create_task(engine.start(API_KEY, API_SECRET))

@app.get("/")
def home():
    return {
        "status": "Order Flow Bot Active",
        "symbol": "BTCUSDT",
        "cumulative_delta": engine.cumulative_delta,
        "last_price": engine.last_price
    }

@app.get("/footprint")
def get_footprint():
    # Return last 10 price levels for dashboard
    sorted_prices = sorted(engine.price_ladder.keys(), reverse=True)[:10]
    return {p: engine.price_ladder[p] for p in sorted_prices}

@app.get("/stats")
def get_stats():
    return {
        "4h_high": engine.high_4h,
        "4h_low": engine.low_4h,
        "current_delta": engine.cumulative_delta
    }

if __name__ == "__main__":
    # Standard Render Port 10000
    uvicorn.run(app, host="0.0.0.0", port=10000)
