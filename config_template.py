# Configuration Template for cTrader Trade Copier
# Copy this file to config.py and fill in your actual values

from trade_copier import AccountConfig, ConnectionType

# Master Account Configuration (the account to copy FROM)
MASTER_CONFIG = AccountConfig(
    client_id="YOUR_MASTER_CLIENT_ID",           # Get from cTrader Automate API settings
    client_secret="YOUR_MASTER_CLIENT_SECRET",   # Get from cTrader Automate API settings
    access_token="YOUR_MASTER_ACCESS_TOKEN",     # Get from cTrader OAuth flow
    account_id=12345678,                         # Your master account ID (number)
    connection_type=ConnectionType.DEMO,         # DEMO or LIVE
    host="demo.ctraderapi.com",                  # demo.ctraderapi.com for demo, live.ctraderapi.com for live
    port=5035
)

# Slave Account Configuration (the account to copy TO)
SLAVE_CONFIG = AccountConfig(
    client_id="YOUR_SLAVE_CLIENT_ID",            # Get from cTrader Automate API settings
    client_secret="YOUR_SLAVE_CLIENT_SECRET",    # Get from cTrader Automate API settings
    access_token="YOUR_SLAVE_ACCESS_TOKEN",      # Get from cTrader OAuth flow
    account_id=87654321,                         # Your slave account ID (number)
    connection_type=ConnectionType.DEMO,         # DEMO or LIVE
    host="demo.ctraderapi.com",                  # demo.ctraderapi.com for demo, live.ctraderapi.com for live
    port=5035
)

# Risk Management Settings
LOT_PERCENTAGE = 0.02  # 2% of balance risk per trade (adjust as needed)

# How to get your credentials:
# 1. Go to cTrader Automate (https://ctrader.com/automate)
# 2. Create a new app in the API section
# 3. Get your Client ID and Client Secret
# 4. Use OAuth2 flow to get access tokens for both accounts
# 5. Find your account IDs in cTrader platform 