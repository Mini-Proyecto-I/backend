from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .serializers import CustomTokenObtainPairSerializer, UserSerializer

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista de obtención de token JWT que devuelve email y nombre en el payload."""
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(ModelViewSet):
    """
    ViewSet para gestionar usuarios.
    
    Endpoints disponibles:
    - POST /api/auth/users/ : Crear un nuevo usuario (público)
    - GET /api/auth/users/ : Listar usuarios (requiere autenticación)
    - GET /api/auth/users/{id}/ : Obtener un usuario específico (requiere autenticación)
    - PUT /api/auth/users/{id}/ : Actualizar completamente un usuario (requiere autenticación, solo propio)
    - PATCH /api/auth/users/{id}/ : Actualizar parcialmente un usuario (requiere autenticación, solo propio)
    - DELETE /api/auth/users/{id}/ : Eliminar un usuario (requiere autenticación, solo propio)
    - GET /api/auth/users/me/ : Obtener el perfil del usuario autenticado
    - PUT /api/auth/users/me/ : Actualizar el perfil del usuario autenticado
    - PATCH /api/auth/users/me/ : Actualizar parcialmente el perfil del usuario autenticado
    """
    serializer_class = UserSerializer
    queryset = User.objects.all()
    
    def get_permissions(self):
        """
        Instanciar y retornar la lista de permisos que requiere esta vista.
        
        - POST (crear): Permitir a cualquiera (registro público)
        - Otros métodos: Requerir autenticación
        
        Returns:
            list: Lista de instancias de permisos
        """
        if self.action == 'create':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar usuarios según el contexto y permisos.
        
        - Usuarios autenticados: pueden ver solo su propio perfil
        - Usuarios no autenticados: no pueden ver ningún usuario (excepto crear)
        
        Returns:
            QuerySet: QuerySet filtrado de usuarios
        """
        user = self.request.user
        
        if user.is_authenticated:
            # Los usuarios solo pueden ver su propio perfil
            return User.objects.filter(id=user.id)
        
        # Usuarios no autenticados no pueden listar usuarios
        return User.objects.none()
    
    def get_object(self):
        """
        Obtener el objeto usuario, asegurando que solo se pueda acceder al propio perfil.
        
        Returns:
            User: Instancia del usuario
            
        Raises:
            Http404: Si el usuario no existe o no tiene permisos
        """
        # Si se usa el endpoint /me/, retornar el usuario autenticado
        if self.kwargs.get('pk') == 'me':
            return self.request.user
        
        # Obtener el usuario por ID
        # get_queryset() ya filtra solo el usuario autenticado, pero verificamos por seguridad
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])
        
        # Verificación adicional de seguridad (aunque get_queryset ya filtra)
        # Esto previene problemas si alguien modifica get_queryset en el futuro
        if obj.id != self.request.user.id:
            raise PermissionDenied("No tienes permiso para acceder a este usuario.")
        
        return obj
    
    @extend_schema(
        summary="Crear un nuevo usuario",
        description="Endpoint público para registrar un nuevo usuario en el sistema.",
        request=UserSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Ejemplo de creación exitosa',
                value={
                    'email': 'nuevo@example.com',
                    'name': 'Juan Pérez',
                    'password': 'contraseña123',
                    'daily_hours_limit': 8.0
                },
                request_only=True,
            ),
        ],
    )
    def create(self, request, *args, **kwargs):
        """
        Crear un nuevo usuario (registro público).
        
        Args:
            request: Request HTTP con los datos del usuario
            
        Returns:
            Response: Respuesta con los datos del usuario creado o errores de validación
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Preparar respuesta sin incluir la contraseña
        response_serializer = self.get_serializer(user)
        
        return Response(
            {
                'success': True,
                'message': 'Usuario creado exitosamente.',
                'data': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        summary="Listar usuarios",
        description="Obtener la lista de usuarios (solo el propio perfil para usuarios autenticados).",
        responses={200: UserSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        """
        Listar usuarios (solo el propio perfil).
        
        Args:
            request: Request HTTP
            
        Returns:
            Response: Lista de usuarios (normalmente solo uno: el propio)
        """
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Obtener un usuario específico",
        description="Obtener los datos de un usuario por su ID (solo el propio perfil).",
        responses={
            200: UserSerializer,
            404: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Obtener un usuario específico (solo el propio perfil).
        
        Args:
            request: Request HTTP
            pk: ID del usuario
            
        Returns:
            Response: Datos del usuario o error si no tiene permisos
        """
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Actualizar completamente un usuario",
        description="Actualizar todos los campos de un usuario (solo el propio perfil).",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def update(self, request, *args, **kwargs):
        """
        Actualizar completamente un usuario (PUT).
        Solo puede actualizar su propio perfil.
        
        Nota: get_object() ya verifica que el usuario solo pueda acceder
        a su propio perfil, por lo que no es necesario verificar nuevamente.
        
        Args:
            request: Request HTTP con los datos a actualizar
            pk: ID del usuario
            
        Returns:
            Response: Datos del usuario actualizado o error
        """
        instance = self.get_object()  # Ya verifica permisos
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'success': True,
                'message': 'Usuario actualizado exitosamente.',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Actualizar parcialmente un usuario",
        description="Actualizar algunos campos de un usuario (solo el propio perfil).",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def partial_update(self, request, *args, **kwargs):
        """
        Actualizar parcialmente un usuario (PATCH).
        Solo puede actualizar su propio perfil.
        
        Nota: get_object() ya verifica que el usuario solo pueda acceder
        a su propio perfil, por lo que no es necesario verificar nuevamente.
        
        Args:
            request: Request HTTP con los datos a actualizar (parciales)
            pk: ID del usuario
            
        Returns:
            Response: Datos del usuario actualizado o error
        """
        instance = self.get_object()  # Ya verifica permisos
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'success': True,
                'message': 'Usuario actualizado exitosamente.',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Eliminar un usuario",
        description="Eliminar un usuario del sistema (solo el propio perfil).",
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def destroy(self, request, *args, **kwargs):
        """
        Eliminar un usuario (DELETE).
        Solo puede eliminar su propio perfil.
        
        Nota: get_object() ya verifica que el usuario solo pueda acceder
        a su propio perfil, por lo que no es necesario verificar nuevamente.
        
        Nota sobre el código HTTP:
        - Se usa 200 en lugar de 204 para mantener consistencia con otros endpoints
        - 204 (No Content) según RFC 7231 NO puede tener body
        - 200 permite devolver mensaje de éxito útil para el frontend
        
        Args:
            request: Request HTTP
            pk: ID del usuario
            
        Returns:
            Response: Respuesta con mensaje de éxito (200) o error
        """
        instance = self.get_object()  # Ya verifica permisos
        
        self.perform_destroy(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Usuario eliminado exitosamente.'
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Obtener perfil del usuario autenticado",
        description="Endpoint conveniente para obtener el perfil del usuario autenticado sin necesidad de conocer su ID.",
        responses={
            200: UserSerializer,
            401: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=['get'], url_path='me', url_name='me')
    def get_me(self, request):
        """
        Obtener el perfil del usuario autenticado.
        
        Endpoint: GET /api/auth/users/me/
        
        Args:
            request: Request HTTP
            
        Returns:
            Response: Datos del usuario autenticado
        """
        serializer = self.get_serializer(request.user)
        return Response(
            {
                'success': True,
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Actualizar perfil del usuario autenticado",
        description="Endpoint conveniente para actualizar el perfil del usuario autenticado (PUT completo).",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=['put'], url_path='me', url_name='me-update')
    def update_me(self, request):
        """
        Actualizar completamente el perfil del usuario autenticado (PUT).
        
        Endpoint: PUT /api/auth/users/me/
        
        Args:
            request: Request HTTP con los datos a actualizar
            
        Returns:
            Response: Datos del usuario actualizado
        """
        serializer = self.get_serializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'success': True,
                'message': 'Perfil actualizado exitosamente.',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Actualizar parcialmente el perfil del usuario autenticado",
        description="Endpoint conveniente para actualizar parcialmente el perfil del usuario autenticado (PATCH).",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiTypes.OBJECT,
            401: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=['patch'], url_path='me', url_name='me-partial-update')
    def partial_update_me(self, request):
        """
        Actualizar parcialmente el perfil del usuario autenticado (PATCH).
        
        Endpoint: PATCH /api/auth/users/me/
        
        Args:
            request: Request HTTP con los datos a actualizar (parciales)
            
        Returns:
            Response: Datos del usuario actualizado
        """
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'success': True,
                'message': 'Perfil actualizado exitosamente.',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
