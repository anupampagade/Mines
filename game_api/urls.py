# game_api/urls.py - CORRECTED VERSION

from django.urls import path
from . import views

urlpatterns = [
    # Page Views
    path('', views.mine_page, name='mine'),
    path('mine/', views.mine_page, name='mine_page'),
    path('signup/', views.signup_page, name='signup'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('account/', views.account_page, name='account'),
    path('history/', views.history_view, name='history'),
    
    # Auth APIs
    path('api/signup/', views.signup_api, name='signup_api'),
    path('api/login/', views.login_api, name='login_api'),
    path('api/check-email/', views.check_email_api, name='check_email'),
    path('api/update-password/', views.update_password_api, name='update_password'),
    
    # Deposit APIs
    path('api/get-payment-details/', views.get_payment_details, name='get_payment_details'),
    path('api/verify-utr/', views.verify_utr_and_update_balance, name='verify_utr'),
    
    # Withdrawal API - YAHAN CORRECT KARO
    path('api/request-withdrawal/', views.request_withdrawal_api, name='request_withdrawal'),  # ← request_withdrawal_api
    # path('api/request-withdrawal/', views.request_withdrawal),  # YEH HATA DO
    
    # Admin APIs
    path('admin/withdrawals/', views.admin_withdrawals_panel, name='admin_withdrawals'),
    path('admin/withdrawals/<str:transaction_id>/approve/', views.admin_approve_withdrawal, name='admin_approve'),
    path('admin/withdrawals/<str:transaction_id>/reject/', views.admin_reject_withdrawal, name='admin_reject'),
    
    # Game APIs
    path('api/process-game-fee/', views.process_game_fee, name='process_game_fee'),
    path('api/save-win/', views.save_win_api, name='save_win'),
    path('api/add-win-reward/<str:win_id>/', views.add_win_reward, name='add_win_reward'),
    path('api/update-status/', views.update_status_api, name='update_status'),
    
    # Payment pages
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/failed/', views.payment_failed, name='payment_failed'),

    path('api/get-wallet-balance/', views.get_wallet_balance, name='get_wallet_balance'),
    path('api/add-win-amount/', views.add_win_amount, name='add_win_amount'),

    # Admin APIs
path('api/admin/stats/', views.admin_stats_api, name='admin_stats'),
path('api/admin/users/', views.admin_users_api, name='admin_users'),
path('api/admin/pending-withdrawals/', views.admin_pending_withdrawals_api, name='admin_pending'),
path('api/admin/all-rewards/', views.admin_all_rewards_api, name='admin_rewards'),
path('api/admin/user-detail/<int:user_id>/', views.admin_user_detail_api, name='user_detail'),

path('api/account-data/', views.account_data_api, name='account_data'),

path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
]