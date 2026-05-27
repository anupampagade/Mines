# game_api/views.py - CLEAN VERSION (No Duplicates)

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

from .models import GameReward, Wallet, Transaction


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
    
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    total_wins = GameReward.objects.filter(user=user, status='CLAIMED').count()
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:50]
    
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


# ========== DEPOSIT SYSTEM (UTR VERIFICATION) ==========

BUSINESS_UPI_ID = "yourbusiness@okhdfcbank"  # CHANGE THIS TO YOUR UPI ID

@login_required
def get_payment_details(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = float(data.get('amount', 0))
            
            if amount < 10:
                return JsonResponse({'status': 'error', 'message': 'Minimum deposit is ₹10'})
            
            if amount > 50000:
                return JsonResponse({'status': 'error', 'message': 'Maximum deposit is ₹50,000'})
            
            transaction = Transaction.objects.create(
                user=request.user,
                transaction_type='DEPOSIT',
                amount=amount,
                status='PENDING',
                description=f"Deposit of ₹{amount} - Waiting for UTR verification"
            )
            
            # Generate QR Code URL using Google Charts API
            upi_id = BUSINESS_UPI_ID
            qr_content = f"pay?pa={upi_id}&am={amount}&cu=INR&pn=MinesGame"
            qr_url = f"https://chart.googleapis.com/chart?cht=qr&chl={qr_content}&chs=200x200"
            
            return JsonResponse({
                'status': 'success',
                'transaction_id': transaction.transaction_id,
                'amount': amount,
                'upi_id': upi_id,
                'qr_code_url': qr_url
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def verify_utr_and_update_balance(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transaction_id = data.get('transaction_id')
            utr_number = data.get('utr_number', '').strip()
            amount = float(data.get('amount', 0))
            
            if not transaction_id:
                return JsonResponse({'status': 'error', 'message': 'Transaction ID required'})
            
            if not utr_number:
                return JsonResponse({'status': 'error', 'message': 'UTR Number is required'})
            
            if len(utr_number) < 8:
                return JsonResponse({'status': 'error', 'message': 'Please enter valid UTR number'})
            
            transaction = Transaction.objects.get(
                transaction_id=transaction_id,
                user=request.user,
                transaction_type='DEPOSIT',
                status='PENDING'
            )
            
            if float(transaction.amount) != amount:
                return JsonResponse({'status': 'error', 'message': 'Amount mismatch!'})
            
            existing_utr = Transaction.objects.filter(utr_number=utr_number).exclude(id=transaction.id)
            if existing_utr.exists():
                return JsonResponse({'status': 'error', 'message': 'This UTR number has already been used!'})
            
            # INSTANT BALANCE UPDATE
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            wallet.add_balance(transaction.amount)
            
            transaction.utr_number = utr_number
            transaction.status = 'COMPLETED'
            transaction.approved_at = datetime.now()
            transaction.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'✅ Payment verified! ₹{transaction.amount} added to your wallet.',
                'new_balance': float(wallet.balance)
            })
            
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ========== WITHDRAWAL SYSTEM ==========

@login_required
def request_withdrawal(request):
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
            
            wallet.deduct_balance(amount)
            
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
                'message': f'Withdrawal request submitted! Funds are on hold. Admin will process soon.',
                'transaction_id': transaction.transaction_id,
                'new_balance': float(wallet.balance)
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ========== ADMIN PANEL ==========

@staff_member_required
def admin_withdrawals_panel(request):
    pending_withdrawals = Transaction.objects.filter(
        transaction_type='WITHDRAW',
        status='PENDING'
    ).order_by('-created_at')
    
    completed_withdrawals = Transaction.objects.filter(
        transaction_type='WITHDRAW',
        status='COMPLETED'
    ).order_by('-approved_at')[:50]
    
    rejected_withdrawals = Transaction.objects.filter(
        transaction_type='WITHDRAW',
        status='FAILED'
    ).order_by('-approved_at')[:50]
    
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
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            transaction = Transaction.objects.get(
                transaction_id=transaction_id,
                transaction_type='WITHDRAW',
                status='PENDING'
            )
            
            transaction.status = 'COMPLETED'
            transaction.approved_by = request.user
            transaction.approved_at = datetime.now()
            transaction.notes = data.get('notes', 'Payment sent manually')
            transaction.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Withdrawal #{transaction_id} approved'
            })
            
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@staff_member_required
def admin_reject_withdrawal(request, transaction_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            transaction = Transaction.objects.get(
                transaction_id=transaction_id,
                transaction_type='WITHDRAW',
                status='PENDING'
            )
            
            wallet = Wallet.objects.get(user=transaction.user)
            wallet.add_balance(transaction.amount)
            
            transaction.status = 'FAILED'
            transaction.approved_by = request.user
            transaction.approved_at = datetime.now()
            transaction.rejection_reason = data.get('reason', 'Rejected by admin')
            transaction.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Withdrawal rejected. ₹{transaction.amount} refunded.'
            })
            
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ========== GAME APIS ==========

@login_required
def process_game_fee(request):
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
        
        prefix = str(user_uid)[:4].upper()
        suffix = ''.join(random.choices(string.digits, k=6))
        new_id = f"{prefix}-{suffix}"
        
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
    amount = request.GET.get('amount', 0)
    return render(request, 'payment_success.html', {'amount': amount})

def payment_failed(request):
    return render(request, 'payment_failed.html')