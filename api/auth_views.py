from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import serializers
from django.conf import settings


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user information"""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    error = serializers.CharField()
    details = serializers.JSONField(required=False)


@extend_schema(
    request=UserRegistrationSerializer,
    responses={
        201: OpenApiResponse(TokenResponseSerializer, description="User created successfully"),
        400: OpenApiResponse(ErrorResponseSerializer, description="Validation error"),
    },
    description="Register a new user and return JWT tokens",
    tags=["auth"],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register a new user and return JWT tokens"""
    # Apply rate limiting if enabled
    if getattr(settings, 'RATELIMIT_ENABLE', True):
        from django_ratelimit.core import is_ratelimited
        from .rate_limiting import get_rate_limit
        rate = get_rate_limit('auth_register')
        if is_ratelimited(request=request, group='auth_register', fn=None, key='ip', rate=rate, method=['POST'], increment=True):
            from .rate_limiting import rate_limit_error_response
            return rate_limit_error_response()
        
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'error': 'Validation failed',
        'details': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token obtain view with user information"""
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    @extend_schema(
        responses={
            200: OpenApiResponse(TokenResponseSerializer, description="Login successful"),
            401: OpenApiResponse(ErrorResponseSerializer, description="Invalid credentials"),
        },
        description="Obtain JWT token pair for authentication",
        tags=["auth"],
    )
    def post(self, request, *args, **kwargs):
        # Apply rate limiting if enabled
        if getattr(settings, 'RATELIMIT_ENABLE', True):
            from django_ratelimit.core import is_ratelimited
            from .rate_limiting import get_rate_limit
            rate = get_rate_limit('auth_sensitive')
            if is_ratelimited(request=request, group='auth_login', fn=None, key='ip', rate=rate, method=['POST'], increment=True):
                from .rate_limiting import rate_limit_error_response
                return rate_limit_error_response()
            
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            username = request.data.get('username')
            user = User.objects.get(username=username)
            response.data['user'] = UserSerializer(user).data
        else:
            response.data = {
                'error': 'Invalid credentials',
                'details': 'Username or password is incorrect'
            }
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """Custom token refresh view with error handling"""
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    @extend_schema(
        responses={
            200: OpenApiResponse(description="Token refreshed successfully"),
            401: OpenApiResponse(ErrorResponseSerializer, description="Invalid or expired refresh token"),
        },
        description="Refresh JWT access token",
        tags=["auth"],
    )
    def post(self, request, *args, **kwargs):
        # Apply rate limiting if enabled
        if getattr(settings, 'RATELIMIT_ENABLE', True):
            from django_ratelimit.core import is_ratelimited
            from .rate_limiting import get_rate_limit
            rate = get_rate_limit('auth_refresh')
            if is_ratelimited(request=request, group='auth_refresh', fn=None, key='ip', rate=rate, method=['POST'], increment=True):
                from .rate_limiting import rate_limit_error_response
                return rate_limit_error_response()
            
        response = super().post(request, *args, **kwargs)
        if response.status_code != 200:
            response.data = {
                'error': 'Token refresh failed',
                'details': 'Invalid or expired refresh token'
            }
        return response


@extend_schema(
    responses={
        200: OpenApiResponse(UserSerializer, description="User profile retrieved successfully"),
        401: OpenApiResponse(ErrorResponseSerializer, description="Authentication required"),
    },
    description="Get current user profile (requires authentication)",
    tags=["auth"],
)
@api_view(['GET'])
def profile(request):
    """Get current user profile"""
    # Apply rate limiting if enabled
    if getattr(settings, 'RATELIMIT_ENABLE', True):
        from django_ratelimit.core import is_ratelimited
        from .rate_limiting import get_rate_limit
        rate = get_rate_limit('auth_general')
        if is_ratelimited(request=request, group='auth_profile', fn=None, key='user' if request.user.is_authenticated else 'ip', rate=rate, method=['GET'], increment=True):
            from .rate_limiting import rate_limit_error_response
            return rate_limit_error_response()
        
    if not request.user.is_authenticated:
        return Response({
            'error': 'Authentication required',
            'details': 'A valid JWT token is required to access this endpoint'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response(UserSerializer(request.user).data)