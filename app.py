import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from datetime import datetime
from pathlib import Path

# CONFIG
API_KEY = "baston123"   # cambia si quieres
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
DB_PATH = "database.db"

app = Flask(__name__, template_folder="templates")
CORS(app)

# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS distancia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valor REAL,
            alerta INTEGER,
            timestamp TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS imagenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_distancia(valor, alerta):
    ts = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO distancia (valor, alerta, timestamp) VALUES (?,?,?)', (valor, int(bool(alerta)), ts))
    conn.commit()
    conn.close()

def get_last_distancia():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT valor, alerta, timestamp FROM distancia ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return {"distancia": row[0], "alerta": bool(row[1]), "ultima_actualizacion": row[2]}
    else:
        return {"distancia": 0, "alerta": False, "ultima_actualizacion": None}

def get_historial(limit=100):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT valor, alerta, timestamp FROM distancia ORDER BY id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"distancia": r[0], "alerta": bool(r[1]), "tiempo": r[2]} for r in rows]

def insert_imagen(filename):
    ts = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO imagenes (filename, timestamp) VALUES (?,?)', (filename, ts))
    conn.commit()
    conn.close()

def get_last_image():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT filename, timestamp FROM imagenes ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return {"filename": row[0], "timestamp": row[1]}
    return None

# init DB
init_db()

# ---------- RUTAS ----------
@app.route('/')
def index():
    return render_template("index.html")

# ESP32 normal -> envía JSON con distancia
@app.route('/data', methods=['POST'])
def recibir_datos():
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({"error": "API Key inválida"}), 403

    data = request.get_json(force=True)
    distancia = float(data.get('distancia', 0))
    alerta = bool(data.get('alerta', False))

    insert_distancia(distancia, alerta)
    print(f"[{datetime.utcnow().isoformat()}] Distancia recibida: {distancia} alerta={alerta}")

    return jsonify({"status": "ok"}), 200

# ESP32-CAM -> envía imagen JPEG (binary)
@app.route('/cam', methods=['POST'])
def recibir_imagen():
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({"error": "API Key inválida"}), 403

    # Aceptamos tanto multipart/form-data (file) como raw image/jpeg
    if 'file' in request.files:
        f = request.files['file']
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        path = UPLOAD_FOLDER / filename
        f.save(path)
    else:
        # raw body (image/jpeg)
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        path = UPLOAD_FOLDER / filename
        with open(path, "wb") as fd:
            fd.write(request.get_data())

    insert_imagen(filename)
    print(f"[{datetime.utcnow().isoformat()}] Imagen guardada: {filename}")

    return jsonify({"status": "ok", "filename": filename}), 200

# API para frontend: datos actuales
@app.route('/api/datos', methods=['GET'])
def api_datos():
    return jsonify(get_last_distancia())

# API historial
@app.route('/api/historico', methods=['GET'])
def api_historico():
    return jsonify(get_historial(limit=200))

# API ultima imagen (devuelve metadata)
@app.route('/api/last_image', methods=['GET'])
def api_last_image():
    info = get_last_image()
    if info:
        return jsonify(info)
    return jsonify({}), 204

# Servir imágenes
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(str(UPLOAD_FOLDER), filename)

# Limpiar historial (opcional)
@app.route('/api/limpiar', methods=['POST'])
def limpiar():
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({"error": "API Key inválida"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM distancia')
    c.execute('DELETE FROM imagenes')
    conn.commit()
    conn.close()
    # borrar archivos
    for p in UPLOAD_FOLDER.glob("*.jpg"):
        p.unlink(missing_ok=True)
    return jsonify({"status": "limpiado"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
