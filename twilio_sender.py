from twilio.rest import Client

TWILIO_SID = "AC6604d2b40b71c2e7835957ba74c535d7"
TWILIO_TOKEN = "1dab509643f5e60def74c50b148f9162"
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
CONTENT_SID = "HXb5b62575e6e4ff6129ad7c8efe1f983e"  # ID de tu plantilla

client = Client(TWILIO_SID, TWILIO_TOKEN)

def enviar_recordatorio_whatsapp(to, fecha="12/1", hora="3pm"):
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to,
            content_sid=CONTENT_SID,
            content_variables={
                "1": fecha,
                "2": hora
            }
        )
        print(f"✅ Mensaje enviado a {to}. SID: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"❌ Error al enviar mensaje a {to}: {e}")
        return None

