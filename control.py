import os
import sys
import argparse
from src.alpaca_bot import Gen3AlpacaBot

def main():
    parser = argparse.ArgumentParser(description='Gen3 Bot Command Center')
    parser.add_argument('command', type=str, choices=[
        'status',    # Check market open/close
        'sync',      # Update historical data (YF/FRED)
        'signal',    # Calculate today's signal
        'rebalance', # Run the full automated cycle
        'sell',      # Sell non-target positions
        'buy',       # Buy target asset with available cash
        'balance'    # Check account equity and cash
    ], help='Command to execute')
    
    parser.add_argument('--live', action='store_true', help='Execute real trades (disables dry-run)')
    args = parser.parse_args()

    # Dry-run is ENABLED by default unless --live is passed
    bot = Gen3AlpacaBot(dry_run=not args.live)
    
    print(f"\n[Gen3 Control] Executing: {args.command.upper()} (Live: {args.live})")
    print("-" * 40)
    
    if args.command == 'status':
        bot.check_market_open()
        
    elif args.command == 'sync':
        bot.sync_data()
        
    elif args.command == 'signal':
        df = bot.sync_data()
        target, asset_type = bot.get_signal(df)
        print(f"\nVERDICT: {asset_type} ({target})")
        
    elif args.command == 'rebalance':
        bot.run_full_cycle()
        
    elif args.command == 'sell':
        df = bot.sync_data()
        target, _ = bot.get_signal(df)
        bot.sell_non_target(target)
        
    elif args.command == 'balance':
        bot.get_buying_power()
        
    elif args.command == 'buy':
        df = bot.sync_data()
        target, _ = bot.get_signal(df)
        cash = bot.get_buying_power()
        bot.buy_target(target, cash)

    print("-" * 40)

if __name__ == "__main__":
    main()
