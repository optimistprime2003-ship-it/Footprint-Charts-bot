from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import os
import logging
import asyncio
from engine import OrderFlowEngine
from dotenv import load_dotenv

# =========================
# LOAD ENVIRONMENT VARIABLES
# =========================
load_dotenv()

# =========================
# LOGGING CONFIG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# =========================
# ENGINE INSTANCE
# =========================
engine = OrderFlowEngine()

# =========================
# API CONFIG
# =========================
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# =========================
# VALIDATION
# =========================
if not API_KEY or not API_SECRET:
    logger.warning("Binance API keys are missing!")

# =========================
# LIFESPAN STARTUP
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting BTC Order Flow Engine...")

    # Start engine in background
    task = asyncio.create_task(
        engine.start(API_KEY, API_SECRET)
    )

    yield

    logger.info("Shutting down BTC Order Flow Engine...")

    # Cancel background task gracefully
    task.cancel()

# =========================
# FASTAPI APP
# =========================
app = FastAPI(
    title="BTC Order Flow Bot",
    description="Advanced Real-Time BTC Order Flow Analytics API",
    version="2.0.0",
    lifespan=lifespan
)

# =========================
# ROOT ENDPOINT
# =========================
@app.get("/")
async def home():

    return {
        "status": "ONLINE",
        "bot": "BTC Order Flow Bot",
        "symbol": "BTCUSDT",
        "last_price": engine.last_price,
        "cumulative_delta": engine.cumulative_delta,
        "active_connections": getattr(engine, "active_connections", 1)
    }

# =========================
# FOOTPRINT DATA
# =========================
@app.get("/footprint")
async def get_footprint():

    try:
        sorted_prices = sorted(
            engine.price_ladder.keys(),
            reverse=True
        )[:15]

        data = {
            str(price): engine.price_ladder[price]
            for price in sorted_prices
        }

        return {
            "levels": len(data),
            "data": data
        }

    except Exception as e:
        logger.error(f"Footprint Error: {e}")

        return {
            "error": str(e)
        }

# =========================
# MARKET STATS
# =========================
@app.get("/stats")
async def get_stats():

    return {
        "4h_high": engine.high_4h,
        "4h_low": engine.low_4h,
        "current_delta": engine.cumulative_delta,
        "last_price": engine.last_price
    }

# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
async def health():

    return {
        "server": "running",
        "engine_status": "active",
        "api_keys_loaded": bool(API_KEY and API_SECRET)
    }

# =========================
# RESET DELTA
# =========================
@app.post("/reset-delta")
async def reset_delta():

    engine.cumulative_delta = 0

    return {
        "message": "Cumulative delta reset successfully"
    }

# =========================
# LIVE SIGNAL ENDPOINT
# =========================
@app.get("/signal")
async def get_signal():

    delta = engine.cumulative_delta

    if delta > 0:
        signal = "BUY"
    elif delta < 0:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    return {
        "signal": signal,
        "delta": delta,
        "price": engine.last_price
    }

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
