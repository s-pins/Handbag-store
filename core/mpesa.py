import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from datetime import datetime
import base64
from decouple import config # Import config for environment variables

class MpesaClient:
    def __init__(self):
        # M-Pesa API credentials from environment variables
        self.consumer_key = config('SAF_CONSUMER_KEY')
        self.consumer_secret = config('SAF_CONSUMER_SECRET')
        self.shortcode = config('SAF_BUSINESS_SHORT_CODE')
        self.passkey = config('SAF_PASSKEY')
        self.stk_push_url = config('SAF_STK_PUSH_URL')
        self.callback_url = config('SAF_CALLBACK_URL')

    def get_access_token(self):
        url = config('SAF_AUTH_URL') # URL for generating access token
        response = requests.get(url, auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret))
        if response.status_code != 200:
            print(f"Error from Safaricom: {response.text}")
            return None
        return response.json()['access_token']

    def stk_push(self, phone, amount, account_reference, transaction_desc): # Added account_reference and transaction_desc
        token = self.get_access_token()
        if not token:
            return {"ResponseCode": "1", "CustomerMessage": "Failed to get access token."}

        url = self.stk_push_url
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        # Generate password using the business shortcode, passkey, and timestamp
        password = base64.b64encode((self.shortcode + self.passkey + timestamp).encode()).decode()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerBuyGoodsOnline", # Or CustomerPayBillOnline
            "Amount": int(amount),
            "PartyA": phone, # Customer phone
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference, # Use the dynamic account reference
            "TransactionDesc": transaction_desc # Use the dynamic transaction description
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()