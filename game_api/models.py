# game_api/models.py - Complete code

import random
import string
from django.db import models
from django.contrib.auth.models import User

class GameReward(models.Model):
    STATUS_CHOICES = [
        ('WIN', 'Won but Not Scratched'),
        ('SCRATCHED', 'Scratched but Not Submitted'),
        ('CLAIMED', 'Claimed & Expired'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    win_id = models.CharField(max_length=20, unique=True) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WIN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.win_id} - {self.status}"

    @staticmethod
    def generate_win_id(user_uid):
        prefix = str(user_uid)[:4].upper()
        suffix = ''.join(random.choices(string.digits, k=6))
        return f"{prefix}-{suffix}"


# ========== NAYA WALLET MODEL ==========
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - ₹{self.balance}"
    
    def add_balance(self, amount):
        """Balance add karo"""
        self.balance += amount
        self.save()
        return self.balance
    
    def deduct_balance(self, amount):
        """Balance deduct karo (agar sufficient ho)"""
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False


# ========== TRANSACTION MODEL ==========
# In game_api/models.py, find the Transaction model and REMOVE this line:
# payment_screenshot = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)

# Your Transaction model should look like this (without payment_screenshot):
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAW', 'Withdraw'),
        ('GAME_FEE', 'Game Fee'),
        ('WIN_REWARD', 'Win Reward'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')
    transaction_id = models.CharField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Keep only these fields (remove payment_screenshot)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    utr_number = models.CharField(max_length=100, blank=True, null=True)  # IMPORTANT: Add this
    bank_account = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    account_holder = models.CharField(max_length=100, blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transactions')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            prefix = self.transaction_type[:3].upper()
            suffix = ''.join(random.choices(string.digits + string.ascii_uppercase, k=10))
            self.transaction_id = f"{prefix}-{suffix}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.transaction_id} - {self.transaction_type} - ₹{self.amount} - {self.status}"

class PaymentGatewayLog(models.Model):
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    gateway_transaction_id = models.CharField(max_length=200)
    gateway_response = models.TextField()
    request_data = models.TextField()
    status = models.CharField(max_length=50, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Gateway: {self.gateway_transaction_id}"


        # Wallet model mein yeh function hona chahiye:
    def deduct_balance(self, amount):
            if self.balance >= amount:
                self.balance = self.balance - amount  # Decimal - Decimal = OK
                self.save()
                return True
            return False