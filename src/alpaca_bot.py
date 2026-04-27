import os
import sys
import json
import logging
import time
import pandas as pd
from dotenv import load_dotenv

# Modern Alpaca SDK
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

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
        # Support both naming conventions (ALPACA_KEY and ALPACA_API_KEY)
        self.api_key = os.getenv("ALPACA_KEY") or os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET") or os.getenv("ALPACA_SECRET_KEY")
        
        if not self.api_key or not self.secret_key:
            raise ValueError("CRITICAL: Alpaca API Keys not found in .env file! Check config/.env")

        # Trading Client
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        # Data Client
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)

    def check_market_open(self):
        clock = self.trading_client.get_clock()
        status = "OPEN" if clock.is_open else "CLOSED"
        self.logger.info(f"Market is {status}. Next Open: {clock.next_open} | Next Close: {clock.next_close}")
        return clock.is_open

    def sync_data(self):
        self.logger.info("Syncing historical data from YFinance and FRED...")
        df = update_market_data()
        last_date = pd.to_datetime(df.index[-1]).date()
        self.logger.info(f"Sync complete. Latest date in DB: {last_date}")
        return df

    def get_signal(self, df):
        ticker = self.settings['signal_ticker']
        # Fetch latest quote
        quote_req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
        quote = self.data_client.get_stock_latest_quote(quote_req)
        curr_price = quote[ticker].ask_price
        
        latest_row = df.iloc[-1].to_dict()
        today_data = {
            'close': curr_price, 'high': curr_price, 'low': curr_price,
            'vix': latest_row['vix'], 'yield_curve': latest_row['yield_curve']
        }
        
        strategy = V3Strategy(self.genome)
        for _, row in df.tail(1000).iterrows():
            strategy.on_data(row.to_dict())
            
        allocation = strategy.on_data(today_data)
        asset_type = list(allocation.keys())[0]
        target_symbol = self.settings['symbols'][asset_type]
        
        self.logger.info(f"Signal Generated: {asset_type} ({target_symbol}) @ ${curr_price:.2f}")
        return target_symbol, asset_type

    def sell_non_target(self, target_symbol):
        positions = self.trading_client.get_all_positions()
        valid_symbols = self.settings['symbols'].values()
        
        for pos in positions:
            if pos.symbol != target_symbol and pos.symbol in valid_symbols:
                self.logger.info(f"Selling position in {pos.symbol} (Qty: {pos.qty})")
                if not self.dry_run:
                    self.trading_client.close_position(pos.symbol)
                    time.sleep(5)
                else:
                    self.logger.info(f"[DRY RUN] Would sell {pos.symbol}")

    def get_buying_power(self):
        account = self.trading_client.get_account()
        cash = float(account.cash)
        self.logger.info(f"Available Cash: ${cash:.2f} | Total Equity: ${account.equity}")
        return cash

    def buy_target(self, target_symbol, cash):
        # Fetch latest price
        quote_req = StockLatestQuoteRequest(symbol_or_symbols=target_symbol)
        quote = self.data_client.get_stock_latest_quote(quote_req)
        price = quote[target_symbol].ask_price
        
        qty = (cash * 0.998) / price
        order_value = qty * price
        
        if order_value < self.settings.get('min_order_value', 20.0):
            self.logger.info(f"Order value ${order_value:.2f} below minimum. Skipping.")
            return

        self.logger.info(f"Buying {qty:.4f} shares of {target_symbol} @ ${price:.2f}")
        if not self.dry_run:
            order_data = MarketOrderRequest(
                symbol=target_symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            self.trading_client.submit_order(order_data)
        else:
            self.logger.info(f"[DRY RUN] Would submit order for {qty:.4f} shares")

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
