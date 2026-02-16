from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista de obtención de token JWT que devuelve email y nombre en el payload."""
    serializer_class = CustomTokenObtainPairSerializer
