# game_api/utils.py
import json
import hashlib
import base64
import requests
import hmac
import hashlib
from decimal import Decimal
from django.conf import settings
from django.urls import reverse

class PhonePePaymentGateway:
    """PhonePe Business Gateway Integration"""
    
    @staticmethod
    def generate_payload(merchant_transaction_id, amount, user_email, user_phone, callback_url):
        """Generate payload for PhonePe payment request"""
        payload = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "merchantTransactionId": merchant_transaction_id,
            "merchantUserId": str(user_email),
            "amount": int(amount * 100),  # Convert to paise
            "redirectUrl": callback_url,
            "redirectMode": "REDIRECT",
            "callbackUrl": callback_url,
            "mobileNumber": user_phone,
            "paymentInstrument": {
                "type": "PAY_PAGE"
            }
        }
        
        # Convert to base64
        payload_json = json.dumps(payload)
        base64_payload = base64.b64encode(payload_json.encode()).decode()
        
        # Generate checksum
        salt_key = settings.PHONEPE_SALT_KEY
        salt_index = settings.PHONEPE_SALT_INDEX
        
        string_for_hash = base64_payload + "/pg/v1/pay" + salt_key
        sha256_hash = hashlib.sha256(string_for_hash.encode()).hexdigest()
        checksum = sha256_hash + "###" + str(salt_index)
        
        return {
            "request": base64_payload,
            "checksum": checksum
        }
    
    @staticmethod
    def initiate_payment(merchant_transaction_id, amount, user_email, user_phone):
        """Initiate payment with PhonePe"""
        
        callback_url = settings.PHONEPE_REDIRECT_URL
        
        payload_data = PhonePePaymentGateway.generate_payload(
            merchant_transaction_id, amount, user_email, user_phone, callback_url
        )
        
        if settings.PHONEPE_SANDBOX:
            url = "https://api-preprod.phonepe.com/apis/hermes/pg/v1/pay"
        else:
            url = settings.PHONEPE_API_URL
        
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": payload_data['checksum']
        }
        
        response = requests.post(url, json=payload_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return {
                    'status': 'success',
                    'payment_url': result['data']['instrumentResponse']['redirectInfo']['url'],
                    'transaction_id': result['data']['merchantTransactionId']
                }
            else:
                return {
                    'status': 'error',
                    'message': result.get('message', 'Payment initiation failed')
                }
        else:
            return {
                'status': 'error',
                'message': 'Gateway connection failed'
            }
    
    @staticmethod
    def check_payment_status(merchant_transaction_id):
        """Check payment status from PhonePe"""
        
        if settings.PHONEPE_SANDBOX:
            url = f"https://api-preprod.phonepe.com/apis/hermes/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}"
        else:
            url = f"{settings.PHONEPE_STATUS_URL}/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}"
        
        salt_key = settings.PHONEPE_SALT_KEY
        salt_index = settings.PHONEPE_SALT_INDEX
        
        string_for_hash = f"/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}" + salt_key
        sha256_hash = hashlib.sha256(string_for_hash.encode()).hexdigest()
        checksum = sha256_hash + "###" + str(salt_index)
        
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": settings.PHONEPE_MERCHANT_ID
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result['code'] == 'PAYMENT_SUCCESS':
                return {
                    'status': 'SUCCESS',
                    'amount': float(result['data']['amount']) / 100,
                    'transaction_id': result['data']['merchantTransactionId']
                }
            else:
                return {
                    'status': 'FAILED',
                    'message': result.get('message', 'Payment not successful')
                }
        else:
            return {
                'status': 'ERROR',
                'message': 'Status check failed'
            }

class NextPayPaymentGateway:
    """NextPay Payment Gateway Integration"""
    
    @staticmethod
    def initiate_payment(transaction_id, amount, user_email, user_name, callback_url):
        """Initiate payment with NextPay"""
        
        payload = {
            'api_key': settings.NEXTPAY_API_KEY,
            'amount': int(amount),  # Amount in rupees
            'order_id': transaction_id,
            'callback_uri': callback_url,
            'customer_email': user_email,
            'customer_name': user_name,
        }
        
        if settings.NEXTPAY_SANDBOX:
            url = "https://api.sandbox.nextpay.org/v1/payment"
        else:
            url = f"{settings.NEXTPAY_API_URL}/payment"
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get('code') == -1:  # Success
                return {
                    'status': 'success',
                    'payment_url': result.get('payment_url'),
                    'trans_id': result.get('trans_id')
                }
            else:
                return {
                    'status': 'error',
                    'message': result.get('message', 'Payment initiation failed')
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @staticmethod
    def verify_payment(trans_id, amount, order_id):
        """Verify payment with NextPay"""
        
        payload = {
            'api_key': settings.NEXTPAY_API_KEY,
            'trans_id': trans_id,
            'amount': int(amount),
            'order_id': order_id
        }
        
        if settings.NEXTPAY_SANDBOX:
            url = "https://api.sandbox.nextpay.org/v1/payment/verify"
        else:
            url = f"{settings.NEXTPAY_API_URL}/payment/verify"
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get('code') == 0:  # Payment successful
                return {
                    'status': 'SUCCESS',
                    'card_pan': result.get('card_pan', ''),
                    'ref_id': result.get('ref_id', '')
                }
            else:
                return {
                    'status': 'FAILED',
                    'message': result.get('message', 'Verification failed')
                }
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': str(e)
            }