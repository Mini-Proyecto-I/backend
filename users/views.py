from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer, UserRegistrationSerializer


User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista de obtención de token JWT que devuelve email y nombre en el payload."""
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """
    Endpoint público de registro.
    Permite crear nuevos usuarios que luego usarán JWT para autenticarse.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
