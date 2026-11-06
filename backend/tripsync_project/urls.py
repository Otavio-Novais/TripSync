"""
URL configuration for tripsync_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static

# Função API Root (Documentação simples da API)
def api_root(request):
    return JsonResponse({
        'message': 'TripSync API',
        'version': '1.0',
        'endpoints': {
            'auth': '/api/auth/',
            'planner': '/planner/api/',
            'admin': '/admin/',
        },
        'status': 'running'
    })

urlpatterns = [
    # Rota Raiz (Retorna o JSON acima)
    path('', api_root, name='api_root'),
    
    # Rota Admin
    path('admin/', admin.site.urls),

    # Rotas de Autenticação (Accounts)
    path('api/auth/', include('accounts.urls')), 
    
    # Rotas do Planner (viagens, finanças, sugestões e membros)
    path('planner/api/', include('planner.urls')), 
]

# Configuração de arquivos de mídia (apenas em DEBUG)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
