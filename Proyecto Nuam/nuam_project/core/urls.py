# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Ruta principal del mantenedor
    path('mantenedor/', views.mantenedor_view, name='mantenedor'),
    
    # Rutas básicas de autenticación (para simplificar, usaremos las que trae Django)
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('carga-masiva/', views.carga_masiva_view, name='carga_masiva'),
]