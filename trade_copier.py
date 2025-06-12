import asyncio
import websockets
import json
import struct
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trade_copier.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

@dataclass
class TradeSignal:
    """Represents a trade signal to be copied"""
    symbol: str
    order_type: str  # "MARKET", "LIMIT", "STOP"
    side: str  # "BUY", "SELL"
    volume: int  # in micro lots
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    comment: Optional[str] = None

class CTraderConnection:
    """Handles connection to cTrader Open API"""
    
    def __init__(self, config: AccountConfig):
        self.config = config
        self.websocket = None
        self.is_connected = False
        self.is_authorized = False
        self.account_info = {}
        self.positions = {}
        self.orders = {}
        
    async def connect(self):
        """Establish connection to cTrader API"""
        try:
            uri = f"wss://{self.config.host}:{self.config.port}"
            self.websocket = await websockets.connect(uri)
            self.is_connected = True
            logger.info(f"Connected to {self.config.connection_type.value} server")
            
            # Start heartbeat task
            asyncio.create_task(self._heartbeat())
            
            # Authorize the application
            await self._authorize_application()
            
            # Get account list and authorize account
            await self._authorize_account()
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise
    
    async def _heartbeat(self):
        """Send heartbeat every 10 seconds to keep connection alive"""
        while self.is_connected:
            try:
                heartbeat_msg = {
                    "payloadType": "PROTO_OA_HEARTBEAT_EVENT",
                    "payload": {}
                }
                await self._send_message(heartbeat_msg)
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                break
    
    async def _authorize_application(self):
        """Authorize the application with client credentials"""
        auth_msg = {
            "payloadType": "PROTO_OA_APPLICATION_AUTH_REQ",
            "payload": {
                "clientId": self.config.client_id,
                "clientSecret": self.config.client_secret
            }
        }
        await self._send_message(auth_msg)
        
        # Wait for authorization response
        response = await self._receive_message()
        if response.get("payloadType") == "PROTO_OA_APPLICATION_AUTH_RES":
            logger.info("Application authorized successfully")
        else:
            raise Exception("Application authorization failed")
    
    async def _authorize_account(self):
        """Get account list and authorize specific account"""
        # Get account list
        account_list_msg = {
            "payloadType": "PROTO_OA_GET_ACCOUNT_LIST_BY_ACCESS_TOKEN_REQ",
            "payload": {
                "accessToken": self.config.access_token
            }
        }
        await self._send_message(account_list_msg)
        
        response = await self._receive_message()
        if response.get("payloadType") == "PROTO_OA_GET_ACCOUNT_LIST_BY_ACCESS_TOKEN_RES":
            accounts = response.get("payload", {}).get("ctidTraderAccount", [])
            logger.info(f"Found {len(accounts)} accounts")
            
            # Authorize specific account
            account_auth_msg = {
                "payloadType": "PROTO_OA_ACCOUNT_AUTH_REQ",
                "payload": {
                    "ctidTraderAccountId": self.config.account_id,
                    "accessToken": self.config.access_token
                }
            }
            await self._send_message(account_auth_msg)
            
            auth_response = await self._receive_message()
            if auth_response.get("payloadType") == "PROTO_OA_ACCOUNT_AUTH_RES":
                self.is_authorized = True
                logger.info(f"Account {self.config.account_id} authorized successfully")
                
                # Get initial account info
                await self._get_account_info()
            else:
                raise Exception("Account authorization failed")
    
    async def _get_account_info(self):
        """Get account balance and other information"""
        try:
            # Subscribe to spot events for this account
            subscribe_msg = {
                "payloadType": "PROTO_OA_SUBSCRIBE_SPOTS_REQ",
                "payload": {
                    "ctidTraderAccountId": self.config.account_id,
                    "symbolId": []  # Subscribe to all symbols
                }
            }
            await self._send_message(subscribe_msg)
            
            # Get current positions
            positions_msg = {
                "payloadType": "PROTO_OA_GET_POSITIONS_REQ",
                "payload": {
                    "ctidTraderAccountId": self.config.account_id
                }
            }
            await self._send_message(positions_msg)
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
    
    async def get_balance(self) -> float:
        """Get current account balance"""
        # Request trader info
        trader_msg = {
            "payloadType": "PROTO_OA_TRADER_REQ",
            "payload": {
                "ctidTraderAccountId": self.config.account_id
            }
        }
        await self._send_message(trader_msg)
        
        response = await self._receive_message()
        if response.get("payloadType") == "PROTO_OA_TRADER_RES":
            trader_data = response.get("payload", {}).get("trader", {})
            balance = trader_data.get("balance", 0) / 100  # Convert from cents
            logger.info(f"Account balance: {balance}")
            return balance
        return 0.0
    
    async def place_order(self, trade_signal: TradeSignal):
        """Place an order based on trade signal"""
        try:
            order_msg = {
                "payloadType": "PROTO_OA_NEW_ORDER_REQ",
                "payload": {
                    "ctidTraderAccountId": self.config.account_id,
                    "symbolId": await self._get_symbol_id(trade_signal.symbol),
                    "orderType": trade_signal.order_type,
                    "tradeSide": trade_signal.side,
                    "volume": trade_signal.volume,
                    "comment": trade_signal.comment or "Trade Copier"
                }
            }
            
            # Add price for limit/stop orders
            if trade_signal.price:
                order_msg["payload"]["limitPrice"] = int(trade_signal.price * 100000)  # Convert to points
            
            # Add stop loss and take profit
            if trade_signal.stop_loss:
                order_msg["payload"]["stopLoss"] = int(trade_signal.stop_loss * 100000)
            
            if trade_signal.take_profit:
                order_msg["payload"]["takeProfit"] = int(trade_signal.take_profit * 100000)
            
            await self._send_message(order_msg)
            logger.info(f"Order placed: {trade_signal.symbol} {trade_signal.side} {trade_signal.volume}")
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
    
    async def _get_symbol_id(self, symbol_name: str) -> int:
        """Get symbol ID from symbol name"""
        # This is a simplified mapping - in real implementation, 
        # you'd get this from the symbols list API call
        symbol_map = {
            "EURUSD": 1,
            "GBPUSD": 2,
            "USDJPY": 3,
            "USDCHF": 4,
            "AUDUSD": 5,
            "USDCAD": 6,
            "NZDUSD": 7,
            # Add more symbols as needed
        }
        return symbol_map.get(symbol_name, 1)
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send message to cTrader API"""
        if not self.websocket:
            raise Exception("Not connected")
        
        json_message = json.dumps(message)
        await self.websocket.send(json_message)
        logger.debug(f"Sent: {message['payloadType']}")
    
    async def _receive_message(self) -> Dict[str, Any]:
        """Receive message from cTrader API"""
        if not self.websocket:
            raise Exception("Not connected")
        
        raw_message = await self.websocket.recv()
        message = json.loads(raw_message)
        logger.debug(f"Received: {message.get('payloadType', 'Unknown')}")
        return message
    
    async def listen_for_trades(self, callback):
        """Listen for incoming trade events"""
        while self.is_connected and self.is_authorized:
            try:
                message = await self._receive_message()
                payload_type = message.get("payloadType")
                
                # Handle different message types
                if payload_type == "PROTO_OA_EXECUTION_EVENT":
                    await self._handle_execution_event(message, callback)
                elif payload_type == "PROTO_OA_ORDER_ERROR_EVENT":
                    logger.error(f"Order error: {message}")
                
            except Exception as e:
                logger.error(f"Error listening for trades: {e}")
                await asyncio.sleep(1)
    
    async def _handle_execution_event(self, message: Dict[str, Any], callback):
        """Handle execution event (new position, order fill, etc.)"""
        payload = message.get("payload", {})
        execution_type = payload.get("executionType")
        
        if execution_type in ["ORDER_FILLED", "ORDER_PARTIAL_FILL"]:
            # Extract trade information
            symbol_id = payload.get("symbolId")
            symbol_name = await self._get_symbol_name(symbol_id)
            
            trade_signal = TradeSignal(
                symbol=symbol_name,
                order_type="MARKET",
                side="BUY" if payload.get("tradeSide") == "BUY" else "SELL",
                volume=payload.get("volume", 0),
                price=payload.get("price", 0) / 100000 if payload.get("price") else None,
                stop_loss=payload.get("stopLoss", 0) / 100000 if payload.get("stopLoss") else None,
                take_profit=payload.get("takeProfit", 0) / 100000 if payload.get("takeProfit") else None,
                comment="Copied from master"
            )
            
            await callback(trade_signal)
    
    async def _get_symbol_name(self, symbol_id: int) -> str:
        """Get symbol name from symbol ID"""
        # Reverse mapping - in real implementation, maintain a proper symbol cache
        id_to_symbol = {
            1: "EURUSD",
            2: "GBPUSD", 
            3: "USDJPY",
            4: "USDCHF",
            5: "AUDUSD",
            6: "USDCAD",
            7: "NZDUSD"
        }
        return id_to_symbol.get(symbol_id, "UNKNOWN")
    
    async def disconnect(self):
        """Close the connection"""
        self.is_connected = False
        self.is_authorized = False
        if self.websocket:
            await self.websocket.close()

class TradeCopier:
    """Main trade copier class"""
    
    def __init__(self, master_config: AccountConfig, slave_config: AccountConfig, lot_percentage: float = 0.02):
        self.master_config = master_config
        self.slave_config = slave_config
        self.lot_percentage = lot_percentage  # Percentage of balance to risk per trade
        
        self.master_connection = CTraderConnection(master_config)
        self.slave_connection = CTraderConnection(slave_config)
        
        self.is_running = False
    
    async def start(self):
        """Start the trade copier"""
        try:
            logger.info("Starting cTrader Trade Copier...")
            
            # Connect to both accounts
            await self.master_connection.connect()
            await self.slave_connection.connect()
            
            logger.info("Both accounts connected and authorized")
            
            # Start listening for trades on master account
            self.is_running = True
            await self.master_connection.listen_for_trades(self._handle_master_trade)
            
        except Exception as e:
            logger.error(f"Failed to start trade copier: {e}")
            await self.stop()
    
    async def _handle_master_trade(self, trade_signal: TradeSignal):
        """Handle trade signal from master account"""
        try:
            logger.info(f"Master trade detected: {trade_signal.symbol} {trade_signal.side} {trade_signal.volume}")
            
            # Calculate adjusted lot size based on slave account balance
            slave_balance = await self.slave_connection.get_balance()
            adjusted_volume = self._calculate_adjusted_volume(trade_signal.volume, slave_balance)
            
            # Create adjusted trade signal
            adjusted_signal = TradeSignal(
                symbol=trade_signal.symbol,
                order_type=trade_signal.order_type,
                side=trade_signal.side,
                volume=adjusted_volume,
                price=trade_signal.price,
                stop_loss=trade_signal.stop_loss,
                take_profit=trade_signal.take_profit,
                comment=f"Copied - Adj: {adjusted_volume}"
            )
            
            # Place order on slave account
            await self.slave_connection.place_order(adjusted_signal)
            
            logger.info(f"Trade copied to slave: {adjusted_signal.symbol} {adjusted_signal.side} {adjusted_volume}")
            
        except Exception as e:
            logger.error(f"Failed to copy trade: {e}")
    
    def _calculate_adjusted_volume(self, original_volume: int, slave_balance: float) -> int:
        """Calculate adjusted volume based on slave account balance percentage"""
        # Calculate risk amount based on percentage of balance
        risk_amount = slave_balance * self.lot_percentage
        
        # For simplicity, assume 1 micro lot = $0.10 risk (adjust based on your broker)
        # This is a simplified calculation - in reality, you'd need to consider:
        # - Symbol specifications (contract size, tick value)
        # - Current market price
        # - Stop loss distance
        micro_lots_per_dollar = 10  # Simplified assumption
        
        adjusted_volume = int(risk_amount * micro_lots_per_dollar)
        
        # Ensure minimum volume (usually 1000 micro lots = 0.01 lots)
        min_volume = 1000
        adjusted_volume = max(adjusted_volume, min_volume)
        
        logger.info(f"Volume adjustment: Original={original_volume}, Balance=${slave_balance:.2f}, Risk%={self.lot_percentage*100}%, Adjusted={adjusted_volume}")
        
        return adjusted_volume
    
    async def stop(self):
        """Stop the trade copier"""
        logger.info("Stopping trade copier...")
        self.is_running = False
        
        await self.master_connection.disconnect()
        await self.slave_connection.disconnect()
        
        logger.info("Trade copier stopped")

async def main():
    """Main function to run the trade copier"""
    
    # Configuration - REPLACE WITH YOUR ACTUAL VALUES
    master_config = AccountConfig(
        client_id="YOUR_MASTER_CLIENT_ID",
        client_secret="YOUR_MASTER_CLIENT_SECRET", 
        access_token="YOUR_MASTER_ACCESS_TOKEN",
        account_id=12345678,  # Your master account ID
        connection_type=ConnectionType.DEMO,  # Change to LIVE for live trading
        host="demo.ctraderapi.com"  # Use "live.ctraderapi.com" for live
    )
    
    slave_config = AccountConfig(
        client_id="YOUR_SLAVE_CLIENT_ID",
        client_secret="YOUR_SLAVE_CLIENT_SECRET",
        access_token="YOUR_SLAVE_ACCESS_TOKEN", 
        account_id=87654321,  # Your slave account ID
        connection_type=ConnectionType.DEMO,  # Change to LIVE for live trading
        host="demo.ctraderapi.com"  # Use "live.ctraderapi.com" for live
    )
    
    # Create trade copier with 2% balance risk per trade
    copier = TradeCopier(master_config, slave_config, lot_percentage=0.02)
    
    try:
        await copier.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await copier.stop()

if __name__ == "__main__":
    print("cTrader to cTrader Trade Copier")
    print("=" * 40)
    print("Please configure your account details in the main() function")
    print("before running this script.")
    print("=" * 40)
    
    # Uncomment the line below after configuring your accounts
    # asyncio.run(main())
    
    print("Configuration required. Please edit the main() function with your account details.")
