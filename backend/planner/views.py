from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .serializers import TripDashboardSerializer, TripSerializer, SugestaoSerializer, VotoSerializer
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction, models
from django.db.models import Sum
import json
from .models import Viagem, Despesa, Rateio, Sugestao, Voto, TripMember
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.db import transaction
from datetime import date

@api_view(['GET'])
def home_data(request):
    """
    API endpoint for home page data
    """
    data = {
        'features': [
            {
                'icon': '🗺️',
                'title': 'Collaborative Planning',
                'description': 'Create trips and invite friends to plan together in real-time.'
            },
            {
                'icon': '📅',
                'title': 'Detailed Itineraries',
                'description': 'Organize day-by-day activities and locations for your trip.'
            },
            {
                'icon': '💰',
                'title': 'Expense Tracking',
                'description': 'Track group expenses and see who paid for what.'
            },
            {
                'icon': '🔒',
                'title': 'Secure Authentication',
                'description': 'Safe and secure user registration and login system.'
            }
        ],
        'stats': {
            'trips': '10K+',
            'users': '50K+',
            'countries': '100+',
            'rating': '4.9★'
        }
    }
    return Response(data)

class TripDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, trip_id):
        trip = get_object_or_404(
            Viagem.objects.prefetch_related(
                'participantes',
                'despesas__pagador'
            ),
            pk=trip_id
        )

        # Security check: User must be a participant
        if request.user not in trip.participantes.all():
             return Response({"error": "Você não tem permissão para visualizar esta viagem."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TripDashboardSerializer(trip)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, trip_id):
        trip = get_object_or_404(Viagem, pk=trip_id)
        
        # Check if user is ADMIN
        is_admin = TripMember.objects.filter(viagem=trip, user=request.user, role='ADMIN').exists()
        
        # Fallback for legacy trips (no TripMember records yet): allow if user is a participant
        if not is_admin and not TripMember.objects.filter(viagem=trip).exists():
            if request.user in trip.participantes.all():
                is_admin = True

        if not is_admin:
            return Response({"error": "Apenas administradores podem excluir a viagem."}, status=status.HTTP_403_FORBIDDEN)

        trip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, trip_id):
        trip = get_object_or_404(Viagem, pk=trip_id)
        
        # Check if user is ADMIN
        is_admin = TripMember.objects.filter(viagem=trip, user=request.user, role='ADMIN').exists()
        
        # Fallback for legacy trips
        if not is_admin and not TripMember.objects.filter(viagem=trip).exists():
            if request.user in trip.participantes.all():
                is_admin = True

        if not is_admin:
            return Response({"error": "Apenas administradores podem editar a viagem."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TripSerializer(trip, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class TripCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = TripSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            trip = serializer.save()
            trip.participantes.add(request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

User = get_user_model()


def _eh_participante(viagem, user):
    """True se o usuário participa da viagem."""
    return viagem.participantes.filter(pk=user.pk).exists()


def _sem_permissao():
    return Response(
        {"error": "Você não participa desta viagem."},
        status=status.HTTP_403_FORBIDDEN,
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_api(request, viagem_id):
    # Otimiza query com prefetch de relacionamentos
    viagem = get_object_or_404(
        Viagem.objects.prefetch_related(
            'participantes',
            'despesas__pagador',
            'despesas__rateios__participante'
        ),
        pk=viagem_id
    )
    user = request.user
    if not _eh_participante(viagem, user):
        return _sem_permissao()
    
    # 1. Calcular saldos de TODOS (para o gráfico de usuários)
    participantes = list(viagem.participantes.all())  # Converte para lista
    resumo_todos = []
    
    for p in participantes:
        # Pega apenas despesas CONFIRMADAS
        pagou = Despesa.objects.filter(viagem=viagem, pagador=p, status='CONFIRMADO').aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        consumiu = Rateio.objects.filter(despesa__viagem=viagem, despesa__status='CONFIRMADO', participante=p).aggregate(Sum('valor_devido'))['valor_devido__sum'] or 0
        saldo_calculado = float(pagou - consumiu)
        
        avatar_url = None
        if p.avatar:
            avatar_url = request.build_absolute_uri(p.avatar.url)

        resumo_todos.append({
            'id': p.id,
            'nome': p.full_name or p.email.split('@')[0],
            'saldo': saldo_calculado,
            'avatar': avatar_url

        })

    # 2. Calcular Totais do USUÁRIO LOGADO (Para os cards do topo)
    # Quanto EU tenho a receber (meu saldo positivo) ou pagar (meu saldo negativo)
    meu_saldo_obj = next((item for item in resumo_todos if item['id'] == user.id), None)
    meu_saldo = meu_saldo_obj['saldo'] if meu_saldo_obj else 0

    # Lógica de negócio: 
    # Total a Receber = Soma dos saldos positivos de quem me deve (simplificado pelo saldo geral)
    # Total a Pagar = Meu saldo se for negativo
    
    # 3. Lista de Despesas (Incluindo Rascunhos se for o dono)
    despesas_qs = Despesa.objects.filter(viagem=viagem).order_by('-data', '-id')
    lista_despesas = []
    for d in despesas_qs:
        # Só mostra rascunho se for o dono
        if d.status == 'RASCUNHO' and d.pagador != user:
            continue
            
        lista_despesas.append({
            'id': d.id,
            'titulo': d.titulo,
            'valor': float(d.valor_total),
            'pagador': d.pagador.full_name or d.pagador.email.split('@')[0],
            'pagador_id': d.pagador.id,
            'data': d.data.strftime('%Y-%m-%d'),
            'status': d.status
        })

    return JsonResponse({
        'meta': {
            'titulo': viagem.titulo,
            'data': viagem.data_inicio.strftime('%d %b') if hasattr(viagem, 'data_inicio') and viagem.data_inicio else ""
        },
        # ADICIONE ESTA LINHA:
        'current_user_id': request.user.id, 
        
        'user_stats': {
            'a_receber': meu_saldo if meu_saldo > 0 else 0,
            'a_pagar': abs(meu_saldo) if meu_saldo < 0 else 0,
            'saldo_geral': meu_saldo
        },
        'resumo': resumo_todos,
        'despesas': lista_despesas
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_despesa_api(request, viagem_id):
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    if not _eh_participante(viagem, request.user):
        return _sem_permissao()
    try:
        data = request.data
        status = data.get('status', 'CONFIRMADO') # Recebe o status (Rascunho ou não)

        with transaction.atomic():
            pagador = get_object_or_404(viagem.participantes, pk=data['pagador_id'])
            nova_despesa = Despesa.objects.create(
                viagem=viagem,
                pagador=pagador,
                titulo=data['titulo'],
                valor_total=data['valor_total'],
                data=data['data'],
                status=status # Salva o status
            )

            # Só cria rateios se não for rascunho ou se tiver dados
            rateios_data = data.get('rateios', [])
            for r in rateios_data:
                participante = get_object_or_404(viagem.participantes, pk=r['user_id'])
                Rateio.objects.create(
                    despesa=nova_despesa,
                    participante=participante,
                    valor_devido=r['valor']
                )

        return JsonResponse({'message': 'Salvo!', 'id': nova_despesa.id}, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def liquidar_divida_api(request, viagem_id):
    """
    Registra um pagamento direto (reembolso) entre duas pessoas para quitar dívida.
    """
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    if not _eh_participante(viagem, request.user):
        return _sem_permissao()

    try:
        data = request.data
        devedor_id = data.get('devedor_id')  # Quem está pagando (ex: Ana)
        credor_id = data.get('credor_id')    # Quem está recebendo (ex: Bruno)
        valor = float(data.get('valor'))

        with transaction.atomic():
            # Cria uma despesa especial do tipo "ACERTO"
            devedor = get_object_or_404(viagem.participantes, pk=devedor_id)
            credor = get_object_or_404(viagem.participantes, pk=credor_id)

            nova_despesa = Despesa.objects.create(
                viagem=viagem,
                pagador=devedor,
                titulo=f"Acerto: {devedor.full_name} pagou {credor.full_name}",
                valor_total=valor,
                categoria='OUTROS', # Poderia criar uma categoria REEMBOLSO
                data=timezone.now().date()
            )

            # O Credor é o único "beneficiário" dessa despesa, pois ele recebeu o dinheiro
            Rateio.objects.create(
                despesa=nova_despesa,
                participante=credor,
                valor_devido=valor
            )

        return JsonResponse({'message': 'Dívida quitada com sucesso!'}, status=201)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_viagens_api(request):
    # Filtra apenas as viagens do usuário logado com otimizações
    viagens = Viagem.objects.filter(
        participantes=request.user
    ).prefetch_related(
        'participantes'  # Carrega participantes em uma única query
    ).annotate(
        participantes_count_cached=models.Count('participantes')  # Conta sem query adicional
    ).order_by('-id')
    
    data = []
    hoje = date.today()

    for v in viagens:
        status = 'PLANEJAMENTO'
        status_display = 'Em Planejamento'
        
        if v.data_inicio and v.data_inicio < hoje:
            status = 'CONCLUIDA'
            status_display = 'Concluída'

        # Busca participantes com avatares (já carregados via prefetch_related)
        participantes_list = list(v.participantes.all()[:5])  # Converte para lista para evitar re-query
        participantes_data = []
        for p in participantes_list:

            avatar_url = None
            if p.avatar:
                avatar_url = request.build_absolute_uri(p.avatar.url)
            participantes_data.append({
                'id': p.id,
                'name': p.full_name or p.email,
                'avatar': avatar_url
            })
        
        # --- CORREÇÃO DA IMAGEM AQUI ---
        imagem_url = None
        if v.imagem:
            # request.build_absolute_uri cria a URL completa (http://localhost:8000/media/...)
            imagem_url = v.imagem.url 

        data.append({
            'id': v.id,
            'titulo': v.titulo,
            'destino': v.destino if hasattr(v, 'destino') else None,
            'data': v.data_inicio.strftime('%d %b') if hasattr(v, 'data_inicio') and v.data_inicio else "Data a definir",
            'data_inicio': v.data_inicio.isoformat() if v.data_inicio else None,
            'data_fim': v.data_fim.isoformat() if v.data_fim else None,
            'participantes_count': v.participantes_count_cached,  # Usa o valor anotado
            'participantes': participantes_data,
            'status': status,
            'status_display': status_display,
            'imagem': imagem_url  # <--- ADICIONE ESTA LINHA
        })
    
    return Response(data)


# ===== VIEWS PARA SUGESTÕES =====

class ListarCriarSugestoesView(APIView):
    """
    GET: Listar todas as sugestões de uma viagem
    POST: Criar nova sugestão
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, tripId):
        viagem = get_object_or_404(Viagem, pk=tripId)
        
        # Verificar se o usuário é participante da viagem
        if request.user not in viagem.participantes.all():
            return Response(
                {'error': 'Você não é participante desta viagem'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        sugestoes = Sugestao.objects.filter(viagem=viagem)
        serializer = SugestaoSerializer(
            sugestoes, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def post(self, request, tripId):
        viagem = get_object_or_404(Viagem, pk=tripId)
        
        # Verificar se o usuário é participante da viagem
        if request.user not in viagem.participantes.all():
            return Response(
                {'error': 'Você não é participante desta viagem'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        data['viagem'] = viagem.id

        serializer = SugestaoSerializer(data=data, context={'request': request})

        if serializer.is_valid():
            # SALVA manualmente autor e viagem (isso resolve o erro)
            sugestao = serializer.save(
                autor=request.user,
                viagem=viagem
            )
            return Response(SugestaoSerializer(sugestao).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class DetalheEditarDeleteSugestaoView(APIView):
    """
    GET: Detalhe de uma sugestão
    PATCH: Editar sugestão (apenas autor)
    DELETE: Deletar sugestão (apenas autor)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, tripId, sugestaoId):
        viagem = get_object_or_404(Viagem, pk=tripId)
        sugestao = get_object_or_404(Sugestao, pk=sugestaoId, viagem=viagem)
        
        # Verificar se o usuário é participante da viagem
        if request.user not in viagem.participantes.all():
            return Response(
                {'error': 'Você não é participante desta viagem'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SugestaoSerializer(sugestao, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, tripId, sugestaoId):
        viagem = get_object_or_404(Viagem, pk=tripId)
        sugestao = get_object_or_404(Sugestao, pk=sugestaoId, viagem=viagem)
        
        # Verificar se o usuário é o autor
        if sugestao.autor != request.user:
            return Response(
                {'error': 'Apenas o autor pode editar esta sugestão'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SugestaoSerializer(
            sugestao, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, tripId, sugestaoId):
        viagem = get_object_or_404(Viagem, pk=tripId)
        sugestao = get_object_or_404(Sugestao, pk=sugestaoId, viagem=viagem)
        
        # Verificar se o usuário é o autor
        if sugestao.autor != request.user:
            return Response(
                {'error': 'Apenas o autor pode deletar esta sugestão'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        sugestao.delete()
        return Response(
            {'message': 'Sugestão deletada com sucesso'},
            status=status.HTTP_204_NO_CONTENT
        )


class VotarSugestaoView(APIView):
    """
    POST: Votar em uma sugestão (adiciona ou remove voto)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, tripId, sugestaoId):
        viagem = get_object_or_404(Viagem, pk=tripId)
        sugestao = get_object_or_404(Sugestao, pk=sugestaoId, viagem=viagem)
        
        # Verificar se o usuário é participante da viagem
        if request.user not in viagem.participantes.all():
            return Response(
                {'error': 'Você não é participante desta viagem'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar se o voto já existe
        voto = Voto.objects.filter(sugestao=sugestao, usuario=request.user).first()
        
        if voto:
            # Se já votou, remove o voto (toggle)
            voto.delete()
            votou = False
        else:
            # Se não votou, adiciona o voto
            Voto.objects.create(sugestao=sugestao, usuario=request.user)
            votou = True
        
        # Retornar o novo total de votos
        votes_count = sugestao.votos.count()
        
        return Response(
            {
                'message': 'Voto removido' if not votou else 'Voto adicionado',
                'voted': votou,
                'votes_count': votes_count
            },
            status=status.HTTP_200_OK
        )
# ===== VIEWS PARA MEMBROS E CONVITES =====
from .models import TripMember, TripInvite
from .serializers import TripMemberSerializer, TripInviteSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from django.core.mail import send_mail
from django.conf import settings as django_settings


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_membros_e_convites(request, viagem_id):
    """Lista todos os membros e convites pendentes de uma viagem"""
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    
    # Verifica se o usuário é membro da viagem (TripMember OU participantes)
    is_trip_member = TripMember.objects.filter(viagem=viagem, user=request.user).exists()
    is_participant = viagem.participantes.filter(id=request.user.id).exists()
    
    if not (is_trip_member or is_participant):
        return Response({"error": "Você não tem permissão para acessar esta viagem"}, 
                       status=http_status.HTTP_403_FORBIDDEN)
    
    # Busca membros
    membros = TripMember.objects.filter(viagem=viagem).select_related('user')
    membros_data = TripMemberSerializer(membros, many=True).data
    
    # Busca convites pendentes
    convites = TripInvite.objects.filter(viagem=viagem, status='PENDING').order_by('-created_at')
    convites_data = TripInviteSerializer(convites, many=True).data
    
    # Verifica se o usuário atual é admin
    user_member = TripMember.objects.filter(viagem=viagem, user=request.user).first()
    is_admin = user_member.role == 'ADMIN' if user_member else False
    
    return Response({
        'members': membros_data,
        'invites': convites_data,
        'is_admin': is_admin,
        'trip_info': {
            'id': viagem.id,
            'title': viagem.titulo,
            'date_range': f"{viagem.data_inicio.strftime('%d-%m')} {viagem.data_fim.strftime('%d %b')}" if viagem.data_inicio else ""
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enviar_convites(request, viagem_id):
    """Envia convites por email (separados por vírgula)"""
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    
    # Verifica se o usuário é admin
    user_member = TripMember.objects.filter(viagem=viagem, user=request.user, role='ADMIN').first()
    if not user_member:
        return Response({"error": "Apenas administradores podem enviar convites"}, 
                       status=http_status.HTTP_403_FORBIDDEN)
    
    emails_string = request.data.get('emails', '')
    emails = [e.strip() for e in emails_string.split(',') if e.strip()]
    
    if not emails:
        return Response({"error": "Nenhum email fornecido"}, status=http_status.HTTP_400_BAD_REQUEST)
    
    convites_criados = []
    erros = []
    
    for email in emails:
        # Verifica se já é membro
        if User.objects.filter(email=email, viagens=viagem).exists():
            erros.append(f"{email} já é membro da viagem")
            continue
        
        # Verifica se já tem convite pendente
        if TripInvite.objects.filter(viagem=viagem, email=email, status='PENDING').exists():
            erros.append(f"{email} já tem um convite pendente")
            continue
        
        # Cria o convite
        convite = TripInvite.objects.create(
            viagem=viagem,
            email=email,
            invited_by=request.user
        )
        
        # Envia email (simplificado - em produção usar templates)
        try:
            link_convite = f"{django_settings.FRONTEND_URL}/join/{convite.token}"
            send_mail(
                subject=f"Convite para {viagem.titulo}",
                message=f"Você foi convidado para participar da viagem {viagem.titulo}. Acesse: {link_convite}",
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            convites_criados.append(email)
        except Exception as e:
            erros.append(f"{email}: Erro ao enviar email - {str(e)}")
    
    return Response({
        'message': f'{len(convites_criados)} convite(s) enviado(s)',
        'convites_criados': convites_criados,
        'erros': erros
    }, status=http_status.HTTP_201_CREATED if convites_criados else http_status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reenviar_convite(request, viagem_id, convite_id):
    """Reenvia um convite"""
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    convite = get_object_or_404(TripInvite, pk=convite_id, viagem=viagem)
    
    # Verifica se o usuário é admin
    user_member = TripMember.objects.filter(viagem=viagem, user=request.user, role='ADMIN').first()
    if not user_member:
        return Response({"error": "Apenas administradores podem reenviar convites"}, 
                       status=http_status.HTTP_403_FORBIDDEN)
    
    # Atualiza data de expiração
    convite.expires_at = timezone.now() + timedelta(days=7)
    convite.save()
    
    # Reenvia email
    try:
        link_convite = f"{django_settings.FRONTEND_URL}/join/{convite.token}"
        send_mail(
            subject=f"Lembrete: Convite para {viagem.titulo}",
            message=f"Lembrete: Você foi convidado para {viagem.titulo}. Acesse: {link_convite}",
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[convite.email],
            fail_silently=False,
        )
        return Response({"message": "Convite reenviado com sucesso"})
    except Exception as e:
        return Response({"error": f"Erro ao enviar email: {str(e)}"}, 
                       status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cancelar_convite(request, viagem_id, convite_id):
    """Cancela um convite pendente"""
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    convite = get_object_or_404(TripInvite, pk=convite_id, viagem=viagem)
    
    # Verifica se o usuário é admin
    user_member = TripMember.objects.filter(viagem=viagem, user=request.user, role='ADMIN').first()
    if not user_member:
        return Response({"error": "Apenas administradores podem cancelar convites"}, 
                       status=http_status.HTTP_403_FORBIDDEN)
    
    convite.status = 'CANCELLED'
    convite.save()
    
    return Response({"message": "Convite cancelado"}, status=http_status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def alternar_admin(request, viagem_id, membro_id):
    """Promove ou remove permissão de admin de um membro"""
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    membro = get_object_or_404(TripMember, pk=membro_id, viagem=viagem)
    
    # Verifica se o usuário é admin
    user_member = TripMember.objects.filter(viagem=viagem, user=request.user, role='ADMIN').first()
    if not user_member:
        return Response({"error": "Apenas administradores podem alterar permissões"}, 
                       status=http_status.HTTP_403_FORBIDDEN)
    
    # Impede que o criador perca o admin
    primeiro_admin = viagem.members.filter(role='ADMIN').order_by('joined_at').first()
    if membro == primeiro_admin and membro.role == 'ADMIN':
        return Response({"error": "O criador da viagem não pode perder permissões de admin"}, 
                       status=http_status.HTTP_400_BAD_REQUEST)
    
    # Alterna o role
    membro.role = 'MEMBER' if membro.role == 'ADMIN' else 'ADMIN'
    membro.save()
    
    return Response({
        "message": f"Usuário {'promovido a admin' if membro.role == 'ADMIN' else 'removido de admin'}",
        "new_role": membro.role
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remover_membro(request, viagem_id, membro_id):
    """Remove um membro da viagem"""
    viagem = get_object_or_404(Viagem, pk=viagem_id)
    membro = get_object_or_404(TripMember, pk=membro_id, viagem=viagem)
    
    # Verifica se o usuário é admin
    user_member = TripMember.objects.filter(viagem=viagem, user=request.user, role='ADMIN').first()
    if not user_member:
        return Response({"error": "Apenas administradores podem remover membros"}, 
                       status=http_status.HTTP_403_FORBIDDEN)
    
    # Impede remover o criador
    primeiro_admin = viagem.members.filter(role='ADMIN').order_by('joined_at').first()
    if membro == primeiro_admin:
        return Response({"error": "O criador da viagem não pode ser removido"}, 
                       status=http_status.HTTP_400_BAD_REQUEST)
    
    # Remove da tabela de membros e da relação ManyToMany
    user_to_remove = membro.user
    membro.delete()
    viagem.participantes.remove(user_to_remove)
    
    return Response({"message": "Membro removido com sucesso"}, status=http_status.HTTP_200_OK)
