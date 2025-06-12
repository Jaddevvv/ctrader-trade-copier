# Configuration for cTrader Trade Copier
# Fill in your actual values

from enum import Enum
from dataclasses import dataclass
from typing import Dict

class ConnectionType(Enum):
    DEMO = "demo"
    LIVE = "live"

@dataclass
class AccountConfig:
    """Configuration for a cTrader account"""
    client_id: str
    client_secret: str
    access_token: str
    account_id: int
    connection_type: ConnectionType
    host: str = "demo.ctraderapi.com"  # Default demo host
    port: int = 5035

# Risk-Based Lot Size Configuration
# This system calculates lot sizes based on dollar risk equivalence between brokers
# Format: "SYMBOL": {"target_risk_ratio": ratio, "pip_value_master": value, "pip_value_slave": value}

# IMPORTANT: Set USE_DYNAMIC_PIP_SIZING = True to enable automatic pip value calculation
USE_DYNAMIC_PIP_SIZING = True
USE_RISK_BASED_SIZING = False  # Deprecated - use USE_DYNAMIC_PIP_SIZING instead

# Risk-based configuration for different brokers
# This accounts for different contract sizes and pip values
RISK_BASED_MULTIPLIERS = {
    # Gold (XAUUSD) - Example configuration
    # If master broker: 0.01 lot = $1 per $1 move
    # If slave broker: 0.01 lot = $5 per $1 move  
    # Then to get same risk: slave should trade 0.01 * (1/5) = 0.002 lot
    "XAUUSD": {
        "target_risk_ratio": 1.0,  # 1.0 = same dollar risk
        "master_contract_size": 84,  # Master broker: $84 per 1.0 lot (calculated from your data)
        "slave_contract_size": 79,   # Slave broker: $79 per 1.0 lot (calculated from your data)
        # Based on your reported P&L: Master 0.02 lot = $1.68, Slave 0.10 lot = $7.90
    },
    
    "GOLD": {
        "target_risk_ratio": 1.0,
        "master_contract_size": 84,  # Same as XAUUSD
        "slave_contract_size": 79,   # Same as XAUUSD
    },
    
    # Forex pairs - usually standard across brokers
    "EURUSD": {
        "target_risk_ratio": 1.0,
        "master_contract_size": 100000,  # Standard lot size
        "slave_contract_size": 100000,   # Standard lot size
    },
    
    "GBPUSD": {
        "target_risk_ratio": 1.0,
        "master_contract_size": 100000,
        "slave_contract_size": 100000,
    },
    
    # Add more instruments as needed
}

# Fallback: Simple Lot Size Multiplier Configuration (used when USE_RISK_BASED_SIZING = False)
# This allows you to set different multipliers for different instruments
# Format: "SYMBOL": multiplier_value
# Example: If master trades 0.10 lot EURUSD and multiplier is 0.5, slave will trade 0.05 lot
LOT_SIZE_MULTIPLIERS = {
    # Forex Pairs - Standard multipliers
    "EURUSD": 0.5,
    "GBPUSD": 0.5,
    "USDJPY": 0.5,
    "USDCHF": 0.5,
    "AUDUSD": 0.5,
    "USDCAD": 0.5,
    "NZDUSD": 0.5,
    "EURGBP": 0.5,
    "EURJPY": 0.5,
    "GBPJPY": 0.5,
    
    # Gold and Precious Metals - Adjust based on your broker's contract sizes
    "XAUUSD": 0.25,  # Reduced from 0.5 based on your feedback
    "GOLD": 0.25,    # Alternative Gold symbol
    "XAGUSD": 0.5,   # Silver
    "SILVER": 0.5,   # Alternative Silver symbol
    
    # Indices - Usually smaller multipliers due to higher contract values
    "US30": 0.1,    # Dow Jones
    "SPX500": 0.1,  # S&P 500
    "NAS100": 0.1,  # Nasdaq
    "GER30": 0.1,   # DAX
    "UK100": 0.1,   # FTSE
    "JPN225": 0.1,  # Nikkei
    
    # Commodities
    "CRUDE": 0.5,   # WTI Oil
    "BRENT": 0.5,   # Brent Oil
    "NGAS": 0.3,    # Natural Gas
    
    # Cryptocurrencies - Very volatile, smaller multipliers recommended
    "BTCUSD": 0.1,
    "ETHUSD": 0.2,
    "LTCUSD": 0.3,
    "XRPUSD": 0.5,
}

