# game_api/views.py - COMPLETE CLEAN VERSION

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
from django.conf import settings
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
        "user_id": request.user.id
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
        "user_id": user.id,
        "user_email": user.email,
        "joined_date": user.date_joined.strftime("%d %B, %Y"),
        "total_wins": total_wins,
        "wallet_balance": float(wallet.balance),
        "transactions": transactions,
        "total_deposit": float(total_deposit),
        "total_withdraw": float(total_withdraw),
    }
    return render(request, 'account.html', context)

@login_required
def history_view(request):
    user_history = GameReward.objects.filter(user=request.user).order_by('-created_at')
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return render(request, 'history.html', {
        'history': user_history,
        'wallet_balance': float(wallet.balance),
        'user_name': request.user.username,
        'user_id': request.user.id
    })

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
            
            if User.objects.filter(email__iexact=u_email).exists():
                return JsonResponse({"status": "error", "message": "Email already exists!"})
            
            if User.objects.filter(username=u_name).exists():
                return JsonResponse({"status": "error", "message": "Username already taken!"})
            
            user = User.objects.create_user(username=u_name, email=u_email, password=u_pass)
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
            return JsonResponse({"status": "success", "username": user.username, "user_id": user.id})
        else:
            return JsonResponse({"status": "error", "message": "Invalid Username or Password!"})

@csrf_exempt
def check_email_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            if not email:
                return JsonResponse({"status": "error", "message": "Email is required"})
            user_exists = User.objects.filter(email__iexact=email).exists()
            return JsonResponse({"status": "success", "exists": user_exists, "message": "Email found" if user_exists else "Email not registered"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error"})

@csrf_exempt
def update_password_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')
            
            if not email or not new_password:
                return JsonResponse({"status": "error", "message": "Email and password are required"})
            if new_password != confirm_password:
                return JsonResponse({"status": "error", "message": "Passwords do not match"})
            if len(new_password) < 6:
                return JsonResponse({"status": "error", "message": "Password must be at least 6 characters"})
            
            try:
                user = User.objects.get(email__iexact=email)
                user.set_password(new_password)
                user.save()
                return JsonResponse({"status": "success", "message": "Password updated successfully!"})
            except User.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Email not found!"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error"})


# ========== DEPOSIT SYSTEM ==========

BUSINESS_UPI_ID = "yourbusiness@okhdfcbank"

@login_required
def get_payment_details(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = data.get('amount')
            
            # Get UPI ID from settings
            upi_id = settings.BUSINESS_UPI_ID  # "8806261014@ybl"
            
            # Create transaction record
            transaction = Transaction.objects.create(
                user=request.user,
                amount=amount,
                transaction_type='DEPOSIT',
                status='PENDING',
                upi_id=upi_id
            )
            
            # Generate QR code (optional - you can use any QR API)
            qr_code_url = f"https://quickchart.io/qr?text=upi://pay?pa={upi_id}&am={amount}&cu=INR&pn=MinesGame&size=200"
            
            return JsonResponse({
                'status': 'success',
                'transaction_id': transaction.id,
                'upi_id': upi_id,
                'amount': amount,
                'qr_code_url': qr_code_url,
                'message': 'Payment details generated'
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
@login_required
def verify_utr_and_update_balance(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transaction_id = data.get('transaction_id')
            utr_number = data.get('utr_number', '').strip()
            amount = float(data.get('amount', 0))
            
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
            
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            wallet.add_balance(transaction.amount)
            
            transaction.utr_number = utr_number
            transaction.status = 'COMPLETED'
            transaction.approved_at = datetime.now()
            transaction.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'✅ Payment verified! ₹{transaction.amount} added.',
                'new_balance': float(wallet.balance)
            })
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Transaction not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})


# ========== WITHDRAWAL SYSTEM ==========

@login_required
def request_withdrawal_api(request):
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
            
            # FIX: Decimal se compare kar
            from decimal import Decimal
            if wallet.balance < Decimal(str(amount)):
                return JsonResponse({'status': 'error', 'message': 'Insufficient balance!'})
            
            # FIX: deduct_balance method use kar (jo Decimal handle karta hai)
            wallet.deduct_balance(Decimal(str(amount)))
            
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
                'message': 'Withdrawal request submitted! Admin will process soon.',
                'transaction_id': transaction.transaction_id,
                'new_balance': float(wallet.balance)
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

# ========== ADMIN PANEL ==========

@staff_member_required
def admin_dashboard(request):
    """Complete Admin Dashboard HTML"""
    return render(request, 'admin_dashboard.html')

@staff_member_required
def admin_withdrawals_panel(request):
    pending_withdrawals = Transaction.objects.filter(transaction_type='WITHDRAW', status='PENDING').order_by('-created_at')
    return render(request, 'admin_withdrawals.html', {
        'pending_withdrawals': pending_withdrawals,
        'total_pending': pending_withdrawals.count(),
        'total_amount_pending': sum(float(w.amount) for w in pending_withdrawals)
    })

@staff_member_required
def admin_approve_withdrawal(request, transaction_id):
    if request.method == 'POST':
        try:
            transaction = Transaction.objects.get(transaction_id=transaction_id, transaction_type='WITHDRAW', status='PENDING')
            transaction.status = 'COMPLETED'
            transaction.approved_by = request.user
            transaction.approved_at = datetime.now()
            transaction.save()
            return JsonResponse({'status': 'success', 'message': 'Withdrawal approved'})
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'})
    return JsonResponse({'status': 'error'})

@staff_member_required
def admin_reject_withdrawal(request, transaction_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transaction = Transaction.objects.get(transaction_id=transaction_id, transaction_type='WITHDRAW', status='PENDING')
            wallet = Wallet.objects.get(user=transaction.user)
            wallet.add_balance(transaction.amount)
            
            transaction.status = 'FAILED'
            transaction.approved_by = request.user
            transaction.approved_at = datetime.now()
            transaction.rejection_reason = data.get('reason', 'Rejected by admin')
            transaction.save()
            return JsonResponse({'status': 'success', 'message': 'Withdrawal rejected'})
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'})
    return JsonResponse({'status': 'error'})

@staff_member_required
def admin_stats_api(request):
    total_users = User.objects.count()
    pending_withdrawals = Transaction.objects.filter(transaction_type='WITHDRAW', status='PENDING').count()
    pending_amount = sum(t.amount for t in Transaction.objects.filter(transaction_type='WITHDRAW', status='PENDING'))
    total_rewards = GameReward.objects.filter(status='CLAIMED').count()
    
    return JsonResponse({
        'total_users': total_users,
        'pending_withdrawals': pending_withdrawals,
        'pending_amount': float(pending_amount),
        'total_rewards': total_rewards
    })

@staff_member_required
def admin_users_api(request):
    users = User.objects.all()
    data = []
    for u in users:
        wallet, _ = Wallet.objects.get_or_create(user=u)
        total_wins = GameReward.objects.filter(user=u, status='CLAIMED').count()
        data.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'balance': float(wallet.balance),
            'total_wins': total_wins,
            'joined_date': u.date_joined.strftime("%d %b %Y")
        })
    return JsonResponse(data, safe=False)

@staff_member_required
def admin_pending_withdrawals_api(request):
    pendings = Transaction.objects.filter(transaction_type='WITHDRAW', status='PENDING').order_by('-created_at')
    data = []
    for p in pendings:
        data.append({
            'transaction_id': p.transaction_id,
            'user_id': p.user.id,
            'username': p.user.username,
            'amount': float(p.amount),
            'upi_id': p.upi_id,
            'created_at': p.created_at.strftime("%d %b %Y, %I:%M %p")
        })
    return JsonResponse(data, safe=False)

@staff_member_required
def admin_all_rewards_api(request):
    rewards = GameReward.objects.all().order_by('-created_at')[:200]
    data = []
    for r in rewards:
        data.append({
            'win_id': r.win_id,
            'username': r.user.username,
            'amount': float(r.win_amount),
            'status': r.status,
            'date': r.created_at.strftime("%d %b %Y")
        })
    return JsonResponse(data, safe=False)

@staff_member_required
def admin_user_detail_api(request, user_id):
    user = User.objects.get(id=user_id)
    wallet, _ = Wallet.objects.get_or_create(user=user)
    
    deposits = Transaction.objects.filter(user=user, transaction_type='DEPOSIT', status='COMPLETED')
    deposit_data = [{'transaction_id': d.transaction_id, 'amount': float(d.amount), 'utr_number': d.utr_number, 'date': d.created_at.strftime("%d %b %Y")} for d in deposits]
    
    completed_withdrawals = Transaction.objects.filter(user=user, transaction_type='WITHDRAW', status='COMPLETED')
    withdrawal_data = [{'transaction_id': w.transaction_id, 'amount': float(w.amount), 'upi_id': w.upi_id, 'status': w.status, 'date': w.created_at.strftime("%d %b %Y")} for w in completed_withdrawals]
    
    pending_withdrawals = Transaction.objects.filter(user=user, transaction_type='WITHDRAW', status='PENDING')
    pending_data = [{'transaction_id': p.transaction_id, 'amount': float(p.amount), 'upi_id': p.upi_id} for p in pending_withdrawals]
    
    rewards = GameReward.objects.filter(user=user)
    reward_data = [{'win_id': r.win_id, 'amount': float(r.win_amount), 'status': r.status, 'date': r.created_at.strftime("%d %b %Y")} for r in rewards]
    
    total_wins = GameReward.objects.filter(user=user, status='CLAIMED').count()
    
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'balance': float(wallet.balance),
        'total_wins': total_wins,
        'joined_date': user.date_joined.strftime("%d %b %Y"),
        'deposits': deposit_data,
        'completed_withdrawals': withdrawal_data,
        'pending_withdrawals': pending_data,
        'rewards': reward_data
    })


# ========== GAME APIS ==========

# ========== GAME APIS ==========

@login_required
def process_game_fee(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = float(data.get('amount', 10))
        except:
            amount = 10
        
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        # 🔥 FIX: Decimal me convert kar
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        
        if wallet.balance >= amount_decimal:
            wallet.deduct_balance(amount_decimal)  # ✅ Decimal pass kar
            Transaction.objects.create(
                user=request.user,
                transaction_type='GAME_FEE',
                amount=amount_decimal,
                status='COMPLETED',
                description=f"Game entry fee"
            )
            return JsonResponse({'status': 'success', 'balance': float(wallet.balance)})
        else:
            return JsonResponse({'status': 'error', 'message': 'Insufficient balance!'})
    return JsonResponse({'status': 'error'})
@login_required
def save_win_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            win_amount = float(data.get('win_amount', 10))
            user = request.user
            
            prefix = f"UID{user.id}"
            suffix = ''.join(random.choices(string.digits + string.ascii_uppercase, k=6))
            win_id = f"{prefix}-{suffix}"
            
            while GameReward.objects.filter(win_id=win_id).exists():
                suffix = ''.join(random.choices(string.digits + string.ascii_uppercase, k=6))
                win_id = f"{prefix}-{suffix}"
            
            GameReward.objects.create(user=user, win_id=win_id, status='WIN', win_amount=win_amount)
            return JsonResponse({"status": "success", "win_id": win_id, "win_amount": win_amount})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error"})

@login_required
def add_win_reward(request, win_id):
    try:
        reward = GameReward.objects.get(win_id=win_id, user=request.user)
        if reward.status != 'CLAIMED':
            wallet, _ = Wallet.objects.get_or_create(user=request.user)
            wallet.add_balance(reward.win_amount)
            reward.status = 'CLAIMED'
            reward.save()
            Transaction.objects.create(
                user=request.user,
                transaction_type='WIN_REWARD',
                amount=reward.win_amount,
                status='COMPLETED',
                description=f"Scratch card reward claimed - {win_id}"
            )
            return JsonResponse({"status": "success", "balance": float(wallet.balance)})
        else:
            return JsonResponse({"status": "error", "message": "Already claimed"})
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
                wallet, _ = Wallet.objects.get_or_create(user=request.user)
                wallet.add_balance(reward.win_amount)
                Transaction.objects.create(
                    user=request.user,
                    transaction_type='WIN_REWARD',
                    amount=reward.win_amount,
                    status='COMPLETED',
                    description=f"Scratch card reward claimed - {win_id}"
                )
            reward.save()
            return JsonResponse({"status": "success"})
        except GameReward.DoesNotExist:
            return JsonResponse({"status": "error", "message": "ID not found!"})
    return JsonResponse({"status": "error"})

@login_required
def get_wallet_balance(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    return JsonResponse({'status': 'success', 'balance': float(wallet.balance)})

@login_required
def add_win_amount(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = float(data.get('amount', 0))
            
            from decimal import Decimal
            amount_decimal = Decimal(str(amount))
            
            wallet, _ = Wallet.objects.get_or_create(user=request.user)
            wallet.add_balance(amount_decimal)  # ✅ Decimal pass kar
            
            Transaction.objects.create(
                user=request.user,
                transaction_type='WIN_REWARD',
                amount=amount_decimal,
                status='COMPLETED',
                description="Mines game win reward"
            )
            return JsonResponse({'status': 'success', 'balance': float(wallet.balance)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})
@login_required
def account_data_api(request):
    user = request.user
    wallet, _ = Wallet.objects.get_or_create(user=user)
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:50]
    
    total_deposit = sum(t.amount for t in transactions if t.transaction_type == 'DEPOSIT' and t.status == 'COMPLETED')
    total_withdraw = sum(t.amount for t in transactions if t.transaction_type == 'WITHDRAW' and t.status == 'COMPLETED')
    
    txn_data = []
    for t in transactions:
        txn_data.append({
            'id': t.transaction_id,
            'type': t.transaction_type,
            'type_display': t.get_transaction_type_display(),
            'amount': float(t.amount),
            'status': t.status,
            'date': t.created_at.strftime("%d %b %Y, %I:%M %p"),
            'utr': t.utr_number if t.utr_number else ''
        })
    
    return JsonResponse({
        'status': 'success',
        'balance': float(wallet.balance),
        'total_deposit': float(total_deposit),
        'total_withdraw': float(total_withdraw),
        'transactions': txn_data
    })

def payment_success(request):
    amount = request.GET.get('amount', 0)
    return render(request, 'payment_success.html', {'amount': amount})

def payment_failed(request):
    return render(request, 'payment_failed.html')