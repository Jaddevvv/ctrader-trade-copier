#!/usr/bin/env python3

"""
Broker Calibration Helper for cTrader Trade Copier

This script helps you determine the correct contract sizes for your brokers
to ensure risk equivalence between master and slave accounts.

Usage:
1. Run this script
2. Enter the P&L values you observe for the same lot size on both brokers
3. The script will calculate the correct contract sizes for config.py
"""

def calculate_contract_sizes():
    """Calculate contract sizes based on observed P&L differences"""
    print("=" * 60)
    print("BROKER CALIBRATION HELPER")
    print("=" * 60)
    print()
    print("This tool helps you configure risk-equivalent lot sizes")
    print("between your master and slave brokers.")
    print()
    
    # Get symbol information
    symbol = input("Enter the symbol (e.g., XAUUSD): ").strip().upper()
    if not symbol:
        symbol = "XAUUSD"
    
    print(f"\nConfiguring for symbol: {symbol}")
    print()
    
    # Get test lot size
    test_lot = input("Enter the test lot size you used (e.g., 0.01): ").strip()
    try:
        test_lot_float = float(test_lot)
    except:
        test_lot_float = 0.01
        print(f"Using default: {test_lot_float}")
    
    print(f"Test lot size: {test_lot_float}")
    print()
    
    # Get price movement
    price_move = input("Enter the price movement in $ (e.g., 1.0 for $1 move): ").strip()
    try:
        price_move_float = float(price_move)
    except:
        price_move_float = 1.0
        print(f"Using default: ${price_move_float}")
    
    print(f"Price movement: ${price_move_float}")
    print()
    
    # Get P&L for master broker
    print("MASTER BROKER:")
    master_pnl = input(f"Enter P&L change for {test_lot_float} lot with ${price_move_float} move: $").strip()
    try:
        master_pnl_float = float(master_pnl)
    except:
        print("Invalid input. Please enter a number.")
        return
    
    print(f"Master P&L: ${master_pnl_float}")
    print()
    
    # Get P&L for slave broker
    print("SLAVE BROKER:")
    slave_pnl = input(f"Enter P&L change for {test_lot_float} lot with ${price_move_float} move: $").strip()
    try:
        slave_pnl_float = float(slave_pnl)
    except:
        print("Invalid input. Please enter a number.")
        return
    
    print(f"Slave P&L: ${slave_pnl_float}")
    print()
    
    # Calculate contract sizes
    # Contract size = P&L per lot per unit price move
    master_contract_per_lot = master_pnl_float / (test_lot_float * price_move_float)
    slave_contract_per_lot = slave_pnl_float / (test_lot_float * price_move_float)
    
    # Scale to standard 1.0 lot
    master_contract_size = master_contract_per_lot
    slave_contract_size = slave_contract_per_lot
    
    # Calculate risk multiplier
    risk_multiplier = master_contract_size / slave_contract_size
    
    print("=" * 60)
    print("CALCULATION RESULTS")
    print("=" * 60)
    print()
    print(f"Master contract size: ${master_contract_size:.2f} per 1.0 lot per ${price_move_float} move")
    print(f"Slave contract size:  ${slave_contract_size:.2f} per 1.0 lot per ${price_move_float} move")
    print()
    print(f"Risk multiplier: {risk_multiplier:.4f}")
    print()
    
    if risk_multiplier > 1:
        print(f"⚠️  Slave broker has SMALLER contract size")
        print(f"   To match master risk, slave should trade {risk_multiplier:.2f}x the volume")
    elif risk_multiplier < 1:
        print(f"⚠️  Slave broker has LARGER contract size")
        print(f"   To match master risk, slave should trade {risk_multiplier:.2f}x the volume")
    else:
        print(f"✅ Both brokers have the same contract size")
    
    print()
    print("=" * 60)
    print("CONFIG.PY CONFIGURATION")
    print("=" * 60)
    print()
    print("Add this to your RISK_BASED_MULTIPLIERS in config.py:")
    print()
    print(f'    "{symbol}": {{')
    print(f'        "target_risk_ratio": 1.0,')
    print(f'        "master_contract_size": {master_contract_size:.0f},')
    print(f'        "slave_contract_size": {slave_contract_size:.0f},')
    print(f'    }},')
    print()
    
    # Example calculation
    example_master_lot = 0.02
    example_slave_lot = example_master_lot * risk_multiplier
    
    print("=" * 60)
    print("EXAMPLE")
    print("=" * 60)
    print()
    print(f"If master trades {example_master_lot:.3f} lot:")
    print(f"Slave will trade {example_slave_lot:.3f} lot")
    print()
    print(f"Expected P&L for ${price_move_float} move:")
    print(f"Master: ${example_master_lot * master_contract_size * price_move_float:.2f}")
    print(f"Slave:  ${example_slave_lot * slave_contract_size * price_move_float:.2f}")
    print()
    
    if abs((example_master_lot * master_contract_size) - (example_slave_lot * slave_contract_size)) < 0.01:
        print("✅ Risk equivalence achieved!")
    else:
        print("⚠️  There may be a calculation error. Please double-check your inputs.")

def quick_test():
    """Quick test with reported values"""
    print("=" * 60)
    print("QUICK TEST - Based on your reported issue")
    print("=" * 60)
    print()
    print("Your reported scenario:")
    print("- Master: 0.02 lot, made $1.68")
    print("- Slave:  0.10 lot, made $7.90")
    print()
    
    # Calculate implied contract sizes
    master_pnl_per_lot = 1.68 / 0.02  # $84 per lot
    slave_pnl_per_lot = 7.90 / 0.10   # $79 per lot
    
    print(f"Implied contract sizes:")
    print(f"Master: ${master_pnl_per_lot:.0f} per lot")
    print(f"Slave:  ${slave_pnl_per_lot:.0f} per lot")
    print()
    
    # Calculate what slave should have traded
    risk_multiplier = master_pnl_per_lot / slave_pnl_per_lot
    correct_slave_lot = 0.02 * risk_multiplier
    
    print(f"Risk multiplier: {risk_multiplier:.4f}")
    print(f"Slave should have traded: {correct_slave_lot:.3f} lot (instead of 0.10)")
    print()
    
    print("Suggested config.py setting:")
    print()
    print('    "XAUUSD": {')
    print('        "target_risk_ratio": 1.0,')
    print(f'        "master_contract_size": {master_pnl_per_lot:.0f},')
    print(f'        "slave_contract_size": {slave_pnl_per_lot:.0f},')
    print('    },')

def main():
    """Main function"""
    print("Choose an option:")
    print("1. Full calibration (recommended)")
    print("2. Quick test based on your reported issue")
    print()
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        quick_test()
    else:
        calculate_contract_sizes()
    
    print()
    print("=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print()
    print("1. Update your config.py with the calculated values")
    print("2. Make sure USE_RISK_BASED_SIZING = True in config.py")
    print("3. Test with small amounts first")
    print("4. Monitor the first few trades to verify correct sizing")
    print()

if __name__ == "__main__":
    quick_test() 