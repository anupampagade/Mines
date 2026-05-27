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
    
    path('api/get-payment-details/', views.get_payment_details),
    path('api/verify-utr/', views.verify_utr_and_update_balance),
    
    # Withdrawal APIs
    path('api/request-withdrawal/', views.request_withdrawal),
    
    # Admin APIs
    path('admin/withdrawals/', views.admin_withdrawals_panel),
    path('admin/withdrawals/<str:transaction_id>/approve/', views.admin_approve_withdrawal),
    path('admin/withdrawals/<str:transaction_id>/reject/', views.admin_reject_withdrawal),
    
    # Game APIs (existing)
    path('api/process-game-fee/', views.process_game_fee),
    path('api/save-win/', views.save_win_api),
    path('api/add-win-reward/<str:win_id>/', views.add_win_reward),
    path('api/update-status/', views.update_status_api),
    

]