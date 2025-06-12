#!/usr/bin/env python3
"""
cTrader to cTrader Trade Copier - Run Script
============================================

This script runs the trade copier with your configured settings.

Before running:
1. Copy config_template.py to config.py
2. Fill in your actual cTrader account credentials in config.py
3. Install dependencies: pip install -r requirements.txt
4. Run this script: python run_copier.py
"""

import asyncio
import sys

try:
    from config import MASTER_CONFIG, SLAVE_CONFIG, LOT_PERCENTAGE
except ImportError:
    print("ERROR: config.py not found!")
    print("Please copy config_template.py to config.py and fill in your credentials.")
    sys.exit(1)

from trade_copier import TradeCopier, logger

async def main():
    """Main function to run the trade copier"""
    
    print("cTrader to cTrader Trade Copier")
    print("=" * 50)
    print(f"Master Account: {MASTER_CONFIG.account_id} ({MASTER_CONFIG.connection_type.value})")
    print(f"Slave Account:  {SLAVE_CONFIG.account_id} ({SLAVE_CONFIG.connection_type.value})")
    print(f"Risk per trade: {LOT_PERCENTAGE * 100}% of slave account balance")
    print("=" * 50)
    print("\nStarting trade copier... Press Ctrl+C to stop.")
    print()
    
    # Validate configurations
    if MASTER_CONFIG.client_id.startswith("YOUR_"):
        print("ERROR: Please configure your master account credentials in config.py")
        return
    
    if SLAVE_CONFIG.client_id.startswith("YOUR_"):
        print("ERROR: Please configure your slave account credentials in config.py")
        return
    
    # Create and start trade copier
    copier = TradeCopier(MASTER_CONFIG, SLAVE_CONFIG, lot_percentage=LOT_PERCENTAGE)
    
    try:
        await copier.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal (Ctrl+C)")
        print("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")
    finally:
        await copier.stop()
        print("Trade copier stopped.")

if __name__ == "__main__":
    # Check if dependencies are installed
    try:
        import websockets
    except ImportError:
        print("ERROR: websockets not installed.")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Run the copier
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0) 