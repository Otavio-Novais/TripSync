from urllib.parse import urlparse
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
import requests
from rest_framework import generics, permissions
from .serializers import UserRegistrationSerializer, ChangePasswordSerializer, UserProfileSerializer

from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
from django.contrib.auth import authenticate

# --- IMPORTS NOVOS DE SEGURANÇA ---
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator

# ----------------------------------

from .serializers import (
    UserRegistrationSerializer,
    PasswordResetRequestSerializer,
    SetNewPasswordSerializer,
)
from .models import CustomUser


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


# View de Login customizado
class CustomLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Email e senha são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password):
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                        "email": user.email,
                        "full_name": user.full_name,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Credenciais inválidas"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Credenciais inválidas"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


# View de Login com Google
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")

        if not token:
            return Response(
                {"error": "Token não fornecido"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 1. Validar o token direto na API do Google
            google_response = requests.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"id_token": token},
                timeout=5
            )
        except requests.exceptions.RequestException:
            logger.exception("Falha de rede ao validar token do Google")
            return Response(
                {"error": "Não foi possível validar o token com o Google."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not google_response.ok:
            return Response(
                {"error": "Token do Google inválido."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        google_data = google_response.json()

        # 2. O token precisa ter sido emitido para ESTE app e com email verificado.
        if google_data.get("aud") != settings.GOOGLE_CLIENT_ID:
            return Response(
                {"error": "Token do Google emitido para outro aplicativo."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if str(google_data.get("email_verified")).lower() != "true":
            return Response(
                {"error": "Email do Google não verificado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = google_data.get("email")
        name = google_data.get("name", "")

        if not email:
            return Response(
                {"error": "Email não encontrado no token do Google"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Verificar se o usuário existe. Se não, cria.
        user, created = CustomUser.objects.get_or_create(
            email=email, defaults={"full_name": name}
        )

        if created:
            user.set_unusable_password()
            user.save()

        # 4. Gerar tokens JWT
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "email": user.email,
                "full_name": user.full_name,
            },
            status=status.HTTP_200_OK,
        )


# View de Reset de Senha
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]

            form = PasswordResetForm(data={"email": email})

            if form.is_valid():
                frontend = urlparse(settings.FRONTEND_URL)
                opts = {
                    "use_https": frontend.scheme == "https",
                    "from_email": settings.DEFAULT_FROM_EMAIL,
                    "email_template_name": "registration/password_reset_email.html",
                    "subject_template_name": "registration/password_reset_subject.txt",
                    "domain_override": frontend.netloc,
                    "extra_email_context": {
                        "site_name": "Tripsync",
                        "protocol": frontend.scheme,
                    },
                }
                form.save(**opts)

            return Response(
                {"message": "Se o e-mail existir, um link foi enviado."},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetNewPasswordSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data["token"]
            uidb64 = serializer.validated_data["uidb64"]
            password = serializer.validated_data["password"]

            try:
                # Decodifica o ID do usuário
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = CustomUser.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
                return Response(
                    {"error": "Link inválido ou usuário não encontrado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Verifica se o token é válido para este usuário
            if default_token_generator.check_token(user, token):
                user.set_password(password)
                user.save()
                return Response(
                    {"message": "Senha redefinida com sucesso!"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Link expirado ou inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Retorna o usuário que está logado (quem mandou o Token)
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            # Verifica se a senha antiga está certa
            if not user.check_password(serializer.data.get("old_password")):
                return Response(
                    {"old_password": ["Senha atual incorreta."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Salva a nova
            user.set_password(serializer.data.get("new_password"))
            user.save()
            return Response(
                {"message": "Senha atualizada com sucesso!"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.is_active = False  # <--- A MÁGICA: Oculta sem apagar
        user.save()
        return Response(
            {"message": "Conta desativada com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )


