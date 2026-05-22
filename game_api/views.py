# game_api/views.py - FULL REPLACEMENT
import random
import string
import json
from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .models import GameReward, Wallet, Transaction, PaymentGatewayLog
from .utils import PhonePePaymentGateway, NextPayPaymentGateway

# ========== PAGE VIEWS ==========

def signup_page(request):
    return render(request, 'signup.html')

def login_page(request):
    return render(request, 'login.html')

def mine_page(request):
    if not request.user.is_authenticated:
        return redirect('/login/')
    
    return render(request, 'mine.html', {
        "user_name": request.user.username,
        "user_id": request.user.last_name
    })

@login_required
def account_page(request):
    user = request.user
    
    # Get or create wallet
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    total_wins = GameReward.objects.filter(user=user, status='CLAIMED').count()
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:50]
    
    # Calculate totals
    total_deposit = sum(t.amount for t in transactions if t.transaction_type == 'DEPOSIT' and t.status == 'COMPLETED')
    total_withdraw = sum(t.amount for t in transactions if t.transaction_type == 'WITHDRAW' and t.status == 'COMPLETED')
    
    context = {
        "user_name": user.username,
        "user_id": user.last_name,
        "user_email": user.email,
        "joined_date": user.date_joined.strftime("%d %B, %Y"),
        "total_wins": total_wins,
        "wallet_balance": wallet.balance,
        "transactions": transactions,
        "total_deposit": total_deposit,
        "total_withdraw": total_withdraw,
    }
    return render(request, 'account.html', context)

@login_required
def history_view(request):
    user_history = GameReward.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'history.html', {'history': user_history})

def logout_user(request):
    logout(request)
    return redirect('/login/')


# ========== AUTH APIS ==========

@csrf_exempt
def signup_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            u_name = data.get('username')
            u_email = data.get('email')
            u_pass = data.get('password')
            u_id = data.get('user_id')
            
            if User.objects.filter(email__iexact=u_email).exists():
                return JsonResponse({"status": "error", "message": "Email already exists!"})
            
            if User.objects.filter(username=u_name).exists():
                return JsonResponse({"status": "error", "message": "Username already taken!"})
            
            user = User.objects.create_user(
                username=u_name, 
                email=u_email, 
                password=u_pass,
                last_name=u_id
            )
            user.save()
            
            # Auto create wallet for new user
            Wallet.objects.create(user=user, balance=0)
            
            return JsonResponse({"status": "success", "message": "Account created successfully!"})
            
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

@csrf_exempt
def login_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({
                "status": "success", 
                "username": user.username,
                "unique_id": user.last_name
            })
        else:
            return JsonResponse({"status": "error", "message": "Invalid Username or Password!"})


# ========== FORGOT PASSWORD APIS ==========

@csrf_exempt
def check_email_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get('email')
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            return JsonResponse({"status": "success", "token": token})
        except User.DoesNotExist:
            return JsonResponse({"status": "error", "message": "User not found"})

@csrf_exempt
def update_password_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            token = data.get('token')
            new_pass = data.get('new_password')
            
            for user in User.objects.all():
                if default_token_generator.check_token(user, token):
                    user.set_password(new_pass)
                    user.save()
                    return JsonResponse({"status": "success", "message": "Password updated successfully!"})
            
            return JsonResponse({"status": "error", "message": "Invalid or Expired Token!"})
            
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})


# ========== PAYMENT GATEWAY - DEPOSIT (PhonePe/NextPay) ==========

@login_required
def initiate_deposit(request):
    """Step 1: User initiates deposit - Create payment request via Gateway"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = float(data.get('amount', 0))
            gateway = data.get('gateway', 'phonepe')  # 'phonepe' or 'nextpay'
            
            if amount < 10:
                return JsonResponse({'status': 'error', 'message': 'Minimum deposit is ₹10'})
            
            if amount > 50000:
                return JsonResponse({'status': 'error', 'message': 'Maximum deposit is ₹50,000'})
            
            # Create transaction record with PENDING status
            transaction = Transaction.objects.create(
                user=request.user,
                transaction_type='DEPOSIT',
                amount=amount,
                status='PENDING',
                description=f"Deposit of ₹{amount} via {gateway}"
            )
            
            # Call appropriate gateway
            if gateway == 'phonepe':
                # Get user phone (you need to add phone field to User model or ask user)
                user_phone = data.get('phone', '9999999999')
                
                result = PhonePePaymentGateway.initiate_payment(
                    merchant_transaction_id=transaction.transaction_id,
                    amount=amount,
                    user_email=request.user.email,
                    user_phone=user_phone
                )
                
                if result['status'] == 'success':
                    return JsonResponse({
                        'status': 'success',
                        'payment_url': result['payment_url'],
                        'transaction_id': transaction.transaction_id,
                        'gateway': 'phonep'
                    })
                else:
                    transaction.status = 'FAILED'
                    transaction.save()
                    return JsonResponse({'status': 'error', 'message': result['message']})
                    
            elif gateway == 'nextpay':
                callback_url = request.build_absolute_uri('/payment/callback/')
                
                result = NextPayPaymentGateway.initiate_payment(
                    transaction_id=transaction.transaction_id,
                    amount=amount,
                    user_email=request.user.email,
                    user_name=request.user.username,
                    callback_url=callback_url
                )
                
                if result['status'] == 'success':
                    return JsonResponse({
                        'status': 'success',
                        'payment_url': result['payment_url'],
                        'transaction_id': transaction.transaction_id,
                        'gateway': 'nextpay'
                    })
                else:
                    transaction.status = 'FAILED'
                    transaction.save()
                    return JsonResponse({'status': 'error', 'message': result['message']})
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid gateway'})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@csrf_exempt
def payment_callback(request):
    """Gateway redirects user back to website after payment"""
    transaction_id = request.GET.get('order_id') or request.GET.get('transaction_id')
    trans_id = request.GET.get('trans_id')  # For NextPay
    
    if not transaction_id:
        return redirect('/payment/failed/')
    
    try:
        transaction = Transaction.objects.get(transaction_id=transaction_id)
        
        # Check status from gateway
        if trans_id:  # NextPay callback
            result = NextPayPaymentGateway.verify_payment(
                trans_id=trans_id,
                amount=float(transaction.amount),
                order_id=transaction_id
            )
            
            if result['status'] == 'SUCCESS':
                # Update wallet
                wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                wallet.add_balance(transaction.amount)
                
                transaction.status = 'COMPLETED'
                transaction.save()
                
                return redirect(f'/payment/success/?amount={transaction.amount}')
            else:
                transaction.status = 'FAILED'
                transaction.save()
                return redirect('/payment/failed/')
                
        else:  # PhonePe callback
            result = PhonePePaymentGateway.check_payment_status(transaction_id)
            
            if result['status'] == 'SUCCESS':
                wallet, created = Wallet.objects.get_or_create(user=transaction.user)
                wallet.add_balance(transaction.amount)
                
                transaction.status = 'COMPLETED'
                transaction.save()
                
                return redirect(f'/payment/success/?amount={transaction.amount}')
            else:
                transaction.status = 'FAILED'
                transaction.save()
                return redirect('/payment/failed/')
                
    except Transaction.DoesNotExist:
        return redirect('/payment/failed/')
    except Exception as e:
        print(f"Callback error: {e}")
        return redirect('/payment/failed/')


@csrf_exempt
@require_http_methods(["POST"])
def payment_webhook(request):
    """Gateway webhook for automatic balance update (Background)"""
    try:
        # Get payload
        payload = json.loads(request.body)
        
        transaction_id = payload.get('order_id') or payload.get('merchantTransactionId')
        gateway_status = payload.get('status') or payload.get('code')
        
        if not transaction_id:
            return JsonResponse({'status': 'error', 'message': 'No transaction ID'})
        
        transaction = Transaction.objects.get(transaction_id=transaction_id)
        
        # Check if already processed
        if transaction.status == 'COMPLETED':
            return JsonResponse({'status': 'success', 'message': 'Already processed'})
        
        # Determine success
        is_success = False
        if gateway_status == 'SUCCESS' or gateway_status == 0 or gateway_status == -1:
            is_success = True
        
        if is_success:
            # Add balance to wallet
            wallet, created = Wallet.objects.get_or_create(user=transaction.user)
            wallet.add_balance(transaction.amount)
            
            transaction.status = 'COMPLETED'
            transaction.save()
            
            # Save webhook log
            PaymentGatewayLog.objects.create(
                transaction=transaction,
                gateway_transaction_id=payload.get('trans_id', ''),
                gateway_response=json.dumps(payload),
                request_data=json.dumps(payload),
                status='COMPLETED'
            )
            
            return JsonResponse({'status': 'success', 'message': 'Balance updated'})
        else:
            transaction.status = 'FAILED'
            transaction.save()
            return JsonResponse({'status': 'success', 'message': 'Payment failed'})
        
    except Transaction.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
    except Exception as e:
        print(f"Webhook error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ========== WITHDRAWAL SYSTEM (With Admin Panel) ==========

@login_required
def withdraw_money(request):
    """Withdraw request - IMMEDIATE BALANCE DEDUCTION + Admin approval"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = float(data.get('amount', 0))
            upi_id = data.get('upi_id', '').strip()
            
            if not upi_id:
                return JsonResponse({'status': 'error', 'message': 'UPI ID is required'})
            
            if amount < 50:
                return JsonResponse({'status': 'error', 'message': 'Minimum withdrawal is ₹50'})
            
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            
            if wallet.balance < amount:
                return JsonResponse({'status': 'error', 'message': 'Insufficient balance!'})
            
            # IMMEDIATELY DEDUCT from wallet (Hold funds)
            wallet.deduct_balance(amount)
            
            # Create withdrawal transaction with PENDING status
            transaction = Transaction.objects.create(
                user=request.user,
                transaction_type='WITHDRAW',
                amount=amount,
                status='PENDING',
                upi_id=upi_id,
                description=f"Withdrawal request of ₹{amount} to {upi_id}"
            )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Withdrawal request of ₹{amount} submitted for approval! Funds are on hold.',
                'transaction_id': transaction.transaction_id,
                'new_balance': float(wallet.balance)
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@staff_member_required
def admin_withdrawals_panel(request):
    """Admin panel to manage withdrawal requests"""
    # Get all PENDING withdrawal requests
    pending_withdrawals = Transaction.objects.filter(
        transaction_type='WITHDRAW',
        status='PENDING'
    ).order_by('-created_at')
    
    # Get completed withdrawals for history
    completed_withdrawals = Transaction.objects.filter(
        transaction_type='WITHDRAW',
        status='COMPLETED'
    ).order_by('-approved_at')[:50]
    
    # Get rejected withdrawals
    rejected_withdrawals = Transaction.objects.filter(
        transaction_type='WITHDRAW',
        status='FAILED'
    ).order_by('-updated_at')[:50]
    
    context = {
        'pending_withdrawals': pending_withdrawals,
        'completed_withdrawals': completed_withdrawals,
        'rejected_withdrawals': rejected_withdrawals,
        'total_pending': pending_withdrawals.count(),
        'total_completed': Transaction.objects.filter(transaction_type='WITHDRAW', status='COMPLETED').count(),
        'total_amount_pending': sum(float(w.amount) for w in pending_withdrawals)
    }
    
    return render(request, 'admin_withdrawals.html', context)


