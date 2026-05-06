import os
import logging
import asyncio
import numpy as np
from binance import AsyncClient, BinanceSocketManager
from datetime import datetime

# --- SETTINGS ---
SYMBOL = "BTCUSDT"
TICK_SIZE = 1.0  # Group trades every $1.00
IMBALANCE_RATIO = 3.0  # 300% difference for imbalance
STACK_REQUIRED = 3  # How many levels make a 'stack'
RISK_AMOUNT = 1.0  # $1.00 risk for a $100 account

class OrderFlowEngine:
    def __init__(self):
        self.price_ladder = {}  # {price: {'bid': vol, 'ask': vol}}
        self.cumulative_delta = 0
        self.last_price = 0
        self.high_4h = 0
        self.low_4h = 0

    async def start(self, api_key, api_secret):
        client = await AsyncClient.create(api_key, api_secret)
        bm = BinanceSocketManager(client)
        ts = bm.aggtrade_socket(SYMBOL)
        
        # Initial 4H Range Fetch
        klines = await client.get_klines(symbol=SYMBOL, interval='4h', limit=1)
        self.high_4h = float(klines[0][2])
        self.low_4h = float(klines[0][3])

        logging.info(f"Engine Online. Tracking {SYMBOL} @ {TICK_SIZE} ticks.")

        async with ts as tscm:
            while True:
                res = await tscm.recv()
                await self.process_trade(res, client)

    def get_tick_price(self, price):
        return round(float(price) / TICK_SIZE) * TICK_SIZE

    async def process_trade(self, trade, client):
        price = float(trade['p'])
        qty = float(trade['q'])
        is_buyer_maker = trade['m'] # True = Sell (Market hit Bid), False = Buy (Market hit Ask)
        tick = self.get_tick_price(price)

        # 1. Update Price Ladder
        if tick not in self.price_ladder:
            self.price_ladder[tick] = {'bid': 0, 'ask': 0}
        
        if is_buyer_maker:
            self.price_ladder[tick]['bid'] += qty
            self.cumulative_delta -= qty
        else:
            self.price_ladder[tick]['ask'] += qty
            self.cumulative_delta += qty

        # 2. Check for Trapped Traders (Point 2: Delta Divergence)
        if price > self.high_4h and self.cumulative_delta < 0:
            logging.warning(f"TRAP: Price above 4H High but Delta is Negative ({self.cumulative_delta})")
            # Logic: Potential Fakeout - Consider Sell

        # 3. Check for Stacked Imbalances (Point 3)
        await self.check_imbalances(tick, price, client)
        self.last_price = price

    async def check_imbalances(self, current_tick, current_price, client):
        # Diagonal check: Ask at current vs Bid at price below
        prices = sorted(self.price_ladder.keys(), reverse=True)
        stacks = 0
        
        for i in range(len(prices) - 1):
            ask_vol = self.price_ladder[prices[i]]['ask']
            bid_vol_below = self.price_ladder[prices[i+1]]['bid']
            
            if bid_vol_below > 0 and ask_vol > (bid_vol_below * IMBALANCE_RATIO):
                stacks += 1
            else:
                stacks = 0 # Must be consecutive
            
            if stacks >= STACK_REQUIRED:
                logging.info(f"BULLISH STACKED IMBALANCE at {prices[i]}")
                await self.execute_trade("BUY", current_price, client)
                break

    async def execute_trade(self, side, price, client):
        # Calculate Position Size: $1.00 risk / 100 point Stop Loss
        stop_loss_dist = 100 
        qty = round(RISK_AMOUNT / stop_loss_dist, 5)
        
        logging.info(f"EXECUTING {side} | Qty: {qty} | Price: {price}")
        # --- UNCOMMENT TO LIVE TRADE ---
        # await client.create_order(symbol=SYMBOL, side=side, type='MARKET', quantity=qty)
