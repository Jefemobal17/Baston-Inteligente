import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from datetime import datetime
from pathlib import Path

# CONFIG
API_KEY = "baston123"
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
DB_PATH = "database.db"

app = Flask(__name__, template_folder="templates")
CORS(app)

# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabla con campos GPS agregados
    c.execute('''
        CREATE TABLE IF NOT EXISTS distancia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valor REAL,
            alerta INTEGER,
            latitud REAL,
            longitud REAL,
            satelites INTEGER,
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

def insert_distancia(valor, alerta, latitud=None, longitud=None, satelites=0):
    ts = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO distancia (valor, alerta, latitud, longitud, satelites, timestamp) 
        VALUES (?,?,?,?,?,?)
    ''', (valor, int(bool(alerta)), latitud, longitud, satelites, ts))
    conn.commit()
    conn.close()

def get_last_distancia():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT valor, alerta, latitud, longitud, satelites, timestamp 
        FROM distancia ORDER BY id DESC LIMIT 1
    ''')
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "distancia": row[0], 
            "alerta": bool(row[1]), 
            "latitud": row[2],
            "longitud": row[3],
            "satelites": row[4],
            "tiempo": row[5]
        }
    else:
        return {
            "distancia": 0, 
            "alerta": False, 
            "latitud": None,
            "longitud": None,
            "satelites": 0,
            "tiempo": None
        }

def get_historial(limit=100):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT valor, alerta, latitud, longitud, satelites, timestamp 
        FROM distancia ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{
        "distancia": r[0], 
        "alerta": bool(r[1]), 
        "latitud": r[2],
        "longitud": r[3],
        "satelites": r[4],
        "tiempo": r[5]
    } for r in rows]

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

# ESP32 -> envía JSON con distancia + GPS
@app.route('/data', methods=['POST'])
def recibir_datos():
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({"error": "API Key inválida"}), 403

    data = request.get_json(force=True)
    distancia = float(data.get('distancia', 0))
    alerta = bool(data.get('alerta', False))
    
    # Nuevos campos GPS
    latitud = data.get('latitud')
    longitud = data.get('longitud')
    satelites = int(data.get('satelites', 0))
    
    # Convertir a float si no es None
    if latitud is not None:
        latitud = float(latitud)
    if longitud is not None:
        longitud = float(longitud)

    insert_distancia(distancia, alerta, latitud, longitud, satelites)
    
    gps_info = f"GPS:{latitud},{longitud} ({satelites}sats)" if latitud else "GPS:No disponible"
    print(f"[{datetime.utcnow().isoformat()}] Distancia:{distancia}cm alerta={alerta} {gps_info}")

    return jsonify({"status": "ok"}), 200

# ESP32-CAM -> envía imagen JPEG (binary)
@app.route('/cam', methods=['POST'])
def recibir_imagen():
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({"error": "API Key inválida"}), 403

    if 'file' in request.files:
        f = request.files['file']
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        path = UPLOAD_FOLDER / filename
        f.save(path)
    else:
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

# API estadísticas
@app.route('/api/estadisticas', methods=['GET'])
def api_estadisticas():
    historial = get_historial(limit=1000)
    total_registros = len(historial)
    total_alertas = sum(1 for h in historial if h['alerta'])
    
    distancias = [h['distancia'] for h in historial if h['distancia'] > 0]
    distancia_minima = min(distancias) if distancias else None
    distancia_maxima = max(distancias) if distancias else None
    distancia_promedio = round(sum(distancias) / len(distancias), 1) if distancias else None
    
    registros_con_gps = sum(1 for h in historial if h['latitud'] is not None and h['longitud'] is not None)
    porcentaje_gps = round((registros_con_gps / total_registros * 100), 1) if total_registros > 0 else 0
    
    return jsonify({
        'totalRegistros': total_registros,
        'totalAlertas': total_alertas,
        'distanciaMinima': distancia_minima,
        'distanciaMaxima': distancia_maxima,
        'distanciaPromedio': distancia_promedio,
        'registrosConGPS': registros_con_gps,
        'porcentajeGPS': f"{porcentaje_gps}%"
    })

# API alertas con GPS
@app.route('/api/alertas', methods=['GET'])
def api_alertas():
    historial = get_historial(limit=1000)
    alertas = [h for h in historial if h['alerta']]
    return jsonify(alertas)

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

# Limpiar historial
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

# Health check
@app.route('/health')
def health():
    ultimo = get_last_distancia()
    return jsonify({
        'status': 'ok',
        'servidor': 'Bastón Inteligente GPS',
        'ultimaActualizacion': ultimo.get('tiempo')
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Servidor iniciado en puerto {port}")
    print("📡 Esperando datos del ESP32...")
    app.run(host="0.0.0.0", port=port)
