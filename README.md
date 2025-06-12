# cTrader to cTrader Trade Copier

A Python-based trade copier that copies trades from one cTrader account to another, running on the same computer. The slave account automatically adjusts lot sizes based on a percentage of its balance.

## Features

- ✅ Real-time trade copying between cTrader accounts
- ✅ Automatic lot size adjustment based on slave account balance percentage
- ✅ Support for both Demo and Live accounts
- ✅ WebSocket connection for real-time updates
- ✅ Comprehensive logging
- ✅ Error handling and recovery
- ✅ Simple configuration setup

## Requirements

- Python 3.7+
- cTrader accounts with API access
- Internet connection

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get cTrader API Credentials

1. Go to [cTrader Automate](https://ctrader.com/automate)
2. Create a new application in the API section
3. Note down your `Client ID` and `Client Secret`
4. Complete the OAuth2 flow to get `Access Tokens` for both accounts
5. Find your account IDs in the cTrader platform

### 3. Configure Your Accounts

1. Copy the configuration template:
   ```bash
   cp config_template.py config.py
   ```

2. Edit `config.py` with your actual credentials:
   ```python
   MASTER_CONFIG = AccountConfig(
       client_id="your_actual_client_id",
       client_secret="your_actual_client_secret", 
       access_token="your_actual_access_token",
       account_id=1234567890,  # Your actual account ID
       connection_type=ConnectionType.DEMO,  # or LIVE
       host="demo.ctraderapi.com"  # or live.ctraderapi.com
   )
   ```

### 4. Run the Trade Copier

```bash
python run_copier.py
```

## Configuration Options

### Risk Management

- `LOT_PERCENTAGE`: Percentage of slave account balance to risk per trade (default: 2%)

### Connection Types

- `ConnectionType.DEMO`: For demo accounts
- `ConnectionType.LIVE`: For live accounts

### Hosts

- Demo: `demo.ctraderapi.com`
- Live: `live.ctraderapi.com`

## How It Works

1. **Connection**: Establishes WebSocket connections to both master and slave cTrader accounts
2. **Authorization**: Authenticates using OAuth2 credentials
3. **Monitoring**: Listens for trade executions on the master account
4. **Calculation**: Calculates adjusted lot size based on slave account balance percentage
5. **Execution**: Places corresponding trade on the slave account
6. **Logging**: Records all activities for monitoring and debugging

## Lot Size Calculation

The copier adjusts lot sizes based on the slave account balance:

```
Risk Amount = Slave Balance × LOT_PERCENTAGE
Adjusted Volume = Risk Amount × Micro Lots Per Dollar
```

Example:
- Slave balance: $1,000
- Risk percentage: 2%
- Risk amount: $20
- Adjusted volume: ~2,000 micro lots (0.02 lots)

## Logging

All activities are logged to:
- Console output (INFO level)
- `trade_copier.log` file (detailed logging)

## Safety Features

- Minimum volume enforcement
- Connection monitoring with heartbeat
- Error handling and recovery
- Graceful shutdown on Ctrl+C

## Supported Order Types

- Market orders
- Limit orders  
- Stop orders
- Stop Loss and Take Profit levels

## Rate Limits

cTrader API has rate limits:
- 50 requests/second for non-historical data
- 5 requests/second for historical data

The copier respects these limits automatically.

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Check your client credentials
   - Verify access tokens are valid
   - Ensure account IDs are correct

2. **Connection Issues**
   - Check internet connection
   - Verify host URLs (demo vs live)
   - Check firewall settings

3. **No Trades Copying**
   - Ensure master account has trading activity
   - Check account authorization status
   - Verify symbol mappings

### Debug Mode

Enable debug logging by modifying the logging level in `trade_copier.py`:

```python
logging.basicConfig(level=logging.DEBUG, ...)
```

## Disclaimer

- This software is for educational purposes
- Test thoroughly on demo accounts before using with live funds
- Trading involves risk - use at your own discretion
- The authors are not responsible for any losses

## Support

For issues or questions:
1. Check the logs in `trade_copier.log`
2. Verify your configuration
3. Test with demo accounts first

## License

This project is provided as-is for educational purposes. 