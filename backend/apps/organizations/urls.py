from django.urls import path
from .views import MeView, CustomTokenObtainPairView

urlpatterns = [
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='custom_token'),
    path('users/me/', MeView.as_view(), name='me'),
]
