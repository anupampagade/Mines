# game_api/admin.py

from django.contrib import admin
from .models import GameReward, Wallet, Transaction

@admin.register(GameReward)
class GameRewardAdmin(admin.ModelAdmin):
    list_display = ['win_id', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['win_id', 'user__username']
    readonly_fields = ['win_id', 'created_at', 'updated_at']

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'created_at', 'updated_at']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['transaction_id', 'user__username']
    readonly_fields = ['transaction_id', 'created_at']
    
    actions = ['mark_as_completed']
    
    def mark_as_completed(self, request, queryset):
        for transaction in queryset:
            if transaction.transaction_type == 'WITHDRAW' and transaction.status == 'PENDING':
                # Withdraw approve karte time balance deduct karo
                wallet = transaction.user.wallet
                if wallet.deduct_balance(transaction.amount):
                    transaction.status = 'COMPLETED'
                    transaction.save()
                else:
                    self.message_user(request, f"Insufficient balance for {transaction.user.username}", 'ERROR')
            else:
                transaction.status = 'COMPLETED'
                transaction.save()
        self.message_user(request, f"{queryset.count()} transactions marked as completed.")
    mark_as_completed.short_description = "Mark selected as COMPLETED (Approve Withdrawals)"