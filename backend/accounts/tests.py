from unittest.mock import MagicMock, patch

from django.conf import settings
from rest_framework.test import APITestCase

from .models import CustomUser


class RegistroLoginTests(APITestCase):
    def test_registro_e_login(self):
        resposta = self.client.post(
            "/api/auth/register/",
            {"email": "ana@teste.com", "password": "Senha@123", "full_name": "Ana"},
            format="json",
        )
        self.assertEqual(resposta.status_code, 201)

        resposta = self.client.post(
            "/api/auth/login/", {"email": "ana@teste.com", "password": "Senha@123"}, format="json"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("access", resposta.json())
        self.assertIn("refresh", resposta.json())

    def test_senha_fraca_e_rejeitada(self):
        resposta = self.client.post(
            "/api/auth/register/", {"email": "ana@teste.com", "password": "senha123"}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(CustomUser.objects.exists())

    def test_login_com_senha_errada(self):
        CustomUser.objects.create_user(email="ana@teste.com", password="Senha@123")
        resposta = self.client.post(
            "/api/auth/login/", {"email": "ana@teste.com", "password": "Errada@123"}, format="json"
        )
        self.assertEqual(resposta.status_code, 401)

    def test_perfil_exige_token(self):
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)

    def test_perfil_com_token(self):
        CustomUser.objects.create_user(email="ana@teste.com", password="Senha@123")
        token = self.client.post(
            "/api/auth/login/", {"email": "ana@teste.com", "password": "Senha@123"}, format="json"
        ).json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resposta = self.client.get("/api/auth/profile/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["email"], "ana@teste.com")


def resposta_google(dados, ok=True):
    resposta = MagicMock()
    resposta.ok = ok
    resposta.json.return_value = dados
    return resposta


class GoogleLoginTests(APITestCase):
    url = "/api/auth/google/"

    def dados(self, **extra):
        base = {
            "aud": settings.GOOGLE_CLIENT_ID,
            "email": "ana@gmail.com",
            "email_verified": "true",
            "name": "Ana",
        }
        base.update(extra)
        return base

    @patch("accounts.views.requests.get")
    def test_token_valido_cria_usuario(self, get):
        get.return_value = resposta_google(self.dados())
        resposta = self.client.post(self.url, {"token": "x"}, format="json")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(CustomUser.objects.filter(email="ana@gmail.com").exists())

    @patch("accounts.views.requests.get")
    def test_token_de_outro_app_e_rejeitado(self, get):
        get.return_value = resposta_google(self.dados(aud="outro-app.apps.googleusercontent.com"))
        resposta = self.client.post(self.url, {"token": "x"}, format="json")
        self.assertEqual(resposta.status_code, 401)
        self.assertFalse(CustomUser.objects.exists())

    @patch("accounts.views.requests.get")
    def test_email_nao_verificado_e_rejeitado(self, get):
        get.return_value = resposta_google(self.dados(email_verified="false"))
        resposta = self.client.post(self.url, {"token": "x"}, format="json")
        self.assertEqual(resposta.status_code, 401)

    @patch("accounts.views.requests.get")
    def test_token_invalido_no_google(self, get):
        get.return_value = resposta_google({"error": "invalid_token"}, ok=False)
        resposta = self.client.post(self.url, {"token": "x"}, format="json")
        self.assertEqual(resposta.status_code, 401)

    def test_sem_token(self):
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)