# Default multiplier for instruments not listed above
DEFAULT_LOT_MULTIPLIER = 0.5

# Alternative: You can also set a global multiplier that applies to all instruments
# Set this to None to use the instrument-specific multipliers above
GLOBAL_LOT_MULTIPLIER = None  # Example: 0.5 for 50% of master volume on all instruments

# Minimum lot size in micro lots. Most brokers allow 0.01 lot (=100 micro-lots for XAUUSD where 1 lot = 100 oz).
# We set 100 so we can place 0.01-lot (1 oz) gold trades while still preventing <0.001-lot orders.
MIN_LOT_SIZE = 100

# Maximum lot size multiplier (safety limit)
# This prevents accidentally large positions due to misconfiguration
MAX_LOT_MULTIPLIER = 2.0  # Never trade more than 2x the master volume

# Your credentials


# Master Account Configuration (the account to copy FROM)
MASTER_CONFIG = AccountConfig(
    client_id=all_client_id,           # Get from cTrader Automate API settings
    client_secret=all_client_secret,   # Get from cTrader Automate API settings
    access_token=all_access_token,     # Get from cTrader OAuth flow
    account_id=master_account_id,      # Your master account ID (number)
    connection_type=ConnectionType.DEMO,         # DEMO or LIVE
    host="demo.ctraderapi.com",                  # demo.ctraderapi.com for demo, live.ctraderapi.com for live
    port=5035
)

# Slave Account Configuration (the account to copy TO)
SLAVE_CONFIG = AccountConfig(
    client_id=all_client_id,            # Get from cTrader Automate API settings
    client_secret=all_client_secret,    # Get from cTrader Automate API settings
    access_token=all_access_token,      # Get from cTrader OAuth flow
    account_id=slave_account_id,        # Your slave account ID (number)
    connection_type=ConnectionType.DEMO,         # DEMO or LIVE
    host="demo.ctraderapi.com",                  # demo.ctraderapi.com for demo, live.ctraderapi.com for live
    port=5035
)

# Legacy setting (kept for backward compatibility)
LOT_PERCENTAGE = 0.5  # Deprecated - use LOT_SIZE_MULTIPLIERS instead

# How to get your credentials:
# 1. Go to cTrader Automate (https://ctrader.com/automate)
# 2. Create a new app in the API section
# 3. Get your Client ID and Client Secret
# 4. Use OAuth2 flow to get access tokens for both accounts
# 5. Find your account IDs in cTrader platform

# How to configure risk-based lot sizing:
# 1. Set USE_RISK_BASED_SIZING = True
# 2. For each instrument, determine the contract size for both brokers
# 3. Example: If master 0.01 lot XAUUSD = $1 per $1 move, set master_contract_size = 100
# 4. If slave 0.01 lot XAUUSD = $5 per $1 move, set slave_contract_size = 500
# 5. The system will automatically calculate: slave_lot = master_lot * (100/500) = master_lot * 0.2
# 6. Test with small amounts first and monitor results

# How to find your broker's contract sizes:
# 1. Open a small position (e.g., 0.01 lot) on both accounts
# 2. Note the P&L change for a $1 price move
# 3. That's your contract size per 0.01 lot
# 4. Scale accordingly (e.g., if 0.01 lot = $1 per $1 move, then 1.0 lot = $100 per $1 move)

# =====================================
# Dynamic Pip Sizing Global Settings
# =====================================

# When USE_DYNAMIC_PIP_SIZING = True, the copier calculates a risk-neutral volume so that
# the pip value (monetary value of one pip) on the slave equals the pip value on the master.
# To intentionally scale the risk up or down you can apply a global ratio here.
# 1.0  -> equal risk (default behaviour)
# 0.5  -> half the risk on slave (volume divided by two)
# 2.0  -> double the risk on slave (volume multiplied by two)
DYNAMIC_PIP_VOLUME_RATIO = 0.5 