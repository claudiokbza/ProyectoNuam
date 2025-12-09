Proyecto NUAM – Sistema de Calificación Tributaria

Sistema desarrollado en Django para la gestión y control de calificaciones tributarias asociadas a instrumentos financieros y clientes.

Requisitos
-Python 3.10+
-pip
-virtualenv (recomendado)

Pasos.
1.- Clonar repositorio.
	git clone  https://github.com/claudiokbza/ProyectoNuam.git
	cd ProyectoNuam
2.- Crear entorno Virtual
-python -m venv. Venv
-  .venv\Scripts\activate

3.- Instalar dependencias.
	-pip install -r requirements.txt

4.- Crear superUsuario. (Ya está creado, no debería ser necesario crearlo)
	py manage.py createsuperuser
usuario : proyectonuam
correo	: admin01
pass	: admin01

5.-  Iniciar servidor
	-python manage.py runserver
	-http://127.0.0.1:8000/admin

Restricciones Importantes:
Evitar cambios en:
models.py
estructura de factores
claves foráneas
migraciones
Los cambios deben hacerse en:
templates/
views.py
static/
Lógica frontend



Reglas de negocio principales
La suma de factores F08 a F19 no puede ser superior a 1.0
Cada calificación debe tener un cliente asociado
Los instrumentos deben existir antes de ser usados
La carga masiva valida fila por fila


