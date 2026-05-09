#!/usr/bin/env python3
"""
Haken SaaS - API de Asistencia Móvil
=====================================
API REST para registro de asistencia desde dispositivos móviles.
Soporta múltiples métodos de fichaje:
- GPS con geofencing
- Código QR
- Slack/LINE bot
- IC Card (via webhook)
"""

import json
import math
from dataclasses import dataclass
from datetime import datetime, date
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════


@dataclass
class GeofenceLocation:
    """Ubicación para geofencing."""

    id: str
    name: str  # Nombre del sitio
    latitude: float  # 緯度
    longitude: float  # 経度
    radius_meters: int = 100  # Radio de detección


@dataclass
class ClockRecord:
    """Registro de fichaje."""

    id: str
    worker_id: str
    placement_id: str
    timestamp: datetime
    clock_type: str  # in / out
    method: str  # gps, qr, slack, line, manual
    latitude: float | None = None
    longitude: float | None = None
    location_name: str = ""
    verified: bool = False
    verification_notes: str = ""
    ip_address: str = ""
    device_info: str = ""


class AttendanceStore:
    """Almacén de registros de asistencia (en memoria para demo)."""

    def __init__(self):
        self.records: dict[str, ClockRecord] = {}
        self.geofences: dict[str, GeofenceLocation] = {}

    def add_record(self, record: ClockRecord) -> None:
        self.records[record.id] = record

    def get_worker_records(self, worker_id: str, work_date: date) -> list[ClockRecord]:
        """Obtiene registros de un trabajador para una fecha."""
        return [
            r
            for r in self.records.values()
            if r.worker_id == worker_id and r.timestamp.date() == work_date
        ]

    def add_geofence(self, location: GeofenceLocation) -> None:
        self.geofences[location.id] = location


