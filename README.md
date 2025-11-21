# Baston-Inteligente
Crea un repositorio en GitHub y sube la carpeta baston-inteligente con app.py, templates/, requirements.txt, Procfile.

En Render:

Nuevo → Web Service

Conectar con tu repo de GitHub

Branch: main

Environment: Python (o autodetect)

Build command: pip install -r requirements.txt

Start command: gunicorn app:app

Render construirá y te dará la URL fija: https://tu-proyecto.onrender.com

Ajusta el firmware del ESP32 para enviar a https://tu-proyecto.onrender.com/data y https://tu-proyecto.onrender.com/cam (con X-API-Key: baston123).
