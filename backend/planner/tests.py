from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Despesa, Rateio, TripMember, Viagem

User = get_user_model()


class BaseViagemTestCase(APITestCase):
    """Viagem com três participantes: Ana (admin), Bruno e Carla."""

    def setUp(self):
        self.ana = User.objects.create_user(email="ana@teste.com", password="Senha@123", full_name="Ana")
        self.bruno = User.objects.create_user(email="bruno@teste.com", password="Senha@123", full_name="Bruno")
        self.carla = User.objects.create_user(email="carla@teste.com", password="Senha@123", full_name="Carla")
        self.intruso = User.objects.create_user(email="intruso@teste.com", password="Senha@123")

        self.viagem = Viagem.objects.create(
            titulo="Chile",
            nome="Chile 2026",
            destino="Santiago",
            data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 10),
        )
        self.viagem.participantes.add(self.ana)
        self.viagem.participantes.add(self.bruno, self.carla)

    def url(self, sufixo):
        return f"/planner/api/viagem/{self.viagem.id}/{sufixo}"

    def criar_despesa(self, pagador, valor, rateios, status="CONFIRMADO"):
        despesa = Despesa.objects.create(
            viagem=self.viagem,
            pagador=pagador,
            titulo="Despesa",
            valor_total=Decimal(valor),
            data=date(2026, 7, 2),
            status=status,
        )
        for participante, devido in rateios:
            Rateio.objects.create(despesa=despesa, participante=participante, valor_devido=Decimal(devido))
        return despesa

    def saldos(self, como=None):
        self.client.force_authenticate(como or self.ana)
        resposta = self.client.get(self.url("financas/"))
        self.assertEqual(resposta.status_code, 200)
        return {item["id"]: item["saldo"] for item in resposta.json()["resumo"]}, resposta.json()


class SaldosTests(BaseViagemTestCase):
    def test_despesa_dividida_igualmente(self):
        # Ana paga 300 e divide igualmente entre os três.
        self.criar_despesa(self.ana, "300.00", [(self.ana, "100"), (self.bruno, "100"), (self.carla, "100")])

        saldos, corpo = self.saldos()

        self.assertEqual(saldos[self.ana.id], 200.0)
        self.assertEqual(saldos[self.bruno.id], -100.0)
        self.assertEqual(saldos[self.carla.id], -100.0)
        self.assertEqual(corpo["user_stats"]["a_receber"], 200.0)
        self.assertEqual(corpo["user_stats"]["a_pagar"], 0)

    def test_soma_dos_saldos_e_zero(self):
        self.criar_despesa(self.ana, "300.00", [(self.ana, "100"), (self.bruno, "100"), (self.carla, "100")])
        self.criar_despesa(self.bruno, "90.00", [(self.bruno, "30"), (self.carla, "60")])

        saldos, _ = self.saldos()

        self.assertAlmostEqual(sum(saldos.values()), 0.0)
        self.assertEqual(saldos[self.carla.id], -160.0)

    def test_rascunho_nao_entra_no_saldo_e_so_aparece_para_o_dono(self):
        self.criar_despesa(self.bruno, "500.00", [(self.ana, "500")], status="RASCUNHO")

        saldos, corpo_ana = self.saldos(como=self.ana)
        self.assertEqual(saldos[self.ana.id], 0.0)
        self.assertEqual(corpo_ana["despesas"], [])

        _, corpo_bruno = self.saldos(como=self.bruno)
        self.assertEqual(len(corpo_bruno["despesas"]), 1)

    def test_acerto_de_contas_zera_os_saldos(self):
        self.criar_despesa(self.ana, "200.00", [(self.ana, "100"), (self.bruno, "100")])
        self.client.force_authenticate(self.bruno)

        resposta = self.client.post(
            self.url("liquidar/"),
            {"devedor_id": self.bruno.id, "credor_id": self.ana.id, "valor": 100},
            format="json",
        )

        self.assertEqual(resposta.status_code, 201)
        saldos, _ = self.saldos()
        self.assertEqual(saldos[self.ana.id], 0.0)
        self.assertEqual(saldos[self.bruno.id], 0.0)

    def test_criar_despesa_pela_api(self):
        self.client.force_authenticate(self.carla)

        resposta = self.client.post(
            self.url("despesa/nova/"),
            {
                "pagador_id": self.carla.id,
                "titulo": "Jantar",
                "valor_total": "120.00",
                "data": "2026-07-03",
                "rateios": [
                    {"user_id": self.ana.id, "valor": "60.00"},
                    {"user_id": self.carla.id, "valor": "60.00"},
                ],
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 201)
        saldos, _ = self.saldos()
        self.assertEqual(saldos[self.carla.id], 60.0)
        self.assertEqual(saldos[self.ana.id], -60.0)


class PermissoesFinancasTests(BaseViagemTestCase):
    def test_nao_participante_nao_ve_financas(self):
        self.client.force_authenticate(self.intruso)
        self.assertEqual(self.client.get(self.url("financas/")).status_code, 403)

    def test_nao_participante_nao_cria_despesa(self):
        self.client.force_authenticate(self.intruso)
        resposta = self.client.post(
            self.url("despesa/nova/"),
            {"pagador_id": self.ana.id, "titulo": "x", "valor_total": "10", "data": "2026-07-03", "rateios": []},
            format="json",
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Despesa.objects.exists())

    def test_nao_participante_nao_registra_acerto(self):
        self.client.force_authenticate(self.intruso)
        resposta = self.client.post(
            self.url("liquidar/"),
            {"devedor_id": self.bruno.id, "credor_id": self.ana.id, "valor": 50},
            format="json",
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Despesa.objects.exists())

    def test_pagador_precisa_participar_da_viagem(self):
        self.client.force_authenticate(self.ana)
        resposta = self.client.post(
            self.url("despesa/nova/"),
            {"pagador_id": self.intruso.id, "titulo": "x", "valor_total": "10", "data": "2026-07-03", "rateios": []},
            format="json",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Despesa.objects.exists())

    def test_requer_autenticacao(self):
        self.assertEqual(self.client.get(self.url("financas/")).status_code, 401)


class MembrosTests(BaseViagemTestCase):
    def test_primeiro_participante_vira_admin(self):
        self.assertEqual(TripMember.objects.get(viagem=self.viagem, user=self.ana).role, "ADMIN")
        self.assertEqual(TripMember.objects.get(viagem=self.viagem, user=self.bruno).role, "MEMBER")

    def test_somente_admin_envia_convites(self):
        self.client.force_authenticate(self.bruno)
        resposta = self.client.post(self.url("convites/enviar/"), {"emails": "novo@teste.com"}, format="json")
        self.assertEqual(resposta.status_code, 403)

    def test_admin_envia_convite(self):
        self.client.force_authenticate(self.ana)
        resposta = self.client.post(self.url("convites/enviar/"), {"emails": "novo@teste.com"}, format="json")
        self.assertEqual(resposta.status_code, 201)

    def test_nao_participante_nao_ve_viagem(self):
        self.client.force_authenticate(self.intruso)
        self.assertEqual(self.client.get(self.url("")).status_code, 403)
