<h1 align="center">TripSync ✈️</h1>

<p align="center">
  Planejamento de viagens em grupo: despesas compartilhadas, acerto de contas, sugestões com votação e gestão de participantes.
</p>

<p align="center">
  <a href="https://github.com/Otavio-Novais/TripSync/actions/workflows/ci.yml"><img src="https://github.com/Otavio-Novais/TripSync/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/PostgreSQL-produção-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
</p>

---

## Visão geral

Quem já viajou em grupo conhece o problema: os gastos ficam espalhados entre várias pessoas, ninguém sabe quem deve quanto, e as ideias de passeio se perdem no grupo de mensagens. O TripSync junta tudo isso numa aplicação web com **API REST em Django** e **SPA em React**.

Projeto desenvolvido para a disciplina de **Engenharia de Software** (Ciência da Computação, UNIFESP).

<!-- Dica: adicione aqui um print ou GIF do dashboard financeiro, ex.: ![Finanças](docs/financas.png) -->

## Funcionalidades

**Finanças do grupo**
- Despesas com pagador, categoria e data, divididas **igualmente, por valor exato ou por porcentagem**
- **Rascunhos**: despesas ainda não confirmadas, visíveis só para quem as criou e fora do cálculo de saldos
- Saldo de cada participante (quanto pagou menos quanto consumiu) e totais "a receber" e "a pagar"
- **Sugestão de acertos**: um algoritmo guloso cruza os maiores devedores com os maiores credores para reduzir o número de transferências
- Registro do acerto, que zera a dívida entre as duas pessoas

**Sugestões com votação**
- Ideias de hospedagem, atividade ou comida, com votos dos participantes
- Status: em votação, em discussão, concluída ou reprovada

**Participantes**
- Papéis de **admin** e **membro** (quem cria a viagem vira admin)
- Convites por email, reenvio e cancelamento, promoção a admin e remoção de membros (só admins)

**Conta**
- Cadastro com senha forte (mínimo 8 caracteres, maiúscula, número e caractere especial)
- Login por email e senha ou **com Google**, autenticação via **JWT** (access + refresh)
- Recuperação de senha por email, perfil com foto e preferências, troca de senha e exclusão de conta

## Stack

| Camada | Tecnologias |
|---|---|
| Backend | Python 3.12, Django 5.2, Django REST Framework, SimpleJWT, Pillow, WhiteNoise, Gunicorn |
| Banco | PostgreSQL em produção (Neon), SQLite em desenvolvimento |
| Frontend | React 19 (Create React App), React Router 7, Axios, Lucide, React DatePicker, `@react-oauth/google` |
| Qualidade | Testes do Django + DRF `APITestCase`, ESLint, GitHub Actions |
| Deploy | Heroku (backend e frontend), via GitHub Actions |

## Arquitetura

```text
┌───────────────────────────┐   JSON + JWT   ┌──────────────────────────────────────┐
│ React SPA                 │ ─────────────► │ Django REST API                       │
│ pages/   telas            │                │ accounts/  usuários, JWT, Google,     │
│ services/ clientes da API │ ◄───────────── │            reset de senha, perfil     │
│ contexts/ estado global   │                │ planner/   viagens, despesas, rateios,│
└───────────────────────────┘                │            sugestões, votos, membros  │
                                             └──────────────────┬───────────────────┘
                                                                │ ORM
                                                        PostgreSQL / SQLite
```

**Modelo de dados (app `planner`)**: `Viagem` tem participantes e, para cada um, um `TripMember` com o papel. Cada `Despesa` tem um pagador e vários `Rateio` (quanto cada participante deve). `Sugestao` recebe `Voto`, e `TripInvite` guarda os convites pendentes.

## Como rodar localmente

**Pré-requisitos:** Python 3.12+ e Node.js 20+.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                  # DEBUG=True e SQLite por padrão
python manage.py migrate
python manage.py runserver
```

A API sobe em `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend/tripsync-frontend
npm install
npm start
```

O app abre em `http://localhost:3000` e, por padrão, usa a API em `http://127.0.0.1:8000`. Para apontar para outra URL, defina `REACT_APP_API_URL`.

### Testes

```bash
cd backend
python manage.py test                 # 24 testes: saldos, acertos, permissões, auth e login Google

cd frontend/tripsync-frontend
CI=true npm run build                 # build com ESLint; qualquer aviso falha
```

O workflow [`ci.yml`](.github/workflows/ci.yml) roda as duas verificações em todo push e pull request.

## Variáveis de ambiente

**Backend** (`backend/.env`, veja [`.env.example`](backend/.env.example)):

| Variável | Uso | Padrão |
|---|---|---|
| `SECRET_KEY` | Chave do Django e assinatura dos JWT | obrigatória com `DEBUG=False` |
| `DEBUG` | Modo de desenvolvimento | `False` |
| `ALLOWED_HOSTS` | Hosts aceitos, separados por vírgula | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | Origens do frontend | `http://localhost:3000,...` |
| `CSRF_TRUSTED_ORIGINS` | Origens HTTPS confiáveis (admin) | vazio |
| `DATABASE_URL` | Banco de dados | parâmetros `DB_*` do PostgreSQL |
| `FRONTEND_URL` | Base dos links enviados por email | `http://localhost:3000` |
| `GOOGLE_CLIENT_ID` | Client ID OAuth aceito no login Google | ID do projeto |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Envio de emails por SMTP | emails impressos no console |

**Frontend:** `REACT_APP_API_URL` e `REACT_APP_GOOGLE_CLIENT_ID`.

## Segurança

- Segredos e flags de produção ficam no ambiente, não no código. Sem `SECRET_KEY`, a aplicação não sobe em modo produção.
- Senhas com o hasher padrão do Django (PBKDF2-SHA256) e validação de complexidade.
- JWT com access de 12 h e refresh de 7 dias, com rotação.
- O login Google confere no `tokeninfo` se o token foi emitido para este app (`aud`) e se o email foi verificado.
- Toda rota de viagem confere se o usuário participa dela. Ações administrativas exigem o papel de admin.

## Deploy

O workflow [`deploy.yml`](.github/workflows/deploy.yml) publica o backend e o frontend (via `git subtree`) em dois apps do Heroku. Hoje ele roda **só manualmente**, porque os apps estão desativados. No Heroku, configure as variáveis da tabela acima com `DEBUG=False`.

## Limitações conhecidas e próximos passos

- **Aceite de convite:** o email é enviado com o link `/join/<token>`, mas o fluxo de aceite (rota no frontend + endpoint no backend) ainda não existe.
- **Uploads** (avatares e capas) ficam no disco local. Em produção, com `DEBUG=False` e o disco efêmero do Heroku, o caminho é usar um storage externo (S3, Cloudinary).
- **Roteiro** dia a dia ainda é um placeholder ("Em breve").
- O acerto de contas usa uma heurística gulosa: reduz as transferências, mas nem sempre chega ao mínimo teórico.
- Ainda não há testes automatizados no frontend.
