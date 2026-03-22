#!/usr/bin/env python3
"""
Test PUT /api/modify with DYNAMIC prices based on current market
- Fetches current LCX/USDC price from GET /api/ticker
- Creates BUY order at current_price × 0.90 (10% below)
- Creates SELL order at current_price × 1.10 (10% above)
- Modifies orders 45% towards the constraints (0.0225 min, 0.0657 max)
- Amount: 20 → 30
"""

import requests
import json
import hmac
import hashlib
import base64
import time
import sys
import os

if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')

class Colors:
    PASS = '\033[92m'
    FAIL = '\033[91m'
    WARN = '\033[93m'
    INFO = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def create_signature(method, endpoint, payload=None):
    """Generate HMAC-SHA256 signature"""
    if payload is None:
        payload = {}
    timestamp = str(int(time.time() * 1000))
    request_string = method + endpoint + json.dumps(payload)
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode(),
            request_string.encode(),
            hashlib.sha256
        ).digest()
    ).decode()
    return signature, timestamp

def get_headers(method, endpoint, payload=None):
    """Get authenticated headers"""
    signature, timestamp = create_signature(method, endpoint, payload)
    return {
        'Content-Type': 'application/json',
        'API-VERSION': '1.1.0',
        'x-access-key': api_key,
        'x-access-sign': signature,
        'x-access-timestamp': timestamp
    }

def test_step(name, success):
    """Print test step result"""
    status = f"{Colors.PASS}✅ PASS{Colors.RESET}" if success else f"{Colors.FAIL}❌ FAIL{Colors.RESET}"
    print(f"{status} - {name}\n")

# ===== CONFIGURATION =====
import argparse
parser = argparse.ArgumentParser(description='Test modify with DYNAMIC prices')
parser.add_argument('--api-key', required=True, help='API Key')
parser.add_argument('--api-secret', required=True, help='API Secret')
args = parser.parse_args()

api_key = args.api_key
api_secret = args.api_secret
base_url = "https://exchange-api.lcx.com"

print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
print(f"{Colors.BOLD}Test: Dynamic Order Modification (Market-Based Prices){Colors.RESET}")
print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

# ========== STEP 0: FETCH CURRENT PRICE ==========
print(f"{Colors.INFO}Step 0: Fetch current LCX/USDC price{Colors.RESET}\n")

current_price = None
try:
    response = requests.get(
        base_url + "/api/ticker",
        params={"pair": "LCX/USDC"},
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()['data']
        current_price = float(data['lastPrice'])
        print(f"✅ Current market price: {current_price} USDC")
        print(f"   Bid: {data['bestBid']}")
        print(f"   Ask: {data['bestAsk']}\n")
    else:
        print(f"❌ Failed to fetch price: {response.status_code}\n")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error fetching price: {e}\n")
    sys.exit(1)

# Calculate dynamic prices
buy_price = round(current_price * 0.90, 4)      # 10% below current
sell_price = round(current_price * 1.10, 4)     # 10% above current

# Calculate modify prices (45% towards limits)
# BUY modify: move 45% from buy_price towards minimum (0.0225)
buy_modify_distance = buy_price - 0.0225
buy_modify_price = round(buy_price - (buy_modify_distance * 0.45), 4)

# SELL modify: move 45% from sell_price towards maximum (0.0657)
sell_modify_distance = 0.0657 - sell_price
sell_modify_price = round(sell_price + (sell_modify_distance * 0.45), 4)

print(f"{Colors.INFO}Calculated prices (based on {current_price} USDC):{Colors.RESET}")
print(f"  BUY Create:  {buy_price} (current × 0.90)")
print(f"  BUY Modify:  {buy_modify_price} (45% towards 0.0225 min)")
print(f"  SELL Create: {sell_price} (current × 1.10)")
print(f"  SELL Modify: {sell_modify_price} (45% towards 0.0657 max)\n")

# ========== TRANSACTION 1: BUY ORDER ==========
print(f"\n{Colors.BOLD}TRANSACTION 1: BUY ORDER{Colors.RESET}")
print(f"{Colors.INFO}Step 1.1: Create BUY order (20 LCX @ {buy_price} USDC){Colors.RESET}")
print(f"  Creating: BUY 20 LCX/USDC @ {buy_price}\n")

buy_create_payload = {
    "Pair": "LCX/USDC",
    "Amount": 20,
    "Price": buy_price,
    "OrderType": "LIMIT",
    "Side": "BUY"
}

buy_order_id = None
try:
    headers = get_headers("POST", "/api/create", buy_create_payload)
    response = requests.post(base_url + "/api/create", json=buy_create_payload, headers=headers, timeout=10)

    if response.status_code in [200, 201]:
        order_data = response.json()['data']
        buy_order_id = order_data['Id']
        print(f"✅ BUY Order created")
        print(f"   OrderId: {buy_order_id}")
        print(f"   Amount: {order_data['Amount']}")
        print(f"   Price: {order_data['Price']}\n")
        test_step("POST /api/create (BUY)", True)
    else:
        print(f"❌ Failed to create BUY order")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.text}\n")
        test_step("POST /api/create (BUY)", False)
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}\n")
    test_step("POST /api/create (BUY)", False)
    sys.exit(1)

