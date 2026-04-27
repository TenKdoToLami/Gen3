import os
import sys
import json
from datetime import datetime

# Ensure src is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.helpers.data_provider import update_market_data
from src.strategies.v3_strategy import V3Strategy

def main():
    print("==================================================")
    print("       GEN3 TRADING BOT - SIGNAL GENERATOR        ")
    print("==================================================")
    
    # 1. Load Champion DNA
    config_path = os.path.join("config", "v3_champion.json")
    if not os.path.exists(config_path):
        print(f"Error: Champion file not found at {config_path}")
        return

    with open(config_path, "r") as f:
        genome = json.load(f)
    
    # 2. Fetch/Sync Market Data (SQL Incremental)
    df = update_market_data()
    latest_date = df.index[-1]
    latest_data = df.iloc[-1].to_dict()
    
    print(f"Latest Market Data: {latest_date.date()}")
    print(f"SPY Close: ${latest_data['close']:.2f} | VIX: {latest_data['vix']:.2f} | YC: {latest_data['yield_curve']:.3f}")
    print("--------------------------------------------------")

    # 3. Initialize Strategy and Run History (to warm up indicators)
    strategy = V3Strategy(genome)
    
    # We feed the last 250 days to ensure all SMA/EMA/MACD are fully warmed up
    history = df.tail(250)
    current_allocation = None
    
    for date, row in history.iterrows():
        price_data = row.to_dict()
        current_allocation = strategy.on_data(price_data)

    # 4. Final Verdict
    verdict = list(current_allocation.keys())[0]
    
    print(f"VERDICT FOR NEXT SESSION: {verdict}")
    print("--------------------------------------------------")
    
    # 5. Log Signal
    log_path = os.path.join("logs", "signal_history.csv")
    log_exists = os.path.exists(log_path)
    
    with open(log_path, "a") as f:
        if not log_exists:
            f.write("date,spy_close,vix,yield_curve,signal\n")
        f.write(f"{latest_date.date()},{latest_data['close']},{latest_data['vix']},{latest_data['yield_curve']},{verdict}\n")
    
    print(f"Signal logged to {log_path}")
    print("==================================================")

if __name__ == "__main__":
    main()
