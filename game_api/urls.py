# game_api/urls.py
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
    
    # Payment Gateway APIs (Deposit)
    path('api/deposit/initiate/', views.initiate_deposit, name='initiate_deposit'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('payment/webhook/', views.payment_webhook, name='payment_webhook'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/failed/', views.payment_failed, name='payment_failed'),
    
    # Withdrawal APIs (User)
    path('api/withdraw/', views.withdraw_money, name='withdraw'),
    
    # Admin Withdrawal Panel
    path('admin/withdrawals/', views.admin_withdrawals_panel, name='admin_withdrawals'),
    path('admin/withdrawals/<str:transaction_id>/approve/', views.admin_approve_withdrawal, name='admin_approve'),
    path('admin/withdrawals/<str:transaction_id>/reject/', views.admin_reject_withdrawal, name='admin_reject'),
    
    # Game APIs
    path('api/process-game-fee/', views.process_game_fee, name='process_game_fee'),
    path('api/save-win/', views.save_win_api, name='save_win'),
    path('api/add-win-reward/<str:win_id>/', views.add_win_reward, name='add_win_reward'),
    path('api/update-status/', views.update_status_api, name='update_status'),
]