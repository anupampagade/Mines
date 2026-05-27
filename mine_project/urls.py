# mine_project/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('game_api.urls')),
    path('admin/', admin.site.urls),
]