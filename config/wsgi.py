"""
Punto de entrada WSGI para servidores de producción (PythonAnywhere, gunicorn).
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
