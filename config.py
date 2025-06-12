# Configuration for cTrader Trade Copier
# Fill in your actual values

from enum import Enum
from dataclasses import dataclass
from typing import Dict
from dotenv import load_dotenv
import os

load_dotenv()

all_client_id = os.getenv("all_client_id")
all_client_secret = os.getenv("all_client_secret")
all_access_token = os.getenv("all_access_token")
master_account_id = int(os.getenv("master_account_id"))
slave_account_id = int(os.getenv("slave_account_id"))

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


# Alternative: You can also set a global multiplier that applies to all instruments
# Set this to None to use the instrument-specific multipliers above
GLOBAL_LOT_MULTIPLIER = float(os.getenv("GLOBAL_LOT_MULTIPLIER"))  # Example: 0.5 for 50% of master volume on all instruments



# Minimum lot size in micro lots. Most brokers allow 0.01 lot (=100 micro-lots for XAUUSD where 1 lot = 100 oz).
# We set 100 so we can place 0.01-lot (1 oz) gold trades while still preventing <0.001-lot orders.
MIN_LOT_SIZE = 100

# Maximum lot size multiplier (safety limit)
# This prevents accidentally large positions due to misconfiguration
MAX_LOT_MULTIPLIER = 2.0  # Never trade more than 2x the master volume



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

