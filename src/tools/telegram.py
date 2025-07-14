import requests
import tempfile
from datetime import datetime
import os
import time

from dotenv import load_dotenv

load_dotenv()


def send_text_telegram(txt, chat_id, token, parse_mode: str = 'Markdown'):
    # Primero, enviar el mensaje de texto
    send_message_url = f'https://api.telegram.org/bot{token}/sendMessage'
    message_data = {
        'chat_id': chat_id,
        'text': txt,
    }
    if parse_mode:
        message_data['parse_mode'] = parse_mode
    requests.post(send_message_url, data=message_data)
    return


def send_telegram_html(html_content, token, chat_id):
    """
    Envia contenido HTML como un documento a través de Telegram, con un nombre específico.
    """
    
    url = f'https://api.telegram.org/bot{token}/sendDocument'
    data = {'chat_id': chat_id}

    now = datetime.now()
    filename = now.strftime('%Y_%m_%d_%H_%M_newsletter.html')  # Formato AAA_MM_DD_HH_MM_newsletter.html
    
    # Crear un archivo temporal para guardar el contenido HTML
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".html", delete=True) as temp_html:
        temp_html.write(html_content)
        temp_html.flush()  # Asegura que todo el contenido se escriba en el archivo
        temp_html.seek(0)  # Mover el puntero al inicio del archivo para la lectura

        # Preparar el archivo con el nombre deseado al enviarlo
        files = {'document': (filename, temp_html, 'text/html')}
        
        # Enviar el archivo HTML como un documento
        response = requests.post(url, data=data, files=files)
    
    # Opcional: Retorna la respuesta de la API de Telegram
    return response

def get_bot_info(api_key):
    """Get bot information using Telegram API"""
    url = f"https://api.telegram.org/bot{api_key}/getMe"
    response = requests.get(url)
    return response.json()['result']

def find_group_id(api_key, bot_id):
    """Poll for updates and find group ID where bot was added"""
    offset = 0
    print("Listening for group additions... (Ctrl+C to stop)")
    
    while True:
        # Get updates with long polling
        url = f"https://api.telegram.org/bot{api_key}/getUpdates?offset={offset}&timeout=30"
        response = requests.get(url)
        updates = response.json().get('result', [])

        for update in updates:
            offset = update['update_id'] + 1  # Update offset to avoid repeats
            
            # Check if the update has new chat members
            if 'message' in update and 'new_chat_members' in update['message']:
                message = update['message']
                
                # Check if bot is among the new members
                if any(user['id'] == bot_id for user in message['new_chat_members']):
                    # Verify it's a group chat
                    if message['chat']['type'] in ['group', 'supergroup']:
                        return message['chat']['id']
                    else:
                        print("Error: Bot was added to a non-group chat")
        
        time.sleep(1)

def main():
    # Get API key from environment
    api_key = os.getenv("TG_BOT_TOKEN_STATUS")
    if not api_key:
        raise ValueError("TG_BOT_TOKEN_STATUS not found in .env file")

    # Get bot's own ID
    bot_info = get_bot_info(api_key)
    bot_id = bot_info['id']
    print(f"Bot ID: {bot_id}")

    # Find group ID where bot was added
    group_id = find_group_id(api_key, bot_id)
    print(f"\nGroup ID found: {group_id}")

if __name__ == "__main__":
    main()