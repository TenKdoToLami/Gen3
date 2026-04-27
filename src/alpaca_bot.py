import os
import sys
import json
import logging
import time
from datetime import datetime
import pandas as pd
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Ensure src is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.helpers.data_provider import update_market_data
from src.strategies.v3_strategy import V3Strategy

class Gen3AlpacaBot:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.load_configs()
        self.setup_logging()
        self.init_alpaca()
        
    def load_configs(self):
        env_path = os.path.join("config", ".env")
        load_dotenv(env_path)
        
        dna_path = os.getenv("STRATEGY_DNA", "config/strategy.json")
        if not os.path.isabs(dna_path):
            dna_path = os.path.join(os.getcwd(), dna_path)
            
        with open(dna_path, "r") as f:
            self.genome = json.load(f)
        
        self.settings = {
            'symbols': {
                "3xSPY": os.getenv("TICKER_3X", "SPXL"),
                "CASH": os.getenv("TICKER_CASH", "SGOV")
            },
            'signal_ticker': os.getenv("TICKER_SIGNAL", "VOO"),
            'min_rebalance_threshold': float(os.getenv("MIN_REMAINING_BALANCE", 20.0)),
            'min_order_value': float(os.getenv("MIN_ORDER_VALUE", 20.0))
        }
            
    def setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler("logs/bot_execution.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("Gen3Bot")

    def init_alpaca(self):
        self.api_key = os.getenv("ALPACA_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')

    # --- STEP 1: Market Status ---
    def check_market_open(self):
        clock = self.api.get_clock()
        status = "OPEN" if clock.is_open else "CLOSED"
        self.logger.info(f"Market is {status}. Next Open: {clock.next_open} | Next Close: {clock.next_close}")
        return clock.is_open

    # --- STEP 2: Data Pull (YF + FED) ---
    def sync_data(self):
        self.logger.info("Syncing historical data from YFinance and FRED...")
        df = update_market_data()
        last_date = pd.to_datetime(df.index[-1]).date()
        self.logger.info(f"Sync complete. Latest date in DB: {last_date}")
        return df

    # --- STEP 3: Signal Calculation ---
    def get_signal(self, df):
        # Fetch current signal price (VOO/SPY)
        ticker = self.settings['signal_ticker']
        last_quote = self.api.get_latest_quote(ticker)
        curr_price = last_quote.ap
        
        # Prepare today's data row
        latest_row = df.iloc[-1].to_dict()
        today_data = {
            'close': curr_price, 'high': curr_price, 'low': curr_price,
            'vix': latest_row['vix'], 'yield_curve': latest_row['yield_curve']
        }
        
        # Warmup and Decide (using full history for EMA stability)
        strategy = V3Strategy(self.genome)
        for _, row in df.tail(1000).iterrows():
            strategy.on_data(row.to_dict())
            
        allocation = strategy.on_data(today_data)
        asset_type = list(allocation.keys())[0] # "3xSPY" or "CASH"
        target_symbol = self.settings['symbols'][asset_type]
        
        self.logger.info(f"Signal Generated: {asset_type} ({target_symbol}) @ ${curr_price:.2f}")
        return target_symbol, asset_type

    # --- STEP 4: Sell Position ---
    def sell_non_target(self, target_symbol):
        positions = self.api.list_positions()
        for pos in positions:
            if pos.symbol != target_symbol and pos.symbol in self.settings['symbols'].values():
                self.logger.info(f"Selling position in {pos.symbol} (Qty: {pos.qty})")
                if not self.dry_run:
                    self.api.close_position(pos.symbol)
                    time.sleep(5) # Wait for fill
                else:
                    self.logger.info(f"[DRY RUN] Would sell {pos.symbol}")

    # --- STEP 5: Check Balance ---
    def get_buying_power(self):
        account = self.api.get_account()
        cash = float(account.cash)
        self.logger.info(f"Available Cash: ${cash:.2f} | Total Equity: ${account.equity}")
        return cash

    # --- STEP 6: Buy Position ---
    def buy_target(self, target_symbol, cash):
        # Check if we already have it
        try:
            pos = self.api.get_position(target_symbol)
            curr_qty = float(pos.qty)
        except:
            curr_qty = 0
            
        threshold = self.settings['min_rebalance_threshold']
        if cash < threshold:
            self.logger.info(f"Remaining cash ${cash:.2f} is below threshold ${threshold}. No trade needed.")
            return

        last_quote = self.api.get_latest_quote(target_symbol)
        price = last_quote.ap
        
        # Calculate maximum possible qty (using 99.8% of cash to allow for minor price movement)
        qty = (cash * 0.998) / price
        order_value = qty * price
        
        if order_value < self.settings.get('min_order_value', 20.0):
            self.logger.info(f"Calculated buy order value ${order_value:.2f} is below MIN_ORDER_VALUE. Skipping.")
            return

        self.logger.info(f"Buying {qty:.4f} shares of {target_symbol} @ ${price:.2f} (Value: ${order_value:.2f})")
        if not self.dry_run:
            self.api.submit_order(
                symbol=target_symbol, qty=qty, side='buy',
                type='market', time_in_force='day'
            )
        else:
            self.logger.info(f"[DRY RUN] Would submit fractional buy order for {qty:.4f} shares")

    def run_full_cycle(self):
        self.logger.info("--- Starting Daily Cycle ---")
        if not self.check_market_open() and not self.dry_run:
            self.logger.warning("Market is closed. Skipping execution.")
            return

        df = self.sync_data()
        target_symbol, _ = self.get_signal(df)
        
        self.sell_non_target(target_symbol)
        cash = self.get_buying_power()
        self.buy_target(target_symbol, cash)
        
        self.logger.info("--- Cycle Completed ---")

if __name__ == "__main__":
    bot = Gen3AlpacaBot(dry_run="--dry-run" in sys.argv)
    bot.run_full_cycle()
