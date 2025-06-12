"""
cTrader to cTrader Trade Copier
Using Official cTrader Open API Python Package with Single Connection
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import time
from twisted.internet import reactor

# Import cTrader Open API Python package
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *

from config import all_client_id, all_client_secret, all_access_token, master_account_id, slave_account_id, AccountConfig, ConnectionType

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

class TradeCopier:
    """Main trade copier class using single cTrader API connection"""
    
    def __init__(self, master_config: AccountConfig, slave_config: AccountConfig, lot_percentage: float = 0.02):
        self.master_config = master_config
        self.slave_config = slave_config
        self.lot_percentage = lot_percentage
        
        # Single client for both accounts
        self.client = None
        self.is_connected = False
        self.is_app_authorized = False
        
        # Account authorization status
        self.master_authorized = False
        self.slave_authorized = False
        self.authorized_accounts = {}  # account_id -> True
        
        # Determine host based on connection type
        if master_config.connection_type == ConnectionType.LIVE:
            self.host = EndPoints.PROTOBUF_LIVE_HOST
        else:
            self.host = EndPoints.PROTOBUF_DEMO_HOST
        
        self.is_running = False
        
        logger.info(f"Trade copier initialized for {master_config.connection_type.value} environment")
        logger.info(f"Master account: {master_config.account_id}")
        logger.info(f"Slave account: {slave_config.account_id}")
    
    def start(self):
        """Start the trade copier"""
        try:
            logger.info("Starting cTrader Trade Copier with single connection...")
            
            # Create single client
            self.client = Client(self.host, EndPoints.PROTOBUF_PORT, TcpProtocol)
            
            # Set callbacks
            self.client.setConnectedCallback(self._on_connected)
            self.client.setDisconnectedCallback(self._on_disconnected)
            self.client.setMessageReceivedCallback(self._on_message_received)
            
            # Start the client service
            self.client.startService()
            
            self.is_running = True
            logger.info("Trade copier started - waiting for connection...")
            
            # Run Twisted reactor
            reactor.run()
            
        except Exception as e:
            logger.error(f"Failed to start trade copier: {e}")
            self.stop()
    
    def _on_connected(self, client):
        """Callback for client connection"""
        logger.info("Connected to cTrader server")
        self.is_connected = True
        
        # Send application authorization request
        auth_req = ProtoOAApplicationAuthReq()
        auth_req.clientId = self.master_config.client_id
        auth_req.clientSecret = self.master_config.client_secret
        
        deferred = client.send(auth_req)
        deferred.addErrback(self._on_error)
        
        logger.info("Application authorization request sent")
    
    def _on_disconnected(self, client, reason):
        """Callback for client disconnection"""
        logger.info(f"Disconnected from cTrader server: {reason}")
        self.is_connected = False
        self.is_app_authorized = False
        self.master_authorized = False
        self.slave_authorized = False
        self.authorized_accounts.clear()
    
    def _on_message_received(self, client, message):
        """Callback for receiving all messages"""
        try:
            payload_type = message.payloadType
            
            if payload_type == ProtoOAApplicationAuthRes().payloadType:
                logger.info("Application authorized successfully")
                self.is_app_authorized = True
                self._get_account_list(client)
                
            elif payload_type == ProtoOAGetAccountListByAccessTokenRes().payloadType:
                self._handle_account_list(client, message)
                
            elif payload_type == ProtoOAAccountAuthRes().payloadType:
                self._handle_account_auth(client, message)
                
            elif payload_type == ProtoOAExecutionEvent().payloadType:
                self._handle_execution_event(client, message)
                
            elif payload_type == ProtoOASubscribeSpotsRes().payloadType:
                logger.info("Successfully subscribed to spot events")
                
            elif payload_type == ProtoHeartbeatEvent().payloadType:
                # Handle heartbeat
                pass
                
            elif payload_type == ProtoOANewOrderRes().payloadType:
                order_res = Protobuf.extract(message)
                logger.info(f"Order response received for account {order_res.ctidTraderAccountId}")
                
            else:
                logger.debug(f"Received message type: {payload_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def _get_account_list(self, client):
        """Get account list"""
        account_list_req = ProtoOAGetAccountListByAccessTokenReq()
        account_list_req.accessToken = self.master_config.access_token
        
        deferred = client.send(account_list_req)
        deferred.addErrback(self._on_error)
        
        logger.info("Account list request sent")
    
    def _handle_account_list(self, client, message):
        """Handle account list response and authorize both accounts"""
        account_list_res = Protobuf.extract(message)
        accounts = account_list_res.ctidTraderAccount
        
        logger.info(f"Found {len(accounts)} accounts:")
        for account in accounts:
            logger.info(f"  Account ID: {account.ctidTraderAccountId}")
        
        # Authorize master account first
        self._authorize_account(client, self.master_config.account_id, "Master")
    
    def _authorize_account(self, client, account_id, account_type):
        """Authorize a specific account"""
        account_auth_req = ProtoOAAccountAuthReq()
        account_auth_req.ctidTraderAccountId = account_id
        account_auth_req.accessToken = self.master_config.access_token
        
        deferred = client.send(account_auth_req)
        deferred.addErrback(self._on_error)
        
        logger.info(f"{account_type} account authorization request sent for account {account_id}")
    
    def _handle_account_auth(self, client, message):
        """Handle account authorization response"""
        auth_res = Protobuf.extract(message)
        account_id = auth_res.ctidTraderAccountId
        
        self.authorized_accounts[account_id] = True
        logger.info(f"Account {account_id} authorized successfully")
        
        # Check which account was authorized
        if account_id == self.master_config.account_id:
            self.master_authorized = True
            logger.info("✅ Master account ready")
            
            # Subscribe to execution events for master account
            self._subscribe_to_events(client, account_id)
            
            # Now authorize slave account
            if not self.slave_authorized:
                self._authorize_account(client, self.slave_config.account_id, "Slave")
                
        elif account_id == self.slave_config.account_id:
            self.slave_authorized = True
            logger.info("✅ Slave account ready")
        
        # Check if both accounts are ready
        if self.master_authorized and self.slave_authorized:
            logger.info("🎉 Both accounts authorized - Trade copier is now active!")
    
    def _subscribe_to_events(self, client, account_id):
        """Subscribe to trading events for the master account"""
        try:
            # Subscribe to spot events
            subscribe_req = ProtoOASubscribeSpotsReq()
            subscribe_req.ctidTraderAccountId = account_id
            subscribe_req.symbolId[:] = []  # Subscribe to all symbols
            
            deferred = client.send(subscribe_req)
            deferred.addErrback(self._on_error)
            
            logger.info(f"Subscribed to trading events for account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
    
    def _handle_execution_event(self, client, message):
        """Handle execution event from master account"""
        try:
            execution_event = Protobuf.extract(message)
            
            # Only process events from the master account
            if execution_event.ctidTraderAccountId != self.master_config.account_id:
                return
            
            logger.debug(f"Execution event from master: type={execution_event.executionType if hasattr(execution_event, 'executionType') else 'Unknown'}")
            
            # Check if this is a trade execution
            if hasattr(execution_event, 'executionType') and execution_event.executionType in ['ORDER_FILLED', 'ORDER_PARTIAL_FILL']:
                
                logger.info(f"🚀 Trade execution detected on master account!")
                
                # Extract trade information
                trade_signal = TradeSignal(
                    symbol=self._get_symbol_name(execution_event.symbolId),
                    order_type="MARKET",
                    side="BUY" if execution_event.tradeSide == ProtoOATradeSide.BUY else "SELL",
                    volume=execution_event.volume,
                    price=execution_event.price / 100000 if hasattr(execution_event, 'price') else None,
                    stop_loss=execution_event.stopLoss / 100000 if hasattr(execution_event, 'stopLoss') else None,
                    take_profit=execution_event.takeProfit / 100000 if hasattr(execution_event, 'takeProfit') else None,
                    comment="Copied from master"
                )
                
                # Copy the trade to slave account
                self._copy_trade_to_slave(client, trade_signal)
                    
        except Exception as e:
            logger.error(f"Failed to handle execution event: {e}")
    
    def _copy_trade_to_slave(self, client, trade_signal: TradeSignal):
        """Copy trade from master to slave account"""
        try:
            if not self.slave_authorized:
                logger.error("Cannot copy trade - slave account not authorized")
                return
            
            logger.info(f"📋 Copying trade: {trade_signal.symbol} {trade_signal.side} {trade_signal.volume}")
            
            # Calculate adjusted volume based on slave account balance
            slave_balance = self._get_balance(self.slave_config.account_id)
            adjusted_volume = self._calculate_adjusted_volume(trade_signal.volume, slave_balance)
            
            # Create order for slave account
            order_req = ProtoOANewOrderReq()
            order_req.ctidTraderAccountId = self.slave_config.account_id
            order_req.symbolId = self._get_symbol_id(trade_signal.symbol)
            order_req.orderType = ProtoOAOrderType.MARKET
            order_req.tradeSide = ProtoOATradeSide.BUY if trade_signal.side == "BUY" else ProtoOATradeSide.SELL
            order_req.volume = adjusted_volume
            order_req.comment = f"Copied from master - Adj: {adjusted_volume}"
            
            # Add price for limit/stop orders
            if trade_signal.price:
                order_req.limitPrice = int(trade_signal.price * 100000)
            
            # Add stop loss and take profit
            if trade_signal.stop_loss:
                order_req.stopLoss = int(trade_signal.stop_loss * 100000)
            
            if trade_signal.take_profit:
                order_req.takeProfit = int(trade_signal.take_profit * 100000)
            
            deferred = client.send(order_req)
            deferred.addErrback(self._on_error)
            
            logger.info(f"✅ Trade copied to slave: {trade_signal.symbol} {trade_signal.side} {adjusted_volume}")
            
        except Exception as e:
            logger.error(f"Failed to copy trade: {e}")
    
    def _calculate_adjusted_volume(self, original_volume: int, slave_balance: float) -> int:
        """Calculate adjusted volume based on slave account balance percentage"""
        # Calculate risk amount
        risk_amount = slave_balance * self.lot_percentage
        
        # Simplified calculation
        micro_lots_per_dollar = 10
        adjusted_volume = int(risk_amount * micro_lots_per_dollar)
        
        # Ensure minimum volume
        min_volume = 1000  # 0.01 lots
        adjusted_volume = max(adjusted_volume, min_volume)
        
        logger.info(f"Volume adjustment: Original={original_volume}, Balance=${slave_balance:.2f}, Risk%={self.lot_percentage*100}%, Adjusted={adjusted_volume}")
        
        return adjusted_volume
    
    def _get_balance(self, account_id: int) -> float:
        """Get current account balance"""
        # This would require implementing ProtoOATraderReq
        # For now, return a placeholder
        return 1000.0
    
    def _get_symbol_id(self, symbol_name: str) -> int:
        """Get symbol ID from symbol name"""
        # Simplified mapping - in real implementation, get from symbols API
        symbol_map = {
            "EURUSD": 1,
            "GBPUSD": 2,
            "USDJPY": 3,
            "USDCHF": 4,
            "AUDUSD": 5,
            "USDCAD": 6,
            "NZDUSD": 7,
        }
        return symbol_map.get(symbol_name, 1)
    
    def _get_symbol_name(self, symbol_id: int) -> str:
        """Get symbol name from symbol ID"""
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
    
    def _on_error(self, failure):
        """Error callback"""
        logger.error(f"API Error: {failure}")
    
    def stop(self):
        """Stop the trade copier"""
        logger.info("Stopping trade copier...")
        self.is_running = False
        
        if self.client:
            self.client.disconnect()
        
        # Stop reactor
        if reactor.running:
            reactor.stop()
        
        logger.info("Trade copier stopped")

def main():
    """Main function to run the trade copier"""
    
    master_config = AccountConfig(
        client_id=all_client_id,
        client_secret=all_client_secret,
        access_token=all_access_token,
        account_id=master_account_id,
        connection_type=ConnectionType.DEMO
    )

    slave_config = AccountConfig(
        client_id=all_client_id,
        client_secret=all_client_secret,
        access_token=all_access_token,
        account_id=slave_account_id,
        connection_type=ConnectionType.DEMO
    )
    
    # Create and start trade copier
    copier = TradeCopier(master_config, slave_config, lot_percentage=0.02)
    
    try:
        copier.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        copier.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        copier.stop()

if __name__ == "__main__":
    print("cTrader to cTrader Trade Copier")
    print("=" * 50)
    print("Using Single Connection for Both Accounts")
    print("=" * 50)
    
    main()
