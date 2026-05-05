import os
import json
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import pytz
import threading

app = Flask(__name__)
CORS(app)

# Veritabanı bağlantı parametreleri
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "uptime_db"),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres")
}

def get_db_connection():
    # Veritabanı bağlantı kurulumu
    return psycopg2.connect(**DB_CONFIG)

def get_siteler_from_config():
    # Yapılandırma dosyasının dinamik okunması
    config_path = "/app/config/siteler.json"
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
                siteler = data.get("siteler", [])
                print(f"✅ Yapılandırma okundu: {len(siteler)} site bulundu.")
                return siteler
        else:
            print(f"⚠️ Yapılandırma dosyası bulunamadı: {config_path}")
    except Exception as e:
        print(f"⚠️ Yapılandırma okuma hatası: {e}")
    return []

def init_db(baslangic_siteleri):
    # Veritabanı şeması ve başlangıç verilerinin hazırlanması
    print("🚀 Veritabanı katmanı hazırlanıyor...")
    retries = 10
    while retries > 0:
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS uptime_logs (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    status INTEGER,
                    checked_at TIMESTAMP,
                    response_time FLOAT
                );
                CREATE TABLE IF NOT EXISTS failure_counts (
                    url TEXT PRIMARY KEY,
                    total_failures INTEGER DEFAULT 0
                );
            """)

            for url in baslangic_siteleri:
                cur.execute("""
                    INSERT INTO failure_counts (url, total_failures)
                    VALUES (%s, 0) ON CONFLICT (url) DO NOTHING
                """, (url,))

            conn.commit()
            cur.close()
            conn.close()
            print("✅ Veritabanı ve tablolar hazır.")
            return
        except Exception as e:
            print(f"⚠️ Bağlantı denemesi başarısız, tekrar denenecek... Hata: {e}")
            retries -= 1
            time.sleep(5)
    raise Exception("❌ Veritabanına bağlanılamadı!")

def monitor_worker():
    # Periyodik izleme döngüsü
    tr_tz = pytz.timezone('Europe/Istanbul')

    while True:
        siteler = get_siteler_from_config()
        if not siteler:
            print("💤 İzlenecek site bulunamadı, 10 saniye sonra tekrar denenecek...")
            time.sleep(10)
            continue

        print(f"--- {len(siteler)} Site İçin Periyodik Kontrol Başladı ---")
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            for url in siteler:
                try:
                    now = datetime.now(tr_tz)
                    res = requests.get(url, timeout=10)
                    status = res.status_code
                    resp_time = round(res.elapsed.total_seconds(), 3)
                except Exception as e:
                    print(f"❌ {url} erişim hatası: {e}")
                    status, resp_time = 0, 0

                cur.execute(
                    "INSERT INTO uptime_logs (url, status, checked_at, response_time) VALUES (%s, %s, %s, %s)",
                    (url, status, now, resp_time)
                )

                fail_increment = 1 if status != 200 else 0
                cur.execute("""
                    INSERT INTO failure_counts (url, total_failures)
                    VALUES (%s, %s)
                    ON CONFLICT (url) DO UPDATE
                    SET total_failures = failure_counts.total_failures + EXCLUDED.total_failures
                """, (url, fail_increment))

                conn.commit()
                print(f"📡 {url} -> Durum: {status}, Süre: {resp_time}s")

            cur.close()
            conn.close()
        except Exception as e:
            print(f"💥 Worker genel hatası: {e}")

        time.sleep(10)

@app.route('/api/status', methods=['GET'])
def get_status():
    # Güncel durum verilerinin sunulması
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT DISTINCT ON (l.url)
                l.url,
                l.status,
                l.checked_at,
                l.response_time,
                COALESCE(f.total_failures, 0) as total_failures
            FROM uptime_logs l
            LEFT JOIN failure_counts f ON l.url = f.url
            ORDER BY l.url, l.checked_at DESC
        """)
        logs = cur.fetchall()
        cur.close()
        conn.close()

        for log in logs:
            if log['checked_at']:
                log['checked_at'] = log['checked_at'].strftime("%H:%M:%S")
            else:
                log['checked_at'] = "--:--:--"

        return jsonify(logs)
    except Exception as e:
        print(f"API Hatası: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Yapılandırma verilerinin yüklenmesi
    mevcut_siteler = get_siteler_from_config()

    # Veritabanı ilklendirme işlemi
    init_db(mevcut_siteler)

    # İzleme servisinin başlatılması
    t = threading.Thread(target=monitor_worker, daemon=True)
    t.start()

    # API servisinin yayına alınması
    print("🚀 Flask API 5000 portunda dinlemede...")
    app.run(host='0.0.0.0', port=5000, debug=False)