# ═══════════════════════════════════════════════════════════════
# UTILIDADES DE GEOLOCALIZACIÓN
# ═══════════════════════════════════════════════════════════════


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia entre dos puntos usando la fórmula de Haversine.
    Retorna distancia en metros.
    """
    R = 6371000  # Radio de la Tierra en metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def check_geofence(
    lat: float, lon: float, geofences: dict[str, GeofenceLocation]
) -> GeofenceLocation | None:
    """
    Verifica si una ubicación está dentro de algún geofence.
    """
    for fence in geofences.values():
        distance = haversine_distance(lat, lon, fence.latitude, fence.longitude)
        if distance <= fence.radius_meters:
            return fence
    return None


# ═══════════════════════════════════════════════════════════════
# SERVICIO DE ASISTENCIA
# ═══════════════════════════════════════════════════════════════


class AttendanceService:
    """Servicio de gestión de asistencia."""

    def __init__(self, store: AttendanceStore):
        self.store = store

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 📍 {message}")

    def clock_in_gps(
        self,
        worker_id: str,
        placement_id: str,
        latitude: float,
        longitude: float,
        device_info: str = "",
    ) -> dict:
        """
        Registra entrada via GPS.
        """
        # Verificar geofence
        location = check_geofence(latitude, longitude, self.store.geofences)

        record_id = f"CLK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{worker_id[-4:]}"

        record = ClockRecord(
            id=record_id,
            worker_id=worker_id,
            placement_id=placement_id,
            timestamp=datetime.now(),
            clock_type="in",
            method="gps",
            latitude=latitude,
            longitude=longitude,
            location_name=location.name if location else "位置未確認",
            verified=location is not None,
            verification_notes="" if location else "GPS fuera del área de trabajo",
            device_info=device_info,
        )

        self.store.add_record(record)

        self.log(f"Clock-IN (GPS): {worker_id} @ {record.location_name}")

        return {
            "success": True,
            "record_id": record_id,
            "timestamp": record.timestamp.isoformat(),
            "location_verified": record.verified,
            "location_name": record.location_name,
            "message": "出勤を記録しました"
            if record.verified
            else "出勤を記録しました（位置確認要）",
        }

    def clock_out_gps(
        self,
        worker_id: str,
        placement_id: str,
        latitude: float,
        longitude: float,
        device_info: str = "",
    ) -> dict:
        """
        Registra salida via GPS.
        """
        location = check_geofence(latitude, longitude, self.store.geofences)

        record_id = f"CLK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{worker_id[-4:]}"

        record = ClockRecord(
            id=record_id,
            worker_id=worker_id,
            placement_id=placement_id,
            timestamp=datetime.now(),
            clock_type="out",
            method="gps",
            latitude=latitude,
            longitude=longitude,
            location_name=location.name if location else "位置未確認",
            verified=location is not None,
            device_info=device_info,
        )

        self.store.add_record(record)

        # Calcular horas trabajadas
        today_records = self.store.get_worker_records(worker_id, date.today())
        clock_in = next((r for r in today_records if r.clock_type == "in"), None)

        hours_worked = None
        if clock_in:
            delta = record.timestamp - clock_in.timestamp
            hours_worked = delta.total_seconds() / 3600

        self.log(f"Clock-OUT (GPS): {worker_id} @ {record.location_name}")

        return {
            "success": True,
            "record_id": record_id,
            "timestamp": record.timestamp.isoformat(),
            "location_verified": record.verified,
            "hours_worked": round(hours_worked, 2) if hours_worked else None,
            "message": "退勤を記録しました",
        }

    def clock_qr(
        self,
        worker_id: str,
        qr_code: str,
    ) -> dict:
        """
        Registra entrada/salida via código QR.
        El QR contiene: placement_id:location_id:timestamp_hash
        """
        try:
            parts = qr_code.split(":")
            if len(parts) < 2:
                return {"success": False, "error": "QRコードが無効です"}

            placement_id = parts[0]
            location_id = parts[1]

            # Determinar si es entrada o salida
            today_records = self.store.get_worker_records(worker_id, date.today())
            clock_type = "out" if any(r.clock_type == "in" for r in today_records) else "in"

            location = self.store.geofences.get(location_id)

            record_id = f"CLK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{worker_id[-4:]}"

            record = ClockRecord(
                id=record_id,
                worker_id=worker_id,
                placement_id=placement_id,
                timestamp=datetime.now(),
                clock_type=clock_type,
                method="qr",
                location_name=location.name if location else "QR打刻",
                verified=True,
            )

            self.store.add_record(record)

            self.log(f"Clock-{clock_type.upper()} (QR): {worker_id}")

            return {
                "success": True,
                "record_id": record_id,
                "clock_type": clock_type,
                "timestamp": record.timestamp.isoformat(),
                "message": "出勤を記録しました" if clock_type == "in" else "退勤を記録しました",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def clock_slack(
        self,
        slack_user_id: str,
        command: str,
    ) -> dict:
        """
        Procesa comando de Slack para fichaje.
        Comandos: /clock-in, /clock-out, /status
        """
        # Mapear Slack user a worker_id (en producción, consultar DB)
        worker_id = f"W-{slack_user_id[:8]}"

        if command == "/clock-in" or command == "in" or command == "出勤":
            record_id = f"CLK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{worker_id[-4:]}"

            record = ClockRecord(
                id=record_id,
                worker_id=worker_id,
                placement_id="",
                timestamp=datetime.now(),
                clock_type="in",
                method="slack",
                verified=True,
            )

            self.store.add_record(record)

            return {
                "response_type": "ephemeral",
                "text": f"✅ 出勤を記録しました\n時刻: {record.timestamp.strftime('%H:%M')}\nID: {record_id}",
            }

        elif command == "/clock-out" or command == "out" or command == "退勤":
            record_id = f"CLK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{worker_id[-4:]}"

            record = ClockRecord(
                id=record_id,
                worker_id=worker_id,
                placement_id="",
                timestamp=datetime.now(),
                clock_type="out",
                method="slack",
                verified=True,
            )

            self.store.add_record(record)

            # Calcular horas
            today_records = self.store.get_worker_records(worker_id, date.today())
            clock_in = next((r for r in today_records if r.clock_type == "in"), None)

            hours_text = ""
            if clock_in:
                delta = record.timestamp - clock_in.timestamp
                hours = delta.total_seconds() / 3600
                hours_text = f"\n勤務時間: {hours:.2f}時間"

            return {
                "response_type": "ephemeral",
                "text": f"✅ 退勤を記録しました\n時刻: {record.timestamp.strftime('%H:%M')}{hours_text}",
            }

        elif command == "/status" or command == "status" or command == "状態":
            today_records = self.store.get_worker_records(worker_id, date.today())

            if not today_records:
                return {
                    "response_type": "ephemeral",
                    "text": "📋 本日の打刻記録はありません",
                }

            records_text = "\n".join(
                [
                    f"• {r.clock_type.upper()}: {r.timestamp.strftime('%H:%M')} ({r.method})"
                    for r in today_records
                ]
            )

            return {
                "response_type": "ephemeral",
                "text": f"📋 本日の打刻記録:\n{records_text}",
            }

        return {
            "response_type": "ephemeral",
            "text": "❓ コマンドが認識できません。/clock-in, /clock-out, /status を使用してください。",
        }

    def get_daily_summary(self, worker_id: str, work_date: date) -> dict:
        """Obtiene resumen diario de asistencia."""
        records = self.store.get_worker_records(worker_id, work_date)

        if not records:
            return {
                "date": work_date.isoformat(),
                "worker_id": worker_id,
                "status": "no_record",
                "records": [],
            }

        clock_in = next((r for r in records if r.clock_type == "in"), None)
        clock_out = next((r for r in reversed(records) if r.clock_type == "out"), None)

        hours_worked = None
        if clock_in and clock_out:
            delta = clock_out.timestamp - clock_in.timestamp
            hours_worked = delta.total_seconds() / 3600

        return {
            "date": work_date.isoformat(),
            "worker_id": worker_id,
            "status": "complete" if clock_in and clock_out else "incomplete",
            "clock_in": clock_in.timestamp.isoformat() if clock_in else None,
            "clock_out": clock_out.timestamp.isoformat() if clock_out else None,
            "hours_worked": round(hours_worked, 2) if hours_worked else None,
            "records": [
                {
                    "id": r.id,
                    "type": r.clock_type,
                    "time": r.timestamp.isoformat(),
                    "method": r.method,
                    "verified": r.verified,
                }
                for r in records
            ],
        }


# ═══════════════════════════════════════════════════════════════
# API HTTP SERVER
# ═══════════════════════════════════════════════════════════════


class AttendanceAPIHandler(BaseHTTPRequestHandler):
    """Handler para API REST de asistencia."""

    service: AttendanceService = None

    def log_message(self, format, *args):
        """Override para usar nuestro formato de log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 🌐 API: {args[0]}")

    def send_json(self, data: dict, status: int = 200):
        """Envía respuesta JSON."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/health":
            self.send_json({"status": "ok", "service": "attendance-api"})

        elif path == "/api/summary":
            worker_id = params.get("worker_id", [""])[0]
            date_str = params.get("date", [date.today().isoformat()])[0]
            work_date = date.fromisoformat(date_str)

            summary = self.service.get_daily_summary(worker_id, work_date)
            self.send_json(summary)

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/clock/gps":
            clock_type = data.get("type", "in")
            worker_id = data.get("worker_id")
            placement_id = data.get("placement_id", "")
            lat = data.get("latitude")
            lon = data.get("longitude")
            device = data.get("device_info", "")

            if not all([worker_id, lat, lon]):
                self.send_json({"error": "Missing required fields"}, 400)
                return

            if clock_type == "in":
                result = self.service.clock_in_gps(worker_id, placement_id, lat, lon, device)
            else:
                result = self.service.clock_out_gps(worker_id, placement_id, lat, lon, device)

            self.send_json(result)

        elif path == "/api/clock/qr":
            worker_id = data.get("worker_id")
            qr_code = data.get("qr_code")

            if not all([worker_id, qr_code]):
                self.send_json({"error": "Missing required fields"}, 400)
                return

            result = self.service.clock_qr(worker_id, qr_code)
            self.send_json(result)

        elif path == "/api/slack/command":
            # Slack command webhook
            user_id = data.get("user_id")
            command = data.get("command") or data.get("text", "")

            result = self.service.clock_slack(user_id, command)
            self.send_json(result)

        elif path == "/api/line/webhook":
            # LINE Bot webhook
            events = data.get("events", [])
            for event in events:
                if event.get("type") == "message":
                    user_id = event.get("source", {}).get("userId", "")
                    text = event.get("message", {}).get("text", "")
                    result = self.service.clock_slack(user_id, text)  # Reusar lógica

            self.send_json({"status": "ok"})

        else:
            self.send_json({"error": "Not found"}, 404)


def run_server(host: str = "0.0.0.0", port: int = 8081):
    """Inicia el servidor de API."""
    # Inicializar servicio
    store = AttendanceStore()

    # Agregar geofences de ejemplo
    store.add_geofence(
        GeofenceLocation(
            id="LOC001",
            name="加藤木材株式会社",
            latitude=35.0853,
            longitude=136.8803,
            radius_meters=100,
        )
    )
    store.add_geofence(
        GeofenceLocation(
            id="LOC002",
            name="トヨタ自動車 豊田本社",
            latitude=35.0533,
            longitude=137.1572,
            radius_meters=200,
        )
    )

    service = AttendanceService(store)
    AttendanceAPIHandler.service = service

    server = HTTPServer((host, port), AttendanceAPIHandler)

    print("\n📍 ATTENDANCE API SERVER")
    print("=" * 50)
    print(f"URL: http://{host}:{port}")
    print(f"Geofences configurados: {len(store.geofences)}")
    print("\nEndpoints:")
    print("  GET  /health           - Health check")
    print("  GET  /api/summary      - Resumen diario")
    print("  POST /api/clock/gps    - Fichaje GPS")
    print("  POST /api/clock/qr     - Fichaje QR")
    print("  POST /api/slack/command- Webhook Slack")
    print("  POST /api/line/webhook - Webhook LINE")
    print("\nPresiona Ctrl+C para detener...")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido")
        server.shutdown()


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="API de Asistencia Móvil - Haken SaaS")

    subparsers = parser.add_subparsers(dest="command")

    # Server
    server_parser = subparsers.add_parser("serve", help="Iniciar servidor API")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host")
    server_parser.add_argument("--port", type=int, default=8081, help="Puerto")

    # Test
    test_parser = subparsers.add_parser("test", help="Probar fichaje")
    test_parser.add_argument("--worker", required=True, help="ID del trabajador")
    test_parser.add_argument("--type", choices=["in", "out"], default="in")
    test_parser.add_argument("--lat", type=float, default=35.0853)
    test_parser.add_argument("--lon", type=float, default=136.8803)

    args = parser.parse_args()

    if args.command == "serve":
        run_server(args.host, args.port)

    elif args.command == "test":
        store = AttendanceStore()
        store.add_geofence(
            GeofenceLocation(
                id="LOC001",
                name="Test Location",
                latitude=35.0853,
                longitude=136.8803,
                radius_meters=100,
            )
        )

        service = AttendanceService(store)

        if args.type == "in":
            result = service.clock_in_gps(args.worker, "P001", args.lat, args.lon)
        else:
            result = service.clock_out_gps(args.worker, "P001", args.lat, args.lon)

        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
