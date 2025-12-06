# nuam_project/urls.py

from django.contrib import admin
from django.urls import path, include
from core.views import mantenedor_redirect # Importación nueva

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Incluir las URLs de la app 'core'
    path('', include('core.urls')),
    
    # 2. Redirigir la raíz del sitio (/) a la página de login o al mantenedor
    path('', mantenedor_redirect, name='home'), 
]