@staff_member_required
def admin_approve_withdrawal(request, transaction_id):
    """Approve withdrawal request (After MANUAL payment by admin)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            transaction = Transaction.objects.get(
                transaction_id=transaction_id,
                transaction_type='WITHDRAW',
                status='PENDING'
            )
            
            # Update transaction status
            transaction.status = 'COMPLETED'
            transaction.approved_by = request.user
            transaction.approved_at = datetime.now()
            transaction.notes = data.get('notes', 'Withdrawal approved - Payment sent manually')
            transaction.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Withdrawal #{transaction_id} approved successfully'
            })
            
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@staff_member_required
def admin_reject_withdrawal(request, transaction_id):
    """Reject withdrawal and REVERSE funds back to wallet"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            transaction = Transaction.objects.get(
                transaction_id=transaction_id,
                transaction_type='WITHDRAW',
                status='PENDING'
            )
            
            # REVERSE funds (add back to wallet)
            wallet = Wallet.objects.get(user=transaction.user)
            wallet.add_balance(transaction.amount)
            
            # Update transaction
            transaction.status = 'FAILED'
            transaction.approved_by = request.user
            transaction.approved_at = datetime.now()
            transaction.rejection_reason = data.get('reason', 'Withdrawal rejected by admin')
            transaction.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Withdrawal #{transaction_id} rejected. Funds reversed to user wallet.'
            })
            
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ========== GAME APIS ==========

