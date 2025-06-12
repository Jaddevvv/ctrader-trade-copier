"""
cTrader to cTrader Trade Copier - Single Connection Version
Using one connection to manage both master and slave accounts
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from twisted.internet import reactor

# Import cTrader Open API Python package
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *

from config import (
    all_client_id, all_client_secret, all_access_token, 
    master_account_id, slave_account_id, AccountConfig, ConnectionType,
    GLOBAL_LOT_MULTIPLIER,
    MIN_LOT_SIZE, MAX_LOT_MULTIPLIER,
)

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
    order_type: str
    side: str  # "BUY", "SELL"
    volume: int  # in micro lots
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    comment: Optional[str] = None
    symbol_id: Optional[int] = None  # Store original symbol ID

@dataclass
class SymbolData:
    """Complete symbol information for pip value calculation"""
    symbol_id: int
    symbol_name: str
    digits: int
    pip_position: int
    lot_size: int
    base_asset_id: int
    quote_asset_id: int
    current_bid: float = 0.0
    current_ask: float = 0.0
    volume_step: int = 100

@dataclass
class AssetData:
    """Asset information"""
    asset_id: int
    name: str
    digits: int

class SingleConnectionTradeCopier:
    """Trade copier using single connection for both accounts"""
    
    def __init__(self, master_config: AccountConfig, slave_config: AccountConfig):
        self.master_config = master_config
        self.slave_config = slave_config
        
        # Single client for both accounts
        self.client = None
        self.is_connected = False
        self.is_app_authorized = False
        
        # Track authorization status
        self.master_authorized = False
        self.slave_authorized = False
        
        # Data storage for pip value calculation
        self.master_symbols = {}  # symbol_id -> SymbolData
        self.slave_symbols = {}   # symbol_id -> SymbolData
        self.master_assets = {}   # asset_id -> AssetData
        self.slave_assets = {}    # asset_id -> AssetData
        self.master_deposit_asset_id = None
        self.slave_deposit_asset_id = None
        
        # Pip values cache and pending trades
        self.pip_values_cache = {}  # symbol_id -> {"master_pip_value": value, "slave_pip_value": value}
        self.pending_trades = {}  # symbol_id -> trade_signal (waiting for pip values)
        
        # Track data loading status
        self.master_data_loaded = False
        self.slave_data_loaded = False
        
        # Track volume ratio used for each symbol so we can apply the same ratio for partial closes
        # Key: symbol_id  Value: ratio (slave_volume / master_volume) used when opening
        self.symbol_volume_ratio: Dict[int, float] = {}
        
        # Determine host
        if master_config.connection_type == ConnectionType.LIVE:
            self.host = EndPoints.PROTOBUF_LIVE_HOST
        else:
            self.host = EndPoints.PROTOBUF_DEMO_HOST
        
        logger.info(f"Trade copier initialized for {master_config.connection_type.value}")
        logger.info(f"Master account: {master_config.account_id}")
        logger.info(f"Slave account: {slave_config.account_id}")
    
    def start(self):
        """Start the trade copier"""
        try:
            logger.info("Starting trade copier with single connection...")
            
            # Create single client
            self.client = Client(self.host, EndPoints.PROTOBUF_PORT, TcpProtocol)
            
            # Set callbacks
            self.client.setConnectedCallback(self._on_connected)
            self.client.setDisconnectedCallback(self._on_disconnected)
            self.client.setMessageReceivedCallback(self._on_message_received)
            
            # Start the client service
            self.client.startService()
            
            logger.info("Client service started - waiting for connection...")
            
            # Run Twisted reactor
            reactor.run()
            
        except Exception as e:
            logger.error(f"Failed to start trade copier: {e}")
            self.stop()
    
    def _on_connected(self, client):
        """Callback for client connection"""
        logger.info("Connected to cTrader server")
        self.is_connected = True
        
        # Send application authorization
        auth_req = ProtoOAApplicationAuthReq()
        auth_req.clientId = self.master_config.client_id
        auth_req.clientSecret = self.master_config.client_secret
        
        deferred = client.send(auth_req)
        deferred.addErrback(self._on_error)
        
        logger.info("Application authorization sent")
    
    def _on_disconnected(self, client, reason):
        """Callback for disconnection"""
        logger.info(f"Disconnected: {reason}")
        self.is_connected = False
        self.is_app_authorized = False
        self.master_authorized = False
        self.slave_authorized = False
    
    def _on_message_received(self, client, message):
        """Handle all incoming messages"""
        try:
            payload_type = message.payloadType
            
            # Only log non-market data messages to reduce noise
            if payload_type != 2131:  # Skip ProtoOASpotEvent (market data)
                logger.info(f"[DEBUG] Received message type: {payload_type}")
            
            if payload_type == ProtoOAApplicationAuthRes().payloadType:
                logger.info("[SUCCESS] Application authorized")
                self.is_app_authorized = True
                self._get_account_list(client)
                
            elif payload_type == ProtoOAGetAccountListByAccessTokenRes().payloadType:
                self._handle_account_list(client, message)
                
            elif payload_type == ProtoOAAccountAuthRes().payloadType:
                self._handle_account_auth(client, message)
                
            elif payload_type == ProtoOAExecutionEvent().payloadType:
                logger.info(f"[DEBUG] ProtoOAExecutionEvent received (type {payload_type})")
                self._handle_execution_event(client, message)
                
            elif payload_type == ProtoOASymbolByIdRes().payloadType:
                # Handle symbol information responses (for pip values)
                pass  # Will be handled by callback in _handle_symbol_info
                
            elif payload_type == ProtoOAAssetListRes().payloadType:
                # Handle asset list responses
                pass  # Will be handled by callback in _handle_asset_list
                
            elif payload_type == ProtoOATraderRes().payloadType:
                # Handle trader info responses (for deposit currency)
                pass  # Will be handled by callback in _handle_trader_info
                
            elif payload_type == ProtoOASpotEvent().payloadType:
                # Handle market data for pip value calculation
                self._handle_spot_event(client, message)
                
            elif payload_type == ProtoHeartbeatEvent().payloadType:
                pass  # Heartbeat handled automatically
                
            else:
                # Only log unknown message types (not market data)
                if payload_type != 2131:  # Skip ProtoOASpotEvent (market data)
                    logger.info(f"[DEBUG] Unknown message type: {payload_type}")
                    try:
                        extracted_message = Protobuf.extract(message)
                        logger.info(f"[DEBUG] Message content: {extracted_message}")
                    except Exception as e:
                        logger.info(f"[DEBUG] Could not extract message: {e}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def _get_account_list(self, client):
        """Get list of accounts"""
        account_list_req = ProtoOAGetAccountListByAccessTokenReq()
        account_list_req.accessToken = self.master_config.access_token
        
        deferred = client.send(account_list_req)
        deferred.addErrback(self._on_error)
        
        logger.info("Requesting account list...")
    
    def _handle_account_list(self, client, message):
        """Handle account list and authorize both accounts"""
        account_list_res = Protobuf.extract(message)
        accounts = account_list_res.ctidTraderAccount
        
        logger.info(f"Found {len(accounts)} accounts:")
        for account in accounts:
            logger.info(f"  - Account ID: {account.ctidTraderAccountId}")
        
        # Authorize master account first
        self._authorize_account(client, self.master_config.account_id)
    
    def _authorize_account(self, client, account_id):
        """Authorize a specific account"""
        account_auth_req = ProtoOAAccountAuthReq()
        account_auth_req.ctidTraderAccountId = account_id
        account_auth_req.accessToken = self.master_config.access_token
        
        deferred = client.send(account_auth_req)
        deferred.addErrback(self._on_error)
        
        account_type = "Master" if account_id == self.master_config.account_id else "Slave"
        logger.info(f"Authorizing {account_type} account {account_id}...")
    
    def _handle_account_auth(self, client, message):
        """Handle account authorization response"""
        auth_res = Protobuf.extract(message)
        account_id = auth_res.ctidTraderAccountId
        
        if account_id == self.master_config.account_id:
            self.master_authorized = True
            logger.info(f"[SUCCESS] Master account {account_id} authorized")
            
            # Subscribe to events for master
            self._subscribe_to_events(client, account_id)
            
            # Load master account data for pip calculations
            self._load_account_data(client, account_id, "master")
            
            # Now authorize slave account
            self._authorize_account(client, self.slave_config.account_id)
            
        elif account_id == self.slave_config.account_id:
            self.slave_authorized = True
            logger.info(f"[SUCCESS] Slave account {account_id} authorized")
            
            # Load slave account data for pip calculations
            self._load_account_data(client, account_id, "slave")
        
        # Check if both accounts are ready
        if self.master_authorized and self.slave_authorized:
            logger.info("[ACTIVE] Both accounts ready - Trade copier is active!")
    
    def _subscribe_to_events(self, client, account_id):
        """Subscribe to trading events"""
        # Subscribe to execution events (trades)
        logger.info(f"[DEBUG] Subscribing to execution events for account {account_id}")
        
        # Note: For execution events, we don't need to send a subscription request
        # The API automatically sends execution events for authorized accounts
        # But let's also subscribe to spots for market data
        try:
            subscribe_req = ProtoOASubscribeSpotsReq()
            subscribe_req.ctidTraderAccountId = account_id
            # Subscribe to major currency pairs
            subscribe_req.symbolId[:] = [1, 2, 3, 4, 5, 6, 7]  # Major pairs
            
            deferred = client.send(subscribe_req)
            deferred.addErrback(self._on_error)
            
            logger.info(f"[SUCCESS] Subscribed to market data for account {account_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
        
        logger.info(f"[INFO] Account {account_id} ready to receive execution events")
    
    def _handle_execution_event(self, client, message):
        """Handle trade execution from master account"""
        try:
            execution_event = Protobuf.extract(message)
            logger.info(f"[DEBUG] Execution event received: {execution_event}")
            
            # Only process master account events
            if execution_event.ctidTraderAccountId != self.master_config.account_id:
                logger.info(f"[DEBUG] Ignoring event from account {execution_event.ctidTraderAccountId} (not master)")
                return
            
            logger.info(f"[DEBUG] Processing execution event from master account {execution_event.ctidTraderAccountId}")
            
            # Check for different execution types
            execution_type = getattr(execution_event, 'executionType', None)
            logger.info(f"[DEBUG] Execution type: {execution_type}")
            
            # Handle various execution types that indicate a trade
            # execution_type values: 1=ORDER_ACCEPTED, 2=ORDER_ACCEPTED, 3=ORDER_FILLED, 4=ORDER_PARTIAL_FILL, etc.
            if execution_type in [3, 4]:  # ORDER_FILLED=3, ORDER_PARTIAL_FILL=4
                logger.info("[TRADE] Trade detected on master account!")
                
                # Get trade details from order and deal
                is_closing_order = False
                symbol_id = None
                trade_side = None
                volume = None
                
                # Check if this is a closing order (from order info)
                if hasattr(execution_event, 'order') and execution_event.order:
                    order = execution_event.order
                    is_closing_order = getattr(order, 'closingOrder', False)
                    logger.info(f"[DEBUG] Is closing order: {is_closing_order}")
                
                # Try to get details from deal first (most accurate for filled orders)
                if hasattr(execution_event, 'deal') and execution_event.deal:
                    deal = execution_event.deal
                    symbol_id = getattr(deal, 'symbolId', None)
                    trade_side = getattr(deal, 'tradeSide', None)
                    volume = getattr(deal, 'volume', None)
                    
                    # Check if deal has closePositionDetail (indicates position closing)
                    has_close_detail = hasattr(deal, 'closePositionDetail')
                    close_detail_value = getattr(deal, 'closePositionDetail', None) if has_close_detail else None
                    logger.info(f"[DEBUG] Deal closePositionDetail check: has_attr={has_close_detail}, value='{close_detail_value}'")
                    
                    # Only consider it a closing order if closePositionDetail exists AND has actual content
                    if has_close_detail and close_detail_value is not None and str(close_detail_value).strip():
                        is_closing_order = True
                        logger.info(f"[DEBUG] Deal has valid closePositionDetail - this is a position close")
                    else:
                        logger.info(f"[DEBUG] Deal has no valid closePositionDetail - this is a new position")
                    
                    logger.info(f"[DEBUG] Got trade details from deal")
                
                # If no deal, try to get from order
                elif hasattr(execution_event, 'order') and execution_event.order:
                    order = execution_event.order
                    if hasattr(order, 'tradeData') and order.tradeData:
                        trade_data = order.tradeData
                        symbol_id = getattr(trade_data, 'symbolId', None)
                        trade_side = getattr(trade_data, 'tradeSide', None)
                        volume = getattr(trade_data, 'volume', None)
                        logger.info(f"[DEBUG] Got trade details from order.tradeData")
                
                # Fallback to execution event itself
                if not symbol_id:
                    symbol_id = getattr(execution_event, 'symbolId', None)
                    trade_side = getattr(execution_event, 'tradeSide', None)
                    volume = getattr(execution_event, 'volume', None)
                    logger.info(f"[DEBUG] Got trade details from execution event")
                
                logger.info(f"[DEBUG] Trade details - Symbol ID: {symbol_id}, Side: {trade_side}, Volume: {volume}, Is Closing: {is_closing_order}")
                
                if symbol_id and trade_side is not None and volume:
                    symbol_name = self._get_symbol_name(symbol_id)
                    
                    if is_closing_order:
                        # This is a position close - we need to close the corresponding position on slave
                        logger.info(f"[CLOSE] Position close detected: {symbol_name}")
                        self._close_slave_position(client, symbol_id, symbol_name, volume)
                    else:
                        # This is a new position - copy to slave
                        logger.info(f"[OPEN] New position detected: {symbol_name}")
                        
                        # Create trade signal with symbol ID
                        trade_signal = TradeSignal(
                            symbol=symbol_name,
                            order_type="MARKET",
                            side="BUY" if trade_side == ProtoOATradeSide.BUY else "SELL",
                            volume=volume,
                            comment="Copied from master"
                        )
                        
                        # Store the original symbol ID for copying
                        trade_signal.symbol_id = symbol_id
                        
                        # Copy to slave
                        self._copy_to_slave(client, trade_signal)
                else:
                    logger.error(f"[ERROR] Missing trade details in execution event")
            else:
                logger.info(f"[DEBUG] Execution type '{execution_type}' not handled for trade copying")
                
        except Exception as e:
            logger.error(f"Error handling execution: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _close_slave_position(self, client, symbol_id, symbol_name, master_close_volume=None):
        """Close corresponding position on slave account"""
        try:
            logger.info(f"[CLOSE] Closing slave position for {symbol_name}")
            
            # We need to get the current positions on slave first using reconcile
            reconcile_req = ProtoOAReconcileReq()
            reconcile_req.ctidTraderAccountId = self.slave_config.account_id
            
            # Send reconcile request and handle response
            deferred = client.send(reconcile_req)
            deferred.addCallback(lambda response: self._handle_positions_for_close(client, response, symbol_id, symbol_name, master_close_volume))
            deferred.addErrback(self._on_error)
            
        except Exception as e:
            logger.error(f"Failed to close slave position: {e}")
    
    def _handle_positions_for_close(self, client, response, symbol_id, symbol_name, master_close_volume=None):
        """Handle reconcile response and close matching position"""
        try:
            reconcile_response = Protobuf.extract(response)
            logger.info(f"[DEBUG] Got reconcile response for closing")
            
            # Find position with matching symbol
            position_to_close = None
            if hasattr(reconcile_response, 'position'):
                for position in reconcile_response.position:
                    # Check if position has tradeData with matching symbolId
                    if hasattr(position, 'tradeData') and position.tradeData:
                        trade_data = position.tradeData
                        if getattr(trade_data, 'symbolId', None) == symbol_id:
                            position_to_close = position
                            break
            
            if position_to_close:
                position_id = getattr(position_to_close, 'positionId', None)
                # Get volume from tradeData
                current_volume = None
                if hasattr(position_to_close, 'tradeData') and position_to_close.tradeData:
                    current_volume = getattr(position_to_close.tradeData, 'volume', None)
                
                if position_id and current_volume:
                    # Determine volume to close based on ratio (partial close)
                    ratio = self.symbol_volume_ratio.get(symbol_id, 1.0)
                    raw_volume_to_close = int(master_close_volume * ratio)

                    # Fetch broker volume step directly in API raw units (0.01 base units)
                    step_raw_units = self.slave_symbols.get(symbol_id).volume_step if symbol_id in self.slave_symbols else MIN_LOT_SIZE
                    if step_raw_units <= 0:
                        step_raw_units = MIN_LOT_SIZE

                    logger.debug(f"[CLOSE-CALC] master_close_volume={master_close_volume}, ratio={ratio}, initial={raw_volume_to_close}, step_raw={step_raw_units}")

                    # Round DOWN to nearest broker-allowed increment
                    volume_to_close = (raw_volume_to_close // step_raw_units) * step_raw_units

                    # If this would leave a remainder smaller than one step, just close everything
                    if current_volume - volume_to_close <= step_raw_units:
                        logger.debug(f"[CLOSE-CALC] Remainder {current_volume - volume_to_close} < step {step_raw_units}. Closing full position instead.")
                        volume_to_close = current_volume

                    logger.info(f"[CLOSE] Closing position {position_id} for {symbol_name} with volume {volume_to_close} (current {current_volume}, step {step_raw_units})")
                    
                    # Create close position order
                    close_order = ProtoOAClosePositionReq()
                    close_order.ctidTraderAccountId = self.slave_config.account_id
                    close_order.positionId = position_id
                    close_order.volume = volume_to_close
                    
                    deferred = client.send(close_order)
                    deferred.addErrback(self._on_error)
                    
                    logger.info(f"[SUCCESS] Position close request sent for {symbol_name}")
                else:
                    logger.error(f"[ERROR] Missing position ID or volume for {symbol_name}")
            else:
                logger.warning(f"[WARNING] No matching position found on slave for {symbol_name}")
                
        except Exception as e:
            logger.error(f"Failed to handle reconcile response for close: {e}")
    
    def _copy_to_slave(self, client, trade_signal: TradeSignal):
        """Copy trade to slave account"""
        try:
            if not self.slave_authorized:
                logger.error("Slave account not authorized")
                return
            
            logger.info(f"[COPY] Copying: {trade_signal.symbol} {trade_signal.side} {trade_signal.volume}")
            
            # For dynamic pip sizing, we'll calculate pip values on-demand
            # The _calculate_dynamic_pip_volume method will handle this automatically
            
            # Calculate adjusted volume with instrument-specific logic
            adjusted_volume = self._calculate_adjusted_volume(trade_signal.symbol, trade_signal.volume)
            
            # Store ratio for partial-close handling
            if trade_signal.volume:
                ratio = adjusted_volume / trade_signal.volume
                self.symbol_volume_ratio[self._get_symbol_id(trade_signal.symbol)] = ratio
            
            # Create order using original symbol ID if available
            symbol_id_to_use = trade_signal.symbol_id if trade_signal.symbol_id else self._get_symbol_id(trade_signal.symbol)
            
            order_req = ProtoOANewOrderReq()
            order_req.ctidTraderAccountId = self.slave_config.account_id
            order_req.symbolId = symbol_id_to_use
            order_req.orderType = ProtoOAOrderType.MARKET
            order_req.tradeSide = ProtoOATradeSide.BUY if trade_signal.side == "BUY" else ProtoOATradeSide.SELL
            order_req.volume = adjusted_volume
            order_req.comment = "Copied from master"
            
            logger.info(f"[DEBUG] Using symbol ID {symbol_id_to_use} for {trade_signal.symbol}")
            logger.info(f"[DEBUG] Original volume: {trade_signal.volume}, Adjusted volume: {adjusted_volume}")
            
            deferred = client.send(order_req)
            deferred.addErrback(self._on_error)
            
            logger.info(f"[SUCCESS] Trade copied: {trade_signal.symbol} {trade_signal.side} {adjusted_volume}")
            
        except Exception as e:
            logger.error(f"Failed to copy trade: {e}")
    
    def _calculate_adjusted_volume(self, symbol, original_volume):
        """Calculate adjusted volume using dynamic pip values or fallback methods"""
        try:
            return self._calculate_dynamic_pip_volume(symbol, original_volume)

                
        except Exception as e:
            logger.error(f"Error calculating adjusted volume: {e}")
            # Fallback to 50% of original volume
            return max(MIN_LOT_SIZE, int(original_volume * 0.5))
    
    def _calculate_dynamic_pip_volume(self, symbol, original_volume):
        """Calculate volume based on dynamic pip values from both brokers"""
        try:
            symbol_id = self._get_symbol_id(symbol)
            
            # # Check if we have pip values cached for this symbol
            # if symbol_id in self.pip_values_cache:
            #     pip_data = self.pip_values_cache[symbol_id]
            #     master_pip_value = pip_data.get("master_pip_value")
            #     slave_pip_value = pip_data.get("slave_pip_value")
                
            #     if master_pip_value and slave_pip_value:
            #         # Calculate risk multiplier based on pip values
            #         # If slave has higher pip value, we need smaller volume to maintain same risk
            #         risk_multiplier = (master_pip_value / slave_pip_value) * DYNAMIC_PIP_VOLUME_RATIO
                    
            #         # Apply safety limits
            #         risk_multiplier = min(risk_multiplier, MAX_LOT_MULTIPLIER)
            #         risk_multiplier = max(risk_multiplier, 0.001)
                    
            #         # Calculate adjusted volume
            #         adjusted_volume = int(original_volume * risk_multiplier)
            #         adjusted_volume = max(MIN_LOT_SIZE, adjusted_volume)
                    
            #         # Log the calculation details
            #         original_lots = original_volume / 100000
            #         adjusted_lots = adjusted_volume / 100000
                    
            #         logger.info(f"[DYNAMIC-PIP] {symbol}: {original_lots:.3f} lot → {adjusted_lots:.3f} lot")
            #         logger.info(f"[DYNAMIC-PIP] Master pip value: ${master_pip_value:.5f}, Slave pip value: ${slave_pip_value:.5f}")
            #         logger.info(f"[DYNAMIC-PIP] Risk multiplier: {risk_multiplier:.4f}")
                    
            #         return adjusted_volume
            
            # If no pip values available, calculate them now
            logger.info(f"[DYNAMIC-PIP] No pip values cached for {symbol}, calculating...")
            
            # Try to calculate pip values if we have the necessary data
            logger.info(f"[DYNAMIC-PIP] Attempting to calculate pip values for {symbol} (ID: {symbol_id})")
            
            master_pip_value = self._calculate_pip_value(symbol_id, "master")
            slave_pip_value = self._calculate_pip_value(symbol_id, "slave")
            
            logger.info(f"[DYNAMIC-PIP] Results: Master pip value: {master_pip_value}, Slave pip value: {slave_pip_value}")
            
            if master_pip_value and slave_pip_value:
                # Cache the calculated values
                self.pip_values_cache[symbol_id] = {
                    "master_pip_value": master_pip_value,
                    "slave_pip_value": slave_pip_value
                }
                
                # Recursively call this method now that we have the values
                return self._calculate_dynamic_pip_volume(symbol, original_volume)
            
            # If we still don't have pip values, load the necessary data
            if not self.master_data_loaded or not self.slave_data_loaded:
                logger.info(f"[DYNAMIC-PIP] Account data not fully loaded, using fallback...")
            else:
                logger.info(f"[DYNAMIC-PIP] Unable to calculate pip values for {symbol}, using fallback...")
            
            # Use fallback calculation
            return self._calculate_simple_multiplier_volume(symbol, original_volume)
            
        except Exception as e:
            logger.error(f"Error in dynamic pip volume calculation: {e}")
            return self._calculate_simple_multiplier_volume(symbol, original_volume)
    

    def _get_symbol_id(self, symbol_name: str) -> int:
        """Map symbol name to ID - Extended mapping"""
        symbol_map = {
            # Major Forex Pairs
            "EURUSD": 1, "GBPUSD": 2, "USDJPY": 3, "USDCHF": 4, 
            "AUDUSD": 5, "USDCAD": 6, "NZDUSD": 7,
            # Additional common symbols (these IDs may vary by broker)
            "XAUUSD": 41, "GOLD": 41,  # Gold
            "XAGUSD": 42, "SILVER": 42,  # Silver
            "BTCUSD": 43, "ETHUSD": 44,  # Crypto
            "US30": 45, "SPX500": 46, "NAS100": 47,  # Indices
            "CRUDE": 48, "BRENT": 49,  # Oil
        }
        return symbol_map.get(symbol_name, symbol_id if isinstance(symbol_name, int) else 1)
    

    
    def _get_symbol_name(self, symbol_id: int) -> str:
        """Map symbol ID to name - Extended mapping"""
        id_to_symbol = {
            # Major Forex Pairs
            1: "EURUSD", 2: "GBPUSD", 3: "USDJPY", 4: "USDCHF",
            5: "AUDUSD", 6: "USDCAD", 7: "NZDUSD",
            # Additional common symbols
            41: "XAUUSD",  # Gold
            42: "XAGUSD",  # Silver  
            43: "BTCUSD", 44: "ETHUSD",  # Crypto
            45: "US30", 46: "SPX500", 47: "NAS100",  # Indices
            48: "CRUDE", 49: "BRENT",  # Oil
        }
        return id_to_symbol.get(symbol_id, f"SYMBOL_{symbol_id}")
    
    def _load_account_data(self, client, account_id, account_type):
        """Load all necessary data for pip value calculation"""
        try:
            logger.info(f"[DATA-LOAD] Loading {account_type} account data for pip calculations...")
            
            # 1. Get trader info (for deposit currency)
            trader_req = ProtoOATraderReq()
            trader_req.ctidTraderAccountId = account_id
            
            deferred_trader = client.send(trader_req)
            deferred_trader.addCallback(lambda response: self._handle_trader_info(response, account_type))
            deferred_trader.addErrback(self._on_error)
            
            # 2. Get asset list
            asset_req = ProtoOAAssetListReq()
            asset_req.ctidTraderAccountId = account_id
            
            deferred_assets = client.send(asset_req)
            deferred_assets.addCallback(lambda response: self._handle_asset_list(response, account_type))
            deferred_assets.addErrback(self._on_error)
            
            # 3. Get symbol information for common trading symbols
            symbol_ids = [1, 2, 3, 4, 5, 6, 7, 41, 42]  # Major pairs + Gold/Silver
            symbol_req = ProtoOASymbolByIdReq()
            symbol_req.ctidTraderAccountId = account_id
            symbol_req.symbolId[:] = symbol_ids
            
            deferred_symbols = client.send(symbol_req)
            deferred_symbols.addCallback(lambda response: self._handle_symbol_list(response, account_type))
            deferred_symbols.addErrback(self._on_error)
            
            logger.info(f"[DATA-LOAD] Data requests sent for {account_type} account")
            
        except Exception as e:
            logger.error(f"Failed to load account data: {e}")
    
    def _handle_trader_info(self, response, account_type):
        """Handle trader information response"""
        try:
            trader_res = Protobuf.extract(response)
            
            if hasattr(trader_res, 'trader') and trader_res.trader:
                trader = trader_res.trader
                deposit_asset_id = getattr(trader, 'depositAssetId', None)
                
                if deposit_asset_id:
                    if account_type == "master":
                        self.master_deposit_asset_id = deposit_asset_id
                    else:
                        self.slave_deposit_asset_id = deposit_asset_id
                    
                    logger.info(f"[DATA-LOAD] {account_type.upper()} deposit asset ID: {deposit_asset_id}")
                else:
                    logger.warning(f"[DATA-LOAD] No deposit asset ID found for {account_type}")
            else:
                logger.warning(f"[DATA-LOAD] No trader data in response for {account_type}")
                
        except Exception as e:
            logger.error(f"Failed to handle trader info: {e}")
    
    def _handle_asset_list(self, response, account_type):
        """Handle asset list response"""
        try:
            asset_res = Protobuf.extract(response)
            
            if hasattr(asset_res, 'asset') and asset_res.asset:
                assets = asset_res.asset
                asset_dict = self.master_assets if account_type == "master" else self.slave_assets
                
                for asset in assets:
                    asset_data = AssetData(
                        asset_id=asset.assetId,
                        name=asset.name,
                        digits=getattr(asset, 'digits', 2)
                    )
                    asset_dict[asset.assetId] = asset_data
                
                logger.info(f"[DATA-LOAD] Loaded {len(assets)} assets for {account_type}")
                
                # Check if data loading is complete
                self._check_data_loading_complete(account_type)
            else:
                logger.warning(f"[DATA-LOAD] No asset data in response for {account_type}")
                
        except Exception as e:
            logger.error(f"Failed to handle asset list: {e}")
    
    def _handle_symbol_list(self, response, account_type):
        """Handle symbol list response"""
        try:
            symbol_res = Protobuf.extract(response)
            
            if hasattr(symbol_res, 'symbol') and symbol_res.symbol:
                symbols = symbol_res.symbol
                symbol_dict = self.master_symbols if account_type == "master" else self.slave_symbols
                
                for symbol in symbols:
                    symbol_data = SymbolData(
                        symbol_id=symbol.symbolId,
                        symbol_name=self._get_symbol_name(symbol.symbolId),
                        digits=symbol.digits,
                        pip_position=symbol.pipPosition,
                        lot_size=getattr(symbol, 'lotSize', 100000),
                        base_asset_id=getattr(symbol, 'baseAssetId', 0),
                        quote_asset_id=getattr(symbol, 'quoteAssetId', 0),
                        volume_step=getattr(symbol, 'stepVolume', getattr(symbol, 'volumeStep', 100))
                    )
                    symbol_dict[symbol.symbolId] = symbol_data
                
                logger.info(f"[DATA-LOAD] Loaded {len(symbols)} symbols for {account_type}")
                
                # Subscribe to spot events for these symbols to get current prices
                self._subscribe_to_spots(account_type, list(symbol_dict.keys()))
                
                # Check if data loading is complete
                self._check_data_loading_complete(account_type)
            else:
                logger.warning(f"[DATA-LOAD] No symbol data in response for {account_type}")
                
        except Exception as e:
            logger.error(f"Failed to handle symbol list: {e}")
    
    def _subscribe_to_spots(self, account_type, symbol_ids):
        """Subscribe to spot events for price updates"""
        try:
            account_id = self.master_config.account_id if account_type == "master" else self.slave_config.account_id
            
            subscribe_req = ProtoOASubscribeSpotsReq()
            subscribe_req.ctidTraderAccountId = account_id
            subscribe_req.symbolId[:] = symbol_ids
            
            deferred = self.client.send(subscribe_req)
            deferred.addErrback(self._on_error)
            
            logger.info(f"[DATA-LOAD] Subscribed to spot events for {len(symbol_ids)} symbols ({account_type})")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to spots: {e}")
    
    def _handle_spot_event(self, client, message):
        """Handle spot event (price updates)"""
        try:
            spot_event = Protobuf.extract(message)
            symbol_id = spot_event.symbolId
            account_id = spot_event.ctidTraderAccountId
            
            # Determine which account this is for
            if account_id == self.master_config.account_id:
                symbol_dict = self.master_symbols
                account_type = "master"
            elif account_id == self.slave_config.account_id:
                symbol_dict = self.slave_symbols
                account_type = "slave"
            else:
                return  # Unknown account
            
            # Update symbol prices
            if symbol_id in symbol_dict:
                symbol_data = symbol_dict[symbol_id]
                
                if hasattr(spot_event, 'bid') and spot_event.bid:
                    symbol_data.current_bid = self._convert_relative_price(spot_event.bid, symbol_data)
                
                if hasattr(spot_event, 'ask') and spot_event.ask:
                    symbol_data.current_ask = self._convert_relative_price(spot_event.ask, symbol_data)
                
                # Only log occasionally to avoid spam
                if symbol_id == 1:  # Only log EURUSD updates
                    logger.debug(f"[PRICE] {account_type.upper()} {symbol_data.symbol_name}: Bid={symbol_data.current_bid:.5f}, Ask={symbol_data.current_ask:.5f}")
                
        except Exception as e:
            logger.error(f"Failed to handle spot event: {e}")
    
    def _convert_relative_price(self, relative_price, symbol_data):
        """Convert relative price to actual price"""
        try:
            # The relative price needs to be divided by 10^digits
            return float(relative_price) / (10 ** symbol_data.digits)
        except:
            return 0.0
    
    def _check_data_loading_complete(self, account_type):
        """Check if all necessary data has been loaded"""
        try:
            if account_type == "master":
                has_deposit_asset = self.master_deposit_asset_id is not None
                has_assets = len(self.master_assets) > 0
                has_symbols = len(self.master_symbols) > 0
                
                if has_deposit_asset and has_assets and has_symbols:
                    self.master_data_loaded = True
                    logger.info(f"[DATA-LOAD] Master account data loading complete")
            else:
                has_deposit_asset = self.slave_deposit_asset_id is not None
                has_assets = len(self.slave_assets) > 0
                has_symbols = len(self.slave_symbols) > 0
                
                if has_deposit_asset and has_assets and has_symbols:
                    self.slave_data_loaded = True
                    logger.info(f"[DATA-LOAD] Slave account data loading complete")
            
            # Check if both accounts are ready for pip calculations
            if self.master_data_loaded and self.slave_data_loaded:
                logger.info(f"[DATA-LOAD] All account data loaded - pip calculations ready!")
                
        except Exception as e:
            logger.error(f"Error checking data loading status: {e}")
    
    def _calculate_pip_value(self, symbol_id, account_type):
        """Calculate pip value for a symbol on a specific account"""
        try:
            logger.debug(f"[PIP-CALC] Starting pip calculation for symbol {symbol_id} on {account_type}")
            
            # Get the appropriate data dictionaries
            if account_type == "master":
                symbol_dict = self.master_symbols
                asset_dict = self.master_assets
                deposit_asset_id = self.master_deposit_asset_id
            else:
                symbol_dict = self.slave_symbols
                asset_dict = self.slave_assets
                deposit_asset_id = self.slave_deposit_asset_id
            
            logger.debug(f"[PIP-CALC] {account_type}: symbols={len(symbol_dict)}, assets={len(asset_dict)}, deposit_asset_id={deposit_asset_id}")
            
            # Validate prerequisites
            if symbol_id not in symbol_dict:
                logger.warning(f"[PIP-CALC] Symbol {symbol_id} not found in {account_type} symbols (available: {list(symbol_dict.keys())})")
                return None
            
            if not deposit_asset_id or deposit_asset_id not in asset_dict:
                logger.warning(f"[PIP-CALC] Deposit asset {deposit_asset_id} not found for {account_type} (available: {list(asset_dict.keys())})")
                return None
            
            symbol_data = symbol_dict[symbol_id]
            deposit_asset = asset_dict[deposit_asset_id]
            
            # Ensure quote asset exists in dictionary, if not assume same as deposit
            if symbol_data.quote_asset_id in asset_dict:
                quote_asset = asset_dict[symbol_data.quote_asset_id]
            else:
                logger.warning(f"[PIP-CALC] Quote asset {symbol_data.quote_asset_id} not found for {symbol_data.symbol_name} – assuming same as deposit currency")
                quote_asset = deposit_asset
            
            # Calculate pip size (distance of one pip in price terms)
            pip_size = 1.0 / (10 ** symbol_data.pip_position)
            
            # CASE 1: Quote currency is the SAME as deposit currency -> price not required
            if quote_asset.asset_id == deposit_asset.asset_id:
                pip_value_per_unit = pip_size  # 1 unit of base results in pip_size change in deposit currency
                pip_value = pip_value_per_unit * symbol_data.lot_size
                logger.debug(f"[PIP-CALC] Same currency. pip_size={pip_size}, lot_size={symbol_data.lot_size}")
                logger.info(f"[PIP-CALC] {account_type.upper()} {symbol_data.symbol_name}: Pip value = ${pip_value:.5f} per lot (no price conversion)")
                return pip_value
            
            # CASE 2: Different currencies – require current prices for conversion
            logger.debug(f"[PIP-CALC] Different currency – requires price conversion")
            logger.debug(f"[PIP-CALC] {account_type} {symbol_data.symbol_name}: bid={symbol_data.current_bid}, ask={symbol_data.current_ask}")
            
            if symbol_data.current_bid == 0.0 or symbol_data.current_ask == 0.0:
                logger.warning(f"[PIP-CALC] No current prices for {symbol_data.symbol_name} on {account_type} – cannot convert")
                return None
            
            mid_price = (symbol_data.current_bid + symbol_data.current_ask) / 2.0
            
            # For FX pairs where deposit is NOT quote currency, convert: pip_value = pip_size / mid_price * lot_size
            # This is an approximation. For metals/CFDs conversion may differ, but mid_price gives reasonable risk equivalence.
            pip_value_per_unit = pip_size / mid_price
            pip_value = pip_value_per_unit * symbol_data.lot_size
            
            logger.info(f"[PIP-CALC] {account_type.upper()} {symbol_data.symbol_name}: Pip value = ${pip_value:.5f} per lot (via price conversion)")
            logger.debug(f"[PIP-CALC] Details: pip_size={pip_size}, mid_price={mid_price:.5f}, lot_size={symbol_data.lot_size}")
            return pip_value
            
        except Exception as e:
            logger.error(f"Error calculating pip value: {e}")
            return None
    
    def _on_error(self, failure):
        """Handle errors"""
        logger.error(f"API Error: {failure}")
    
    def stop(self):
        """Stop the trade copier"""
        logger.info("Stopping trade copier...")
        
        if self.client:
            self.client.disconnect()
        
        if reactor.running:
            reactor.stop()
        
        logger.info("Trade copier stopped")

def main():
    """Main function"""
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
    
    copier = SingleConnectionTradeCopier(master_config, slave_config)
    
    try:
        copier.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        copier.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        copier.stop()

if __name__ == "__main__":
    print("cTrader to cTrader Trade Copier - Single Connection")
    print("=" * 55)
    print("Following cTrader API best practice: One connection per environment")
    print("=" * 55)
    
    main() 