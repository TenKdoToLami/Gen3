import os
import sys
import json
import logging
import time
from datetime import datetime
import alpaca_trade_api as tradeapi

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
        # 1. Load Genome
        with open("config/v3_champion.json", "r") as f:
            self.genome = json.load(f)
        
        # 2. Load Bot Settings
        with open("config/bot_settings.json", "r") as f:
            self.settings = json.load(f)
            
    def setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(self.settings.get("log_file", "logs/bot_execution.log")),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("Gen3Bot")

    def init_alpaca(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        if not self.api_key or not self.secret_key:
            self.logger.error("Alpaca credentials missing in environment variables!")
            sys.exit(1)
            
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')

    def get_market_data(self):
        self.logger.info("Syncing market data...")
        df = update_market_data()
        
        # Fetch current SPY price from Alpaca
        spy_last_quote = self.api.get_latest_quote("SPY")
        current_spy_price = spy_last_quote.ap # Ask price
        
        latest_data = df.iloc[-1].to_dict()
        # Create a "today" entry with current SPY price and latest VIX/YC
        today_data = {
            'close': current_spy_price,
            'high': current_spy_price, # Simplified
            'low': current_spy_price,  # Simplified
            'vix': latest_data['vix'],
            'yield_curve': latest_data['yield_curve']
        }
        
        # History for warmup
        history = []
        for _, row in df.tail(250).iterrows():
            history.append(row.to_dict())
            
        return history, today_data

    def calculate_signal(self, history, today_data):
        self.logger.info("Calculating strategy signal...")
        strategy = V3Strategy(self.genome)
        
        # Warmup
        for data in history:
            strategy.on_data(data)
            
        # Get final signal
        allocation = strategy.on_data(today_data)
        target_asset_type = list(allocation.keys())[0] # "3xSPY" or "CASH"
        target_symbol = self.settings['symbols'][target_asset_type]
        
        # Log indicator scores (this requires a small hack or manual calculation since V3Strategy doesn't expose them easily)
        # For now, we'll log the final verdict and the inputs
        self.logger.info(f"Inputs: SPY=${today_data['close']:.2f}, VIX={today_data['vix']:.2f}, YC={today_data['yield_curve']:.3f}")
        self.logger.info(f"Target Allocation: {target_asset_type} ({target_symbol})")
        
        return target_symbol, target_asset_type

    def execute_trade(self, target_symbol, target_asset_type):
        self.logger.info("Checking current positions...")
        account = self.api.get_account()
        positions = self.api.list_positions()
        
        current_symbol = None
        current_qty = 0
        
        for pos in positions:
            if pos.symbol in self.settings['symbols'].values():
                current_symbol = pos.symbol
                current_qty = float(pos.qty)
                break
        
        self.logger.info(f"Current Position: {current_symbol} (Qty: {current_qty})")
        self.logger.info(f"Account Balance: ${account.equity}")
        
        if current_symbol != target_symbol:
            self.logger.info(f"Rebalancing: {current_symbol} -> {target_symbol}")
            
            # 1. Sell current if exists
            if current_symbol:
                if not self.dry_run:
                    self.api.close_position(current_symbol)
                    self.logger.info(f"Closed position in {current_symbol}")
                    # Wait for settlement/order fill
                    time.sleep(5)
                else:
                    self.logger.info(f"[DRY RUN] Would close position in {current_symbol}")

            # Log balance after sell
            account = self.api.get_account()
            self.logger.info(f"Balance after sell: ${account.cash}")

            # 2. Buy target
            if not self.dry_run:
                cash = float(account.cash)
                # Reserve 1% for slippage/fees if necessary, though paper trading is free
                buy_power = cash * 0.99 
                last_price = self.api.get_latest_quote(target_symbol).ap
                qty = int(buy_power / last_price)
                
                if qty > 0:
                    self.api.submit_order(
                        symbol=target_symbol,
                        qty=qty,
                        side='buy',
                        type='market',
                        time_in_force='day'
                    )
                    self.logger.info(f"Bought {qty} shares of {target_symbol}")
                else:
                    self.logger.warning("Insufficient funds to buy even 1 share.")
            else:
                self.logger.info(f"[DRY RUN] Would buy {target_symbol} with available cash")
                
        else:
            # Same symbol - check for unused balance
            cash = float(account.cash)
            threshold = self.settings.get("min_rebalance_threshold", 100.0)
            
            self.logger.info(f"Already in target asset. Current cash: ${cash:.2f}")
            
            if cash > threshold:
                self.logger.info(f"Cash exceeds threshold (${threshold}). Buying more {target_symbol}...")
                if not self.dry_run:
                    last_price = self.api.get_latest_quote(target_symbol).ap
                    qty = int((cash * 0.99) / last_price)
                    if qty > 0:
                        self.api.submit_order(
                            symbol=target_symbol,
                            qty=qty,
                            side='buy',
                            type='market',
                            time_in_force='day'
                        )
                        self.logger.info(f"Added {qty} shares to {target_symbol}")
                else:
                    self.logger.info(f"[DRY RUN] Would add shares to {target_symbol}")
            else:
                self.logger.info("Unused balance below threshold. No additional action taken.")

    def run(self):
        try:
            history, today_data = self.get_market_data()
            target_symbol, target_asset_type = self.calculate_signal(history, today_data)
            self.execute_trade(target_symbol, target_asset_type)
            self.logger.info("Daily routine completed successfully.")
        except Exception as e:
            self.logger.exception(f"Error during bot execution: {str(e)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Gen3 Alpaca Trading Bot')
    parser.add_argument('--dry-run', action='store_true', help='Calculate signal but do not execute trades')
    args = parser.parse_args()
    
    bot = Gen3AlpacaBot(dry_run=args.dry_run)
    bot.run()
