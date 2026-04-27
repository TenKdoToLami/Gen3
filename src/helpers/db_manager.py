import sqlite3
import os
import pandas as pd

class MarketDB:
    def __init__(self, db_path="data/market.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    date TEXT PRIMARY KEY,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    vix REAL,
                    yield_curve REAL
                )
            """)

    def get_latest_date(self):
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT MAX(date) FROM market_data").fetchone()
            return res[0] if res[0] else None

    def save_data(self, df):
        if df is None or df.empty:
            return
        
        # Format index to string YYYY-MM-DD
        df_to_save = df.copy()
        df_to_save.index = df_to_save.index.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            df_to_save.to_sql("market_data", conn, if_exists="append", index=True, index_label="date", method="multi")
            # Remove duplicates if any (e.g. if overlap happened during download)
            conn.execute("""
                DELETE FROM market_data 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM market_data GROUP BY date
                )
            """)

    def get_history(self, limit=500):
        """Returns the most recent N days as a DataFrame."""
        with sqlite3.connect(self.db_path) as conn:
            query = f"SELECT * FROM market_data ORDER BY date DESC LIMIT {limit}"
            df = pd.read_sql(query, conn, index_col="date", parse_dates=True)
            return df.sort_index()

    def prune_old_data(self, keep_days=1000):
        """Deletes data older than the N most recent days."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                DELETE FROM market_data 
                WHERE date NOT IN (
                    SELECT date FROM market_data ORDER BY date DESC LIMIT {keep_days}
                )
            """)
            conn.commit()
            print(f"Database pruned to keep last {keep_days} days.")
