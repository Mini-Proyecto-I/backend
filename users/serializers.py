from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer personalizado para autenticación JWT que usa email en lugar de username.
    Incluye email y nombre en el payload del token para uso en el frontend.
    
    Nota: El campo en el request body debe llamarse 'email' (no 'username').
    """
    
    # Especificar que el campo de autenticación es 'email'
    username_field = 'email'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Renombrar el campo 'username' a 'email' en el formulario
        if 'username' in self.fields:
            self.fields['email'] = self.fields.pop('username')
            self.fields['email'].label = 'Email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["name"] = user.name
        return token


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer para crear, actualizar y listar usuarios.
    
    Campos:
    - id: Identificador único (solo lectura)
    - email: Correo electrónico (único, requerido)
    - name: Nombre completo (requerido)
    - daily_hours_limit: Límite de horas diarias de estudio (0.5-24.0, default: 6.0)
    - password: Contraseña (solo escritura, no se devuelve en respuestas)
    - is_active: Estado activo del usuario (solo lectura para usuarios normales)
    - date_joined: Fecha de registro (solo lectura)
    """
    
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Contraseña del usuario. Mínimo 8 caracteres. Solo para creación/actualización."
    )
    
    email = serializers.EmailField(
        required=True,
        help_text="Correo electrónico único del usuario"
    )
    
    name = serializers.CharField(
        required=True,
        max_length=150,
        min_length=2,
        trim_whitespace=True,
        help_text="Nombre completo del usuario (2-150 caracteres)"
    )
    
    daily_hours_limit = serializers.DecimalField(
        required=False,
        max_digits=4,
        decimal_places=2,
        min_value=0.5,
        max_value=24.0,
        help_text="Límite de horas diarias de estudio (0.5-24.0 horas)"
    )
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'daily_hours_limit',
            'password',
            'is_active',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'is_active': {'read_only': True},
        }
    
    def validate_email(self, value):
        """
        Validar que el email sea único y esté normalizado.
        
        Args:
            value: Email a validar
            
        Returns:
            str: Email normalizado
            
        Raises:
            serializers.ValidationError: Si el email ya existe
        """
        if not value:
            raise serializers.ValidationError("El correo electrónico es obligatorio.")
        
        # Normalizar email (minúsculas, espacios)
        value = value.strip().lower()
        
        # Verificar unicidad (excluir instancia actual si estamos actualizando)
        queryset = User.objects.filter(email=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError(
                "Ya existe un usuario con este correo electrónico."
            )
        
        return value
    
    def validate_name(self, value):
        """
        Validar que el nombre no esté vacío y tenga longitud adecuada.
        
        Args:
            value: Nombre a validar
            
        Returns:
            str: Nombre validado y limpiado
        """
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre es obligatorio.")
        
        value = value.strip()
        
        if len(value) < 2:
            raise serializers.ValidationError(
                "El nombre debe tener al menos 2 caracteres."
            )
        
        if len(value) > 150:
            raise serializers.ValidationError(
                "El nombre no puede exceder 150 caracteres."
            )
        
        return value
    
    def validate_password(self, value):
        """
        Validar la contraseña usando los validadores de Django.
        
        Args:
            value: Contraseña a validar
            
        Returns:
            str: Contraseña validada
            
        Raises:
            serializers.ValidationError: Si la contraseña no cumple los requisitos
        """
        if not value:
            # En actualización, la contraseña es opcional
            if not self.instance:
                raise serializers.ValidationError("La contraseña es obligatoria al crear un usuario.")
            return value
        
        try:
            # Validar contraseña con los validadores de Django
            validate_password(value)
        except DjangoValidationError as e:
            # Convertir errores de Django a errores de DRF
            raise serializers.ValidationError(list(e.messages))
        
        return value
    
    def validate_daily_hours_limit(self, value):
        """
        Validar que el límite de horas esté en el rango permitido.
        
        Args:
            value: Límite de horas a validar
            
        Returns:
            decimal.Decimal: Límite validado
            
        Raises:
            serializers.ValidationError: Si el valor está fuera del rango
        """
        if value is None:
            return value
        
        if value < 0.5:
            raise serializers.ValidationError(
                "El límite de horas diarias no puede ser menor a 0.5 horas."
            )
        
        if value > 24.0:
            raise serializers.ValidationError(
                "El límite de horas diarias no puede ser mayor a 24.0 horas."
            )
        
        return value
    
    def validate(self, attrs):
        """
        Validación a nivel de objeto completo.
        
        Args:
            attrs: Diccionario con todos los atributos validados
            
        Returns:
            dict: Atributos validados
            
        Raises:
            serializers.ValidationError: Si hay errores de validación global
        """
        # Validar que al crear un usuario, la contraseña sea obligatoria
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({
                'password': 'La contraseña es obligatoria al crear un usuario.'
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Crear un nuevo usuario con contraseña hasheada.
        
        Args:
            validated_data: Datos validados del usuario
            
        Returns:
            User: Usuario creado
            
        Raises:
            serializers.ValidationError: Si falta la contraseña
        """
        password = validated_data.pop('password', None)
        
        if not password:
            raise serializers.ValidationError({
                'password': 'La contraseña es obligatoria al crear un usuario.'
            })
        
        # Usar create_user del manager para hashear la contraseña correctamente
        user = User.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            daily_hours_limit=validated_data.get('daily_hours_limit', 6.0),
            password=password,
            is_active=True,  # Por defecto, usuarios nuevos están activos
        )
        
        return user
    
    def update(self, instance, validated_data):
        """
        Actualizar un usuario existente.
        
        Args:
            instance: Instancia del usuario a actualizar
            validated_data: Datos validados para actualizar
            
        Returns:
            User: Usuario actualizado
        """
        password = validated_data.pop('password', None)
        
        # Actualizar campos normales
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Si se proporciona una nueva contraseña, hashearla
        if password:
            instance.set_password(password)
        
        # Guardar cambios
        instance.save()
        
        return instance
    
    def to_representation(self, instance):
        """
        Personalizar la representación del objeto en la respuesta.
        Excluir campos sensibles y formatear datos.
        
        Args:
            instance: Instancia del usuario
            
        Returns:
            dict: Representación del usuario para la respuesta
        """
        representation = super().to_representation(instance)
        
        # Formatear daily_hours_limit como string con 2 decimales
        if 'daily_hours_limit' in representation:
            representation['daily_hours_limit'] = str(representation['daily_hours_limit'])
        
        # Asegurar que nunca se devuelva la contraseña
        representation.pop('password', None)
        
        return representation
