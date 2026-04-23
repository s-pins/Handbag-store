import base64
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

# Credentials from .env
CONSUMER_KEY = ""
CONSUMER_SECRET = ""
SHORTCODE = ""
PASSKEY = ""
AUTH_URL = (
    "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
)
STK_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
CALLBACK_URL = "https://spins.yakalo-eagle.ts.net/stk-callback/"

print("=" * 50)
print("STEP 1: Getting access token...")
print("=" * 50)
auth_response = requests.get(
    AUTH_URL, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)
)
print(f"Status Code: {auth_response.status_code}")
print(f"Response: {auth_response.text}")

if auth_response.status_code != 200:
    print("\n❌ FAILED: Could not get access token. Check consumer key/secret.")
    exit()

token = auth_response.json().get("access_token")
print(f"\n✅ Access Token: {token[:20]}...")

print("\n" + "=" * 50)
print("STEP 2: Initiating STK Push...")
print("=" * 50)

timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
password = base64.b64encode((SHORTCODE + PASSKEY + timestamp).encode()).decode()

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

payload = {
    "BusinessShortCode": SHORTCODE,
    "Password": password,
    "Timestamp": timestamp,
    "TransactionType": "CustomerBuyGoodsOnline",
    "Amount": 1,
    "PartyA": "254708374149",  # Safaricom sandbox test number
    "PartyB": SHORTCODE,
    "PhoneNumber": "254708374149",  # Safaricom sandbox test number
    "CallBackURL": CALLBACK_URL,
    "AccountReference": "TestOrder",
    "TransactionDesc": "Test Payment",
}

print(f"Payload: {payload}")
stk_response = requests.post(STK_URL, json=payload, headers=headers)
print(f"\nStatus Code: {stk_response.status_code}")
print(f"Full Response: {stk_response.text}")

import json

try:
    data = stk_response.json()
    print(f"\nResponseCode: {data.get('ResponseCode')}")
    print(f"ResponseDescription: {data.get('ResponseDescription')}")
    print(f"CustomerMessage: {data.get('CustomerMessage')}")
    print(f"errorCode: {data.get('errorCode')}")
    print(f"errorMessage: {data.get('errorMessage')}")
except:
    pass
