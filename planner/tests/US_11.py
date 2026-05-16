"""
US 11: Inicio de sesión (Login).

Pruebas para:
- Iniciar sesión exitosamente obteniendo token JWT.
- Verificar que el token devuelto contiene las propiedades extra personalizadas 'email' y 'name'.
- Rechazar inicio de sesión con credenciales inválidas (contraseña errónea).
- Rechazar inicio de sesión cuando el usuario no existe.
- Validación de que rechaza parámetros incompletos (envíos sin email o sin password).
"""
import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class US11LoginTests(TestCase):
    """Pruebas del endpoint de inicio de sesión /api/auth/token/ (US 11)."""

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/auth/token/"
        self.user_data = {
            "email": "login@test.com",
            "password": "Secur3Password123!",
            "name": "Usuario Login"
        }
        # Crear usuario para probar
        self.user = User.objects.create_user(**self.user_data)

    def test_login_exitoso_y_custom_claims(self):
        """
        Si las credenciales son correctas, debe devolver los tokens JWT.
        Además debe incorporar 'email' y 'name' en el payload del access token
        en base al CustomTokenObtainPairSerializer definido.
        """
        payload = {
            "email": self.user_data["email"],
            "password": self.user_data["password"]
        }
        response = self.client.post(self.login_url, payload, format="json")
        
        # Se recibe token OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        
        # Validar las extensiones personalizadas del Custom Token Classifier
        token = response.data["access"]
        
        # Decodificamos solo la parte del payload del JWT de forma manual (sin firma)
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)  # pad necesario para decodificar
        payload_decoded = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
        
        # Comprobar "custom claims"
        self.assertIn("email", payload_decoded)
        self.assertIn("name", payload_decoded)
        self.assertEqual(payload_decoded["email"], self.user_data["email"])
        self.assertEqual(payload_decoded["name"], self.user_data["name"])

    def test_login_contrasena_incorrecta(self):
        """Debe retornar un error 401 si la contraseña es incorrecta (pero existe el usuario)."""
        payload = {
            "email": self.user_data["email"],
            "password": "WrongPassword1!"
        }
        response = self.client.post(self.login_url, payload, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    def test_login_usuario_inexistente(self):
        """Debe retornar un error 401 si se intenta loguear con un email no registrado."""
        payload = {
            "email": "no_existe@test.com",
            "password": "Password123!"
        }
        response = self.client.post(self.login_url, payload, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)

    def test_login_falta_password(self):
        """Debe retornar 400 Bad Request si no se envía la contraseña en el body."""
        payload_no_pass = {
            "email": self.user_data["email"]
        }
        response = self.client.post(self.login_url, payload_no_pass, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_falta_email(self):
        """Debe retornar 400 Bad Request si no se envía el email en el body."""
        payload_no_email = {
            "password": self.user_data["password"]
        }
        response = self.client.post(self.login_url, payload_no_email, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)