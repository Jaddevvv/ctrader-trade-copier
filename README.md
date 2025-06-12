# cTrader to cTrader Trade Copier

A Python tool that mirrors all trades from one cTrader account **(master)** to another **(slave)** via the official cTrader Open API.

---

## Key Features

* **Single connection architecture** – both accounts share one TCP connection (per environment) in line with cTrader best-practice.
* **Real-time execution events** – new positions, partial closes and full closes are detected instantly and replicated.
* **Automatic volume adjustment**  
  * Primary control: `GLOBAL_LOT_MULTIPLIER` in `config.py` (e.g. `0.5` = copy 50 % of the master volume).  
  * Safety guard rails: `MIN_LOT_SIZE` and `MAX_LOT_MULTIPLIER`.
* **Experimental dynamic-pip mode** – the copier can attempt to equalise risk between brokers by comparing pip-values (falls back to the global multiplier when data is missing).
* **Broker-agnostic symbol mapping** – common IDs for Forex, Metals, Indices, Crypto are built-in; extend the mapping if your broker uses different IDs.
* **Verbose logging** – everything is written to `trade_copier.log` and printed to the console.

---

## 1  Installation

```bash
# clone / download this repository first

pip install -r requirements.txt
```

The only mandatory runtime dependency is the *cTrader-open-api* Python package (declared in `requirements.txt`).

---

## 2  Configuration

1. Copy the template and edit the values:

```bash
cp config_template.py config.py
```

2. Open `config.py` and fill in **Client ID**, **Client Secret**, **Access Token** and the **account IDs** for your master and slave accounts.

3. Adjust risk parameters if desired:

```python
# Percentage of master volume to copy (0.5 = 50 %)
GLOBAL_LOT_MULTIPLIER = 0.5

# Absolute safety limits (micro-lots)
MIN_LOT_SIZE = 100        # never smaller than 0.01 lot on XAUUSD, for example
MAX_LOT_MULTIPLIER = 2.0  # never larger than 200 % of the master volume
```

> ℹ️ `GLOBAL_LOT_MULTIPLIER` is applied to **all** instruments.  If you need instrument-specific logic you can extend `_calculate_adjusted_volume()` in `trade_copier_single.py`.

---

## 3  Running the Copier

```bash
python trade_copier_single.py
```

You should see output similar to:

```text
cTrader to cTrader Trade Copier - Single Connection
=======================================================
2024-03-01 12:34:56 – INFO – Starting trade copier with single connection…
…
```

The program will continue running until you press **Ctrl-C**.

---

## How It Works (high level)

1. Connects to the cTrader demo/live endpoint over TCP (protobuf).
2. Performs application auth → fetches list of accounts → authorises master & slave.
3. Subscribes to execution events (master) and spot prices (both) for the most common instruments.
4. Whenever the master account receives an execution-event the copier:
   * identifies whether it is a **new position** or a **close / partial close**;
   * recalculates the volume for the slave (global multiplier or dynamic-pip risk method);
   * sends a corresponding *MARKET* order (or *CLOSE* request) on the slave account.

---

## Logs & Troubleshooting

* **Log file**: `trade_copier.log` grows quickly; rotate / tail as needed.
* **Common issues**
  1. *Auth failed* – check `client_id`, `client_secret`, `access_token`.
  2. *Wrong environment* – ensure both accounts are DEMO or both are LIVE.
  3. *Symbol not found* – extend `_get_symbol_id()` / `_get_symbol_name()` mapping.
  4. *Volume rejected* – confirm your broker's minimum lot size; tweak `MIN_LOT_SIZE`.

---

## License / Disclaimer

This repository is provided **as-is** for educational purposes. Trading carries risk; test on demo accounts first and trade responsibly.

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

## Support

For issues:
1. Check the logs in `trade_copier.log`
2. Verify your API credentials and account setup
3. Test with demo accounts first 