from twilio.rest import Client

# 🚨 Tus credenciales reales de Twilio
TWILIO_SID = "AC6604d2b40b71c2e7835957ba74c535d7"
TWILIO_TOKEN = "1dab509643f5e60def74c50b148f9162"
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"

# 🛠️ Cliente Twilio
client = Client(TWILIO_SID, TWILIO_TOKEN)

# 📤 Función para enviar mensaje de WhatsApp libre
def enviar_recordatorio_whatsapp(to, mensaje):
    try:
        message = client.messages.create(
            body=mensaje,
            from_=TWILIO_WHATSAPP_FROM,
            to=to
        )
        print(f"✅ Mensaje enviado a {to}. SID: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"❌ Error al enviar mensaje a {to}: {e}")
        return None
