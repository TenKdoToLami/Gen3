import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from src.helpers.db_manager import MarketDB

def update_market_data(force_full=False):
    """
    Syncs local SQL database with the latest data from YFinance and FRED.
    Only downloads missing days unless force_full is True.
    """
    db = MarketDB()
    latest_date_str = db.get_latest_date()
    
    if force_full or not latest_date_str:
        # Initial seeding: last 5 years
        start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
        print(f"Initializing database from {start_date}...")
    else:
        # Incremental update
        start_date = latest_date_str
        print(f"Syncing incremental data since {start_date}...")

    # 1. SPY + VIX
    spy = yf.download("SPY", start=start_date, progress=False)
    if spy.empty:
        return db.get_history()
        
    if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
    
    vix = yf.download("^VIX", start=start_date, progress=False)
    if isinstance(vix.columns, pd.MultiIndex): vix.columns = vix.columns.get_level_values(0)
    
    # 2. Yield Curve (FRED)
    try:
        fred_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
        fred = pd.read_csv(fred_url, index_col="DATE", parse_dates=True, na_values=".")
        fred = fred[fred.index >= pd.to_datetime(start_date)]
    except:
        fred = pd.DataFrame(index=spy.index)
        fred['T10Y2Y'] = 0.0

    # 3. Merge and Clean
    df = pd.DataFrame({
        "open": spy["Open"],
        "high": spy["High"],
        "low": spy["Low"],
        "close": spy["Close"],
        "volume": spy["Volume"],
        "vix": vix["Close"],
        "yield_curve": fred["T10Y2Y"]
    })
    
    df['vix'] = df['vix'].ffill().bfill()
    df['yield_curve'] = df['yield_curve'].ffill().bfill()
    df = df.dropna(subset=['close'])

    # 4. Save and Prune
    if latest_date_str:
        df = df[df.index > pd.to_datetime(latest_date_str)]
        
    db.save_data(df)
    db.prune_old_data(keep_days=1000)
    
    return db.get_history(limit=1000)
