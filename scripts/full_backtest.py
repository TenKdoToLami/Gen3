import os
import sys
import json
import pandas as pd
import numpy as np

# Ensure src is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.strategies.v3_strategy import V3Strategy

def calculate_metrics(returns):
    # Returns is an array of portfolio values
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
    print("       GEN3 FULL HISTORICAL SIMULATION            ")
    print("       Regime: 1993 - Present                     ")
    print("==================================================")
    
    # 1. Load Master History from tactical_bot cache
    csv_path = "i:/tactical_bot/data/master_history.csv"
    if not os.path.exists(csv_path):
        print(f"Error: Master history not found at {csv_path}")
        return
        
    print(f"Loading master history...")
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    print(f"Loaded {len(df)} trading days.")

    # 2. Load Champion Genome
    with open("config/v3_champion.json", "r") as f:
        genome = json.load(f)
    
    strategy = V3Strategy(genome)
    
    # 3. Simulation Variables
    portfolio_value = 100.0
    spy_value = 100.0
    
    history = []
    
    # Starting allocation
    allocation = {"CASH": 1.0}
    
    print("Simulating day-by-day (No Cheating)...")
    
    # We skip day 0 to have a prev_row for returns
    for i in range(1, len(df)):
        row = df.iloc[i].to_dict()
        prev_row = df.iloc[i-1].to_dict()
        
        # A. Calculate Daily Return of SPY
        spy_change = (row['close'] / prev_row['close']) - 1.0
        
        # B. Apply yesterday's decision to today's portfolio
        if "3xSPY" in allocation:
            portfolio_value *= (1 + spy_change * 3.0)
        
        spy_value *= (1 + spy_change)
        
        # C. Get Today's Indicators and Score (Decision for Tomorrow)
        # This updates internal state using only current 'row'
        allocation = strategy.on_data(row)
        
        # D. Record for metrics
        history.append({
            'date': df.index[i],
            'portfolio': portfolio_value,
            'spy': spy_value,
            'allocation': list(allocation.keys())[0]
        })

    # 4. Results calculation
    results_df = pd.DataFrame(history)
    cagr, mdd, sharpe = calculate_metrics(results_df['portfolio'].values)
    s_cagr, s_mdd, s_sharpe = calculate_metrics(results_df['spy'].values)
    
    print("\nFINAL RESULTS (1993 - Present):")
    print("-" * 50)
    print(f"{'Metric':<12} | {'Gen3 V3':<12} | {'SPY (1x)':<12}")
    print("-" * 50)
    print(f"{'CAGR':<12} | {cagr*100:<11.2f}% | {s_cagr*100:<11.2f}%")
    print(f"{'Max DD':<12} | {mdd*100:<11.2f}% | {s_mdd*100:<11.2f}%")
    print(f"{'Sharpe':<12} | {sharpe:<11.2f} | {s_sharpe:<11.2f}")
    print("-" * 50)
    
    # Optional: Yearly breakdown
    results_df['year'] = results_df['date'].dt.year
    yearly = results_df.groupby('year').apply(lambda x: (x['portfolio'].iloc[-1] / x['portfolio'].iloc[0]) - 1)
    
    print("\nYEARLY PERFORMANCE (Last 5 Years):")
    for year, perf in yearly.tail(5).items():
        print(f"{year}: {perf*100:7.2f}%")
    
    print("==================================================")

if __name__ == "__main__":
    main()
