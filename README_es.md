# Discord Bot de Música y TTS

Un bot de Discord con reproducción de música desde YouTube y capacidades de texto a voz, impulsado por ElevenLabs.

## Características

- **Reproducción de Música** — Reproduce audio desde URLs de YouTube o búsquedas con un sistema de cola por servidor
- **Texto a Voz** — Genera voz en un canal de voz usando el modelo multilingüe v2 de ElevenLabs
- **Desconexión Automática** — Se desconecta automáticamente de los canales de voz cuando no quedan humanos (5s de espera)
- **Gestión de Cola** — Soporte completo de cola con skip, stop y listado de cola

## Comandos

| Comando | Descripción |
|---------|-------------|
| `!pley <url o búsqueda>` | Reproduce un video de YouTube o lo agrega a la cola |
| `!skip` | Salta la pista actual |
| `!stop` | Detiene la reproducción y limpia la cola |
| `!queue` | Muestra la cola actual |
| `!tts <texto>` | Genera y reproduce voz a partir de texto |
| `!setvoz <voice_id>` | Cambia el ID de voz de ElevenLabs |
| `!leave` | Desconecta el bot del canal de voz |

## Configuración

### Requisitos Previos

- Python 3.10+
- FFmpeg instalado y disponible en `PATH`
- Librería Opus (`libopus`) para codificación de voz
- Archivo de cookies de YouTube (opcional, para videos restringidos)

### Instalación

```bash
git clone <repo-url>
cd disc-bot
python -m venv venv
source venv/bin/activate
pip install discord.py yt-dlp python-dotenv elevenlabs
```

### Configuración

Copia `.env.example` a `.env` y completa tus credenciales:

```env
DISCORD_TOKEN=tu_discord_bot_token
ELEVENLABS_API_KEY=tu_elevenlabs_api_key
VOICE_ID=JBFqnCBsd6RMkjVDRZzb
```

- **DISCORD_TOKEN** — Obténlo en el [Portal de Desarrolladores de Discord](https://discord.com/developers/applications)
- **ELEVENLABS_API_KEY** — Obténlo en [ElevenLabs](https://elevenlabs.io/)
- **VOICE_ID** — Voz predeterminada para TTS (encuentra las voces disponibles en tu panel de ElevenLabs)

### Permisos del Bot de Discord

Habilita lo siguiente en el Portal de Desarrolladores de Discord:

- **Intents**: Message Content Intent
- **Permisos del Bot**: Connect, Speak, Send Messages

### Ejecutar

```bash
source venv/bin/activate
python app.py
```

## Notas

- El bot carga Opus desde `/lib/x86_64-linux-gnu/libopus.so.0` por defecto. Ajusta la ruta en `app.py` si es necesario.
- Coloca un archivo `cookies.txt` en la raíz del proyecto para que yt-dlp evite las restricciones de edad/login de YouTube.
- Los archivos de audio TTS generados se eliminan automáticamente después de la reproducción.