print(f"⏱️  Waiting 3 seconds before modify...\n")
time.sleep(3)

# ========== MODIFY BUY ORDER ==========
print(f"{Colors.INFO}Step 1.2: Modify BUY order (30 LCX @ {buy_modify_price} USDC){Colors.RESET}")
print(f"  Changing: Amount 20 → 30, Price {buy_price} → {buy_modify_price}\n")

buy_modify_payload = {
    "OrderId": buy_order_id,
    "Amount": 30,
    "Price": buy_modify_price
}

try:
    headers = get_headers("PUT", "/api/modify", buy_modify_payload)
    response = requests.put(base_url + "/api/modify", json=buy_modify_payload, headers=headers, timeout=10)

    if response.status_code == 200:
        modified_data = response.json()['data']
        print(f"✅ BUY Order modified successfully!")
        print(f"   OrderId: {modified_data['Id']}")
        print(f"   New Amount: {modified_data['Amount']}")
        print(f"   New Price: {modified_data['Price']}\n")
        test_step("PUT /api/modify (BUY)", True)
    else:
        print(f"❌ Failed to modify BUY order")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.text}\n")
        test_step("PUT /api/modify (BUY)", False)
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}\n")
    test_step("PUT /api/modify (BUY)", False)
    sys.exit(1)

# ========== TRANSACTION 2: SELL ORDER ==========
print(f"\n{Colors.BOLD}TRANSACTION 2: SELL ORDER{Colors.RESET}")
print(f"{Colors.INFO}Step 2.1: Create SELL order (20 LCX @ {sell_price} USDC){Colors.RESET}")
print(f"  Creating: SELL 20 LCX/USDC @ {sell_price}\n")

sell_create_payload = {
    "Pair": "LCX/USDC",
    "Amount": 20,
    "Price": sell_price,
    "OrderType": "LIMIT",
    "Side": "SELL"
}

sell_order_id = None
try:
    headers = get_headers("POST", "/api/create", sell_create_payload)
    response = requests.post(base_url + "/api/create", json=sell_create_payload, headers=headers, timeout=10)

    if response.status_code in [200, 201]:
        order_data = response.json()['data']
        sell_order_id = order_data['Id']
        print(f"✅ SELL Order created")
        print(f"   OrderId: {sell_order_id}")
        print(f"   Amount: {order_data['Amount']}")
        print(f"   Price: {order_data['Price']}\n")
        test_step("POST /api/create (SELL)", True)
    else:
        print(f"❌ Failed to create SELL order")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.text}\n")
        test_step("POST /api/create (SELL)", False)
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}\n")
    test_step("POST /api/create (SELL)", False)
    sys.exit(1)

print(f"⏱️  Waiting 3 seconds before modify...\n")
time.sleep(3)

# ========== MODIFY SELL ORDER ==========
print(f"{Colors.INFO}Step 2.2: Modify SELL order (30 LCX @ {sell_modify_price} USDC){Colors.RESET}")
print(f"  Changing: Amount 20 → 30, Price {sell_price} → {sell_modify_price}\n")

sell_modify_payload = {
    "OrderId": sell_order_id,
    "Amount": 30,
    "Price": sell_modify_price
}

try:
    headers = get_headers("PUT", "/api/modify", sell_modify_payload)
    response = requests.put(base_url + "/api/modify", json=sell_modify_payload, headers=headers, timeout=10)

    if response.status_code == 200:
        modified_data = response.json()['data']
        print(f"✅ SELL Order modified successfully!")
        print(f"   OrderId: {modified_data['Id']}")
        print(f"   New Amount: {modified_data['Amount']}")
        print(f"   New Price: {modified_data['Price']}\n")
        test_step("PUT /api/modify (SELL)", True)
    else:
        print(f"❌ Failed to modify SELL order")
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.text}\n")
        test_step("PUT /api/modify (SELL)", False)
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}\n")
    test_step("PUT /api/modify (SELL)", False)
    sys.exit(1)

# ========== SUMMARY ==========
print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
print(f"{Colors.PASS}{Colors.BOLD}✅ ALL TESTS PASSED (4/4 Transactions){Colors.RESET}")
print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
print(f"Market Price: {current_price} USDC\n")
print(f"Transactions completed:")
print(f"  1. ✅ BUY Create:  20 LCX @ {buy_price} (-10% from current)")
print(f"  2. ✅ BUY Modify:  30 LCX @ {buy_modify_price} (45% towards 0.0225)")
print(f"  3. ✅ SELL Create: 20 LCX @ {sell_price} (+10% from current)")
print(f"  4. ✅ SELL Modify: 30 LCX @ {sell_modify_price} (45% towards 0.0657)")
print(f"\nKey: All prices calculated dynamically based on current market!\n")
