# cTrader to cTrader Trade Copier

A Python-based trade copier that copies trades from one cTrader account (master) to another cTrader account (slave) using the official cTrader Open API.

## Features

- ✅ **Single Connection Architecture**: Uses one connection per environment (demo/live) as per cTrader API best practices
- ✅ **Real-time Trade Copying**: Instantly copies trades from master to slave account
- ✅ **Position Management**: Properly handles both position opens and closes
- ✅ **Configurable Lot Sizes**: Flexible lot size multipliers for different instruments
- ✅ **Multi-Instrument Support**: Forex, Gold, Silver, Indices, Commodities, Crypto
- ✅ **Broker-Agnostic**: Adapts to different broker contract sizes
- ✅ **Safety Limits**: Built-in minimum/maximum lot size protection
- ✅ **Comprehensive Logging**: Detailed logs for monitoring and debugging

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Your Accounts**
   ```bash
   cp config_template.py config.py
   # Edit config.py with your credentials and settings
   ```

3. **Test Lot Size Configuration**
   ```bash
   python config_helper.py
   ```

4. **Run the Trade Copier**
   ```bash
   python trade_copier_single.py
   ```

## Configuration

### Basic Setup

Edit `config.py` with your cTrader API credentials:

```python
# Your API credentials
all_client_id = "your_client_id"
all_client_secret = "your_client_secret" 
all_access_token = "your_access_token"
master_account_id = 12345678  # Account to copy FROM
slave_account_id = 87654321   # Account to copy TO
```

### Lot Size Multipliers

The key feature is the flexible lot size configuration. You can set different multipliers for different instruments:

```python
LOT_SIZE_MULTIPLIERS = {
    # Forex pairs - 50% of master volume
    "EURUSD": 0.5,
    "GBPUSD": 0.5,
    
    # Gold - adjust based on your broker
    "XAUUSD": 0.5,  # 0.02 master → 0.01 slave
    
    # Indices - smaller multipliers due to higher contract values
    "US30": 0.1,    # 10% of master volume
    "SPX500": 0.1,
    
    # Crypto - very volatile, smaller multipliers
    "BTCUSD": 0.1,
    "ETHUSD": 0.2,
}
```

### Configuration Options

| Setting | Description | Example |
|---------|-------------|---------|
| `LOT_SIZE_MULTIPLIERS` | Instrument-specific multipliers | `"XAUUSD": 0.5` |
| `DEFAULT_LOT_MULTIPLIER` | Default for unlisted instruments | `0.5` |
| `GLOBAL_LOT_MULTIPLIER` | Override all instruments | `None` or `0.5` |
| `MIN_LOT_SIZE` | Minimum order size (micro lots) | `1000` (0.01 lot) |
| `MAX_LOT_MULTIPLIER` | Safety limit | `2.0` (max 200%) |

### Examples

**Scenario 1: Gold Trading**
- Master trades 0.02 lots XAUUSD
- With multiplier 0.5: Slave trades 0.01 lots
- Perfect for different broker contract sizes

**Scenario 2: Forex Trading**  
- Master trades 0.10 lots EURUSD
- With multiplier 0.5: Slave trades 0.05 lots
- Standard 50% risk reduction

**Scenario 3: Index Trading**
- Master trades 0.05 lots US30
- With multiplier 0.1: Slave trades 0.005 lots (minimum 0.01)
- Accounts for high contract values

## Testing Your Configuration

Use the configuration helper to test your settings:

```bash
python config_helper.py
```

This will show you:
- How your current multipliers will work
- Recommendations for specific instruments
- Configuration summary

Example output:
```
Symbol     Master     Slave      Multiplier   Status
------------------------------------------------------------
EURUSD     0.100      0.050      0.500        ✓
XAUUSD     0.020      0.010      0.500        ✓
US30       0.050      0.010      0.100        ✓
```

## Advanced Configuration

### Global Multiplier
Set a single multiplier for all instruments:
```python
GLOBAL_LOT_MULTIPLIER = 0.3  # 30% of master volume for everything
```

### Broker-Specific Adjustments
Different brokers may have different contract sizes. Adjust multipliers accordingly:

```python
# For Broker A (standard contracts)
"XAUUSD": 0.5,

# For Broker B (smaller gold contracts)  
"XAUUSD": 1.0,

# For Broker C (larger gold contracts)
"XAUUSD": 0.25,
```

## How It Works

1. **Connection**: Establishes single connection to cTrader API
2. **Authorization**: Authorizes both master and slave accounts
3. **Monitoring**: Listens for execution events on master account
4. **Detection**: Distinguishes between position opens and closes
5. **Calculation**: Applies appropriate lot size multiplier
6. **Execution**: Places corresponding order on slave account

## Position Management

The copier correctly handles:
- ✅ **New Positions**: Opens corresponding position on slave
- ✅ **Position Closes**: Closes matching position on slave (not opposite trade)
- ✅ **Partial Closes**: Handles partial position closures
- ✅ **Multiple Instruments**: Tracks positions per symbol

## Safety Features

- **Minimum Lot Size**: Never places orders below broker minimum
- **Maximum Multiplier**: Prevents accidentally large positions
- **Error Handling**: Graceful fallbacks for edge cases
- **Logging**: Comprehensive logs for monitoring

## Troubleshooting

### Common Issues

1. **"Config.py not found"**
   - Copy `config_template.py` to `config.py`
   - Fill in your credentials

2. **Wrong lot sizes**
   - Run `python config_helper.py` to test
   - Adjust multipliers in `config.py`
   - Test with small amounts first

3. **Connection issues**
   - Check your API credentials
   - Verify account IDs are correct
   - Ensure accounts are on same environment (demo/live)

4. **Positions not closing properly**
   - Check logs for execution events
   - Verify slave account has matching positions

### Log Analysis

Monitor the logs for:
- `[OPEN]` - New position detected
- `[CLOSE]` - Position close detected  
- `[VOLUME]` - Lot size calculations
- `[SUCCESS]` - Successful operations
- `[ERROR]` - Issues requiring attention

## API Credentials

Get your credentials from:
1. [cTrader Automate](https://ctrader.com/automate)
2. Create new app in API section
3. Get Client ID and Client Secret
4. Use OAuth2 flow for access tokens
5. Find account IDs in cTrader platform

## Requirements

- Python 3.7+
- cTrader Open API Python package
- Valid cTrader API credentials
- Two cTrader accounts (master and slave)

## License

This project is for educational purposes. Use at your own risk. Always test with small amounts first.

## Support

For issues:
1. Check the logs in `trade_copier.log`
2. Run `python config_helper.py` to test configuration
3. Verify your API credentials and account setup
4. Test with demo accounts first 