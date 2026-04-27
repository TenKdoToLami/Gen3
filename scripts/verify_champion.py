import os
import sys
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.helpers.data_provider import update_market_data
from src.strategies.v3_strategy import V3Strategy

def calculate_metrics(returns):
    cagr = (returns[-1] / returns[0]) ** (252 / len(returns)) - 1
    
    # Max Drawdown
    peak = np.maximum.accumulate(returns)
    drawdown = (returns - peak) / peak
    max_dd = np.min(drawdown)
    
    # Sharpe (assumes 0% risk free)
    daily_rets = np.diff(returns) / returns[:-1]
    sharpe = np.mean(daily_rets) / np.std(daily_rets) * np.sqrt(252) if np.std(daily_rets) > 0 else 0
    
    return cagr, max_dd, sharpe

def main():
    print("==================================================")
    print("       GEN3 CHAMPION VERIFICATION ENGINE          ")
    print("==================================================")
    
    # 1. Sync and Load Data
    df = update_market_data()
    print(f"Loaded {len(df)} days of history from database.")

    # 2. Load Champion
    with open(os.path.join("config", "v3_champion.json"), "r") as f:
        genome = json.load(f)
    
    strategy = V3Strategy(genome)
    
    # 3. Simulate
    portfolio_value = 100.0
    values = [portfolio_value]
    spy_values = [100.0]
    
    allocation = {"CASH": 1.0}
    
    for i in range(1, len(df)):
        date = df.index[i]
        prev_row = df.iloc[i-1]
        row = df.iloc[i]
        
        # Calculate daily change for SPY (and 3x proxy)
        spy_change = (row['close'] / prev_row['close']) - 1.0
        
        # Apply change to portfolio based on previous day's allocation
        if "3xSPY" in allocation:
            portfolio_value *= (1 + spy_change * 3.0)
        
        values.append(portfolio_value)
        spy_values.append(spy_values[-1] * (1 + spy_change))
        
        # Get next day's allocation
        allocation = strategy.on_data(row.to_dict())

    # 4. Results
    cagr, mdd, sharpe = calculate_metrics(np.array(values))
    spy_cagr, spy_mdd, spy_sharpe = calculate_metrics(np.array(spy_values))
    
    print(f"\nRESULTS (1993 - Present):")
    print(f"METRIC      |  GEN3 V3    |  SPY (1x)")
    print(f"-----------------------------------------")
    print(f"CAGR        |  {cagr*100:7.2f}%  |  {spy_cagr*100:7.2f}%")
    print(f"Max DD      |  {mdd*100:7.2f}%  |  {spy_mdd*100:7.2f}%")
    print(f"Sharpe      |  {sharpe:7.2f}   |  {spy_sharpe:7.2f}")
    print("==================================================")

if __name__ == "__main__":
    main()
