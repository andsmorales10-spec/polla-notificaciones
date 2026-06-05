import os
import json
import requests
from datetime import datetime, timezone, timedelta
import google.auth.transport.requests
from google.oauth2 import service_account

# ══ CONFIGURACIÓN ══
PROJECT_ID = os.environ['FIREBASE_PROJECT_ID']
SA_JSON    = os.environ['FIREBASE_SERVICE_ACCOUNT']

COL_TZ = timezone(timedelta(hours=-5))

def get_access_token():
    sa_info = json.loads(SA_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=[
            'https://www.googleapis.com/auth/firebase.messaging',
            'https://www.googleapis.com/auth/firebase.database',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

def get_firebase_data(token, path):
    """Obtener datos de Firebase usando token como parámetro"""
    url = f"https://{PROJECT_ID}-default-rtdb.firebaseio.com/{path}.json?access_token={token}"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Error obteniendo {path}: {resp.text}")
        return None
    return resp.json()

def enviar_notificacion(token, device_token, titulo, cuerpo):
    url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": {
            "token": device_token,
            "notification": {"title": titulo, "body": cuerpo},
            "webpush": {
                "notification": {
                    "title": titulo,
                    "body": cuerpo,
                    "icon": "/icon-192.png",
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
    ahora = datetime.now(COL_TZ)
    print(f"🕐 Revisando partidos — {ahora.strftime('%Y-%m-%d %H:%M')} Colombia")

    token = get_access_token()
    print("✅ Token de acceso obtenido")

    # Obtener partidos
    partidos = get_firebase_data(token, 'partidos')
    if not partidos:
        print("⚠️ No se pudieron obtener los partidos")
        return
    print(f"✅ Partidos encontrados: {len(partidos)}")

    # Obtener tokens de dispositivos
    tokens_data = get_firebase_data(token, 'tokens')
    device_tokens = []
    if tokens_data:
        for uid, info in tokens_data.items():
            if isinstance(info, dict) and 'token' in info:
                device_tokens.append(info['token'])
    print(f"📱 Dispositivos registrados: {len(device_tokens)}")

    if not device_tokens:
        print("⚠️ No hay dispositivos registrados para notificaciones")
        print("   Los participantes deben aceptar notificaciones en la app")
        return

    ET_TZ = timezone(timedelta(hours=-4))
    notif_enviadas = 0

    for pid, p in partidos.items():
        if p.get('estado') in ['Finalizado', 'Resultado confirmado']:
            continue
        try:
            cierre_str = p.get('cierre', '')
            if not cierre_str:
                continue

            cierre_et = datetime.strptime(cierre_str, '%Y-%m-%d %H:%M')
            cierre_et = cierre_et.replace(tzinfo=ET_TZ)
            cierre_col = cierre_et.astimezone(COL_TZ)
            diff = (cierre_col - ahora).total_seconds() / 60

            print(f"   {p.get('local')} vs {p.get('visita')}: cierra en {diff:.1f} min")

            if 8 <= diff <= 15:
                local  = p.get('local', '')
                visita = p.get('visita', '')
                grupo  = p.get('grupo', '')
                hora   = cierre_col.strftime('%I:%M %p')

                titulo = f"⚽ ¡Cierra en {int(diff)} min!"
                cuerpo = f"{local} vs {visita} — Grupo {grupo}\n🔒 Apuestas cierran a las {hora}\n¡Entra y apuesta YA!"

                print(f"\n🔔 Enviando: {local} vs {visita}")
                enviados = sum(1 for t in device_tokens if enviar_notificacion(token, t, titulo, cuerpo))
                print(f"   ✅ Enviada a {enviados}/{len(device_tokens)} dispositivos")
                notif_enviadas += 1

        except Exception as e:
            print(f"Error en partido {pid}: {e}")

    if notif_enviadas == 0:
        print("\n✅ No hay partidos cerrando en los próximos 8-15 minutos")
    else:
        print(f"\n🏆 {notif_enviadas} notificaciones enviadas")

if __name__ == '__main__':
    main()
