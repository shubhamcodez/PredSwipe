from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import KalshiHttpClient, Environment

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def create_client(api_key, private_key_pem):
    """Helper function to create a Kalshi client from API keys."""
    # Load the private key from PEM format
    private_key_str = private_key_pem.strip()
    
    # Handle case where everything might be on one line
    if '-----BEGIN' in private_key_str and '-----END' in private_key_str:
        # Extract the content between the headers
        parts = private_key_str.split('-----')
        if len(parts) >= 4:
            header = f"-----{parts[1]}-----"
            content = parts[2].strip()
            
            # Remove any extra whitespace/newlines from content
            content = content.replace('\n', '').replace(' ', '').replace('\\n', '')
            
            # Reformat with proper line breaks (every 64 characters)
            key_lines = [content[i:i+64] for i in range(0, len(content), 64)]
            key_content_formatted = '\n'.join(key_lines)
            
            private_key_str = f"{header}\n{key_content_formatted}\n-----END{parts[1].replace('BEGIN', '')}-----"
    
    # Try to load the private key
    try:
        private_key = load_pem_private_key(private_key_str.encode(), password=None)
    except Exception as e:
        # Try with PKCS#8 format instead
        if 'RSA PRIVATE KEY' in private_key_str:
            private_key_str = private_key_str.replace('RSA PRIVATE KEY', 'PRIVATE KEY')
            private_key = load_pem_private_key(private_key_str.encode(), password=None)
        else:
            raise e
    
    # Create Kalshi client
    return KalshiHttpClient(
        key_id=api_key,
        private_key=private_key,
        environment=Environment.PROD
    )

@app.route('/api/balance', methods=['POST'])
def get_balance():
    """Get user balance from Kalshi API."""
    try:
        data = request.json
        api_key = data.get('kalshiApiKey')
        private_key_pem = data.get('kalshiPrivateKey')
        
        if not api_key or not private_key_pem:
            return jsonify({'error': 'API key and private key are required'}), 400
        
        client = create_client(api_key, private_key_pem)
        balance_response = client.get_balance()
        
        return jsonify(balance_response), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/markets', methods=['POST'])
def get_markets():
    """Get markets from Kalshi API by series ticker."""
    try:
        data = request.json
        api_key = data.get('kalshiApiKey')
        private_key_pem = data.get('kalshiPrivateKey')
        series_ticker = data.get('series_ticker', 'KXNBAGAME')
        limit = data.get('limit', 100)
        
        if not api_key or not private_key_pem:
            return jsonify({'error': 'API key and private key are required'}), 400
        
        client = create_client(api_key, private_key_pem)
        
        # Get markets
        markets_response = client.get(
            client.markets_url,
            params={'limit': limit, 'series_ticker': series_ticker}
        )
        
        return jsonify(markets_response), 200
        
    except Exception as e:
        print(f"Error fetching markets: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/place_order', methods=['POST'])
def place_order():
    """Place a market or limit order on Kalshi API."""
    try:
        data = request.json
        api_key = data.get('kalshiApiKey')
        private_key_pem = data.get('kalshiPrivateKey')
        ticker = data.get('ticker')
        side = data.get('side')  # 'yes' or 'no'
        count = data.get('count', 1)
        order_mode = data.get('order_mode', 'market')  # 'market' or 'limit'
        
        if not api_key or not private_key_pem:
            return jsonify({'error': 'API key and private key are required'}), 400
        
        if not ticker or not side:
            return jsonify({'error': 'Ticker and side are required'}), 400
        
        if side not in ['yes', 'no']:
            return jsonify({'error': 'Side must be "yes" or "no"'}), 400
        
        client = create_client(api_key, private_key_pem)
        
        # Always use limit orders (with IOC for market-like execution)
        # Get current market price from orderbook
        market_data = client.get_market_orderbook(ticker)
        
        # Debug: print the full orderbook structure
        print(f"Full orderbook data: {market_data}")
        
        # Extract bid prices from orderbook arrays
        orderbook = market_data.get('orderbook', {})
        
        if side == 'yes':
            # YES bids are in the 'yes' array, format: [[price, quantity], ...]
            # YES ask is calculated as 100 - highest NO bid
            yes_bids = orderbook.get('yes', [])
            no_bids = orderbook.get('no', [])
            
            if not yes_bids or len(yes_bids) == 0:
                return jsonify({'error': 'No YES bids available in orderbook'}), 400
            if not no_bids or len(no_bids) == 0:
                return jsonify({'error': 'No NO bids available in orderbook'}), 400
            
            # Get the best (highest) YES bid - find maximum price in array
            yes_bid = max(bid[0] for bid in yes_bids) if yes_bids else 0
            # Get the best (highest) NO bid to calculate YES ask
            no_bid = max(bid[0] for bid in no_bids) if no_bids else 0
            yes_ask = 100 - no_bid
            
            # To buy YES immediately with IOC, use the ask price (what sellers want)
            market_price = yes_ask
            
            print(f"YES market - Bid: {yes_bid}¢, Ask: {yes_ask}¢ (calculated from NO bid: {no_bid}¢)")
        else:
            # NO bids are in the 'no' array
            # NO ask is calculated as 100 - highest YES bid
            no_bids = orderbook.get('no', [])
            yes_bids = orderbook.get('yes', [])
            
            if not no_bids or len(no_bids) == 0:
                return jsonify({'error': 'No NO bids available in orderbook'}), 400
            if not yes_bids or len(yes_bids) == 0:
                return jsonify({'error': 'No YES bids available in orderbook'}), 400
            
            # Get the best (highest) NO bid - find maximum price in array
            no_bid = max(bid[0] for bid in no_bids) if no_bids else 0
            # Get the best (highest) YES bid to calculate NO ask
            yes_bid = max(bid[0] for bid in yes_bids) if yes_bids else 0
            no_ask = 100 - yes_bid
            
            # To buy NO immediately with IOC, use the ask price (what sellers want)
            market_price = no_ask
            
            print(f"NO market - Bid: {no_bid}¢, Ask: {no_ask}¢ (calculated from YES bid: {yes_bid}¢)")
        
        print(f"Placing LIMIT {side} order at {market_price} cents")
        
        order_response = client.place_order(
            ticker=ticker,
            side=side,
            action='buy',
            count=count,
            order_type='limit',
            price_cents=market_price,
            time_in_force='IOC'
        )
        
        return jsonify(order_response), 200
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error placing order: {str(e)}")
        print(f"Full traceback:\n{error_trace}")
        return jsonify({'error': str(e), 'traceback': error_trace}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
