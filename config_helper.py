#!/usr/bin/env python3
"""
Configuration Helper for cTrader Trade Copier
This script helps you test and adjust lot size multipliers
"""

from config import LOT_SIZE_MULTIPLIERS, DEFAULT_LOT_MULTIPLIER, GLOBAL_LOT_MULTIPLIER

def calculate_slave_volume(symbol, master_volume_lots):
    """
    Calculate what the slave volume would be for a given master volume
    
    Args:
        symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")
        master_volume_lots: Master volume in standard lots (e.g., 0.02 for 0.02 lots)
    
    Returns:
        tuple: (slave_volume_lots, multiplier_used)
    """
    # Convert to micro lots (API format)
    master_volume_micro = int(master_volume_lots * 100000)
    
    # Determine multiplier
    if GLOBAL_LOT_MULTIPLIER is not None:
        multiplier = GLOBAL_LOT_MULTIPLIER
    else:
        multiplier = LOT_SIZE_MULTIPLIERS.get(symbol, DEFAULT_LOT_MULTIPLIER)
    
    # Calculate slave volume
    slave_volume_micro = int(master_volume_micro * multiplier)
    slave_volume_micro = max(1000, slave_volume_micro)  # Minimum 0.01 lot
    
    # Convert back to standard lots
    slave_volume_lots = slave_volume_micro / 100000
    
    return slave_volume_lots, multiplier

def test_multipliers():
    """Test current multiplier configuration with common scenarios"""
    print("=" * 60)
    print("LOT SIZE MULTIPLIER TEST")
    print("=" * 60)
    
    test_cases = [
        ("EURUSD", 0.10),
        ("EURUSD", 0.02),
        ("XAUUSD", 0.02),
        ("XAUUSD", 0.10),
        ("US30", 0.05),
        ("BTCUSD", 0.01),
    ]
    
    print(f"{'Symbol':<10} {'Master':<10} {'Slave':<10} {'Multiplier':<12} {'Status'}")
    print("-" * 60)
    
    for symbol, master_lots in test_cases:
        slave_lots, multiplier = calculate_slave_volume(symbol, master_lots)
        status = "✓" if slave_lots > 0 else "✗"
        print(f"{symbol:<10} {master_lots:<10.3f} {slave_lots:<10.3f} {multiplier:<12.3f} {status}")
    
    print("\n" + "=" * 60)
    print("CONFIGURATION SUMMARY")
    print("=" * 60)
    
    if GLOBAL_LOT_MULTIPLIER is not None:
        print(f"Global multiplier: {GLOBAL_LOT_MULTIPLIER}")
        print("(This overrides all instrument-specific multipliers)")
    else:
        print("Using instrument-specific multipliers:")
        print(f"Default multiplier: {DEFAULT_LOT_MULTIPLIER}")
        print("\nInstrument-specific multipliers:")
        for symbol, multiplier in sorted(LOT_SIZE_MULTIPLIERS.items()):
            print(f"  {symbol:<10}: {multiplier}")

def recommend_gold_multiplier(master_lots, desired_slave_lots):
    """
    Recommend a multiplier for Gold based on desired outcome
    
    Args:
        master_lots: Master volume in lots (e.g., 0.02)
        desired_slave_lots: Desired slave volume in lots (e.g., 0.01)
    """
    recommended_multiplier = desired_slave_lots / master_lots
    print(f"\nGOLD MULTIPLIER RECOMMENDATION")
    print(f"To get {desired_slave_lots} lots on slave when master trades {master_lots} lots:")
    print(f"Set XAUUSD multiplier to: {recommended_multiplier:.3f}")
    print(f"\nUpdate config.py:")
    print(f'    "XAUUSD": {recommended_multiplier:.3f},')

if __name__ == "__main__":
    print("cTrader Trade Copier - Configuration Helper")
    print()
    
    # Run tests
    test_multipliers()
    
    # Example recommendation for Gold
    print("\n" + "=" * 60)
    recommend_gold_multiplier(0.02, 0.01)  # User's example: 0.02 master → 0.01 slave
    
    print("\n" + "=" * 60)
    print("USAGE INSTRUCTIONS")
    print("=" * 60)
    print("1. Review the test results above")
    print("2. Adjust multipliers in config.py as needed")
    print("3. For Gold: Use the recommended multiplier above")
    print("4. Test with small amounts first")
    print("5. Set GLOBAL_LOT_MULTIPLIER to override all instruments")
    print("6. Run this script again after making changes") 