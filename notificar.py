import os
import json
import requests
from datetime import datetime, timezone, timedelta
import google.auth.transport.requests
from google.oauth2 import service_account

# ══ CONFIGURACIÓN ══
PROJECT_ID = os.environ['FIREBASE_PROJECT_ID']
VAPID_KEY  = os.environ['VAPID_KEY']
SA_JSON    = os.environ['FIREBASE_SERVICE_ACCOUNT']

# Zona horaria Colombia (UTC-5)
COL_TZ = timezone(timedelta(hours=-5))

def get_access_token():
    """Obtener token de acceso para FCM V1"""
    sa_info = json.loads(SA_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=['https://www.googleapis.com/auth/firebase.messaging']
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

def get_tokens_firebase(token_acceso):
    """Obtener todos los tokens de dispositivos registrados"""
    url = f"https://{PROJECT_ID}-default-rtdb.firebaseio.com/tokens.json"
    headers = {"Authorization": f"Bearer {token_acceso}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Error obteniendo tokens: {resp.text}")
        return []
    data = resp.json()
    if not data:
        return []
    tokens = []
    for uid, info in data.items():
        if isinstance(info, dict) and 'token' in info:
            tokens.append(info['token'])
    return tokens

def get_partidos_firebase(token_acceso):
    """Obtener todos los partidos"""
    url = f"https://{PROJECT_ID}-default-rtdb.firebaseio.com/partidos.json"
    headers = {"Authorization": f"Bearer {token_acceso}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Error obteniendo partidos: {resp.text}")
        return {}
    return resp.json() or {}

def enviar_notificacion(token_acceso, device_token, titulo, cuerpo):
    """Enviar notificación a un dispositivo"""
    url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"
    headers = {
        "Authorization": f"Bearer {token_acceso}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": {
            "token": device_token,
            "notification": {
                "title": titulo,
                "body": cuerpo
            },
            "webpush": {
                "notification": {
                    "title": titulo,
                    "body": cuerpo,
                    "icon": "/icon-192.png",
                    "badge": "/icon-192.png",
                    "vibrate": [200, 100, 200]
                },
                "fcm_options": {
                    "link": "https://pollamundialcanm26.netlify.app"
                }
            }
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    return resp.status_code == 200

def main():
    print(f"🕐 Revisando partidos — {datetime.now(COL_TZ).strftime('%Y-%m-%d %H:%M')} Colombia")

    # Obtener token de acceso
    token_acceso = get_access_token()

    # Obtener partidos y tokens
    partidos = get_partidos_firebase(token_acceso)
    tokens   = get_tokens_firebase(token_acceso)

    if not tokens:
        print("⚠️ No hay dispositivos registrados para notificaciones")
        return

    print(f"📱 Dispositivos registrados: {len(tokens)}")

    # Hora actual en Colombia
    ahora = datetime.now(COL_TZ)

    notificaciones_enviadas = 0

    for pid, p in partidos.items():
        # Solo partidos no finalizados
        if p.get('estado') in ['Finalizado', 'Resultado confirmado']:
            continue

        # Construir datetime del cierre en ET y convertir a Colombia
        try:
            cierre_str = p.get('cierre', '')
            if not cierre_str:
                continue

            # Cierre está en ET (UTC-4 en verano)
            ET_TZ = timezone(timedelta(hours=-4))
            cierre_et = datetime.strptime(cierre_str, '%Y-%m-%d %H:%M')
            cierre_et = cierre_et.replace(tzinfo=ET_TZ)

            # Convertir a Colombia
            cierre_col = cierre_et.astimezone(COL_TZ)

            # ¿El cierre es en los próximos 10-15 minutos?
            diff = (cierre_col - ahora).total_seconds() / 60  # diferencia en minutos

            if 9 <= diff <= 15:  # ventana de 9 a 15 minutos antes del cierre
                local   = p.get('local', '')
                visita  = p.get('visita', '')
                grupo   = p.get('grupo', '')
                hora_col = cierre_col.strftime('%I:%M %p')

                titulo = f"⚽ ¡Cierra en {int(diff)} min!"
                cuerpo = f"{local} vs {visita} — Grupo {grupo}\n🔒 Apuestas cierran a las {hora_col} (Col)\n¡Entra y apuesta YA!"

                print(f"\n🔔 Enviando notificación: {local} vs {visita}")
                print(f"   Cierra en: {diff:.1f} minutos")

                enviados = 0
                for token in tokens:
                    if enviar_notificacion(token_acceso, token, titulo, cuerpo):
                        enviados += 1

                print(f"   ✅ Enviada a {enviados}/{len(tokens)} dispositivos")
                notificaciones_enviadas += 1

        except Exception as e:
            print(f"Error procesando partido {pid}: {e}")
            continue

    if notificaciones_enviadas == 0:
        print("\n✅ No hay partidos próximos a cerrar en este momento")
    else:
        print(f"\n✅ {notificaciones_enviadas} notificaciones enviadas")

if __name__ == '__main__':
    main()