@login_required
def process_game_fee(request):
    """Game start karne se pehle ₹10 deduct"""
    if request.method == 'POST':
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        if wallet.balance >= 10:
            wallet.deduct_balance(10)
            
            Transaction.objects.create(
                user=request.user,
                transaction_type='GAME_FEE',
                amount=10,
                status='COMPLETED',
                description="Game entry fee"
            )
            
            return JsonResponse({
                'status': 'success',
                'balance': float(wallet.balance)
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Insufficient balance! Please deposit money.'
            })
    
    return JsonResponse({'status': 'error'})


@login_required
def save_win_api(request):
    if request.method == "POST":
        user = request.user
        user_uid = user.last_name
        
        # Generate unique win_id
        prefix = str(user_uid)[:4].upper()
        suffix = ''.join(random.choices(string.digits, k=6))
        new_id = f"{prefix}-{suffix}"
        
        # Ensure unique
        while GameReward.objects.filter(win_id=new_id).exists():
            suffix = ''.join(random.choices(string.digits, k=6))
            new_id = f"{prefix}-{suffix}"
        
        reward = GameReward.objects.create(
            user=user, 
            win_id=new_id, 
            status='WIN'
        )
        return JsonResponse({"status": "success", "win_id": new_id})
    return JsonResponse({"status": "error"})


@login_required
def add_win_reward(request, win_id):
    """Win claim karne par ₹50 reward"""
    try:
        reward = GameReward.objects.get(win_id=win_id, user=request.user)
        
        if reward.status == 'WIN':
            reward.status = 'CLAIMED'
            reward.save()
            
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            wallet.add_balance(50)
            
            Transaction.objects.create(
                user=request.user,
                transaction_type='WIN_REWARD',
                amount=50,
                status='COMPLETED',
                description=f"Win reward for {win_id}"
            )
            
            return JsonResponse({
                'status': 'success',
                'balance': float(wallet.balance)
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Reward already claimed'
            })
    except GameReward.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invalid win ID'})


@login_required
def update_status_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        win_id = data.get('win_id')
        action = data.get('action')
        
        try:
            reward = GameReward.objects.get(win_id=win_id, user=request.user)
            if action == 'scratch':
                reward.status = 'SCRATCHED'
            elif action == 'submit':
                reward.status = 'CLAIMED'
            reward.save()
            return JsonResponse({"status": "success"})
        except GameReward.DoesNotExist:
            return JsonResponse({"status": "error", "message": "ID not found!"})
    
    return JsonResponse({"status": "error"})


def payment_success(request):
    """Payment success page"""
    amount = request.GET.get('amount', 0)
    return render(request, 'payment_success.html', {'amount': amount})


def payment_failed(request):
    """Payment failed page"""
    return render(request, 'payment_failed.html')