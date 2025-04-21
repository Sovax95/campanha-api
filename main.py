
import sys
import logging
import time
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

try:
    import ssl
except ModuleNotFoundError:
    sys.stderr.write("[Erro Crítico] O módulo 'ssl' não está disponível neste ambiente. Isso pode causar falhas ao usar bibliotecas que dependem de conexões seguras (HTTPS).\n")
    raise

# Logger
LOG_FILE = "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# Dados da campanha
class Campaign(BaseModel):
    name: str
    hashtags: List[str]
    message: str

# Simulação de envio com Telegram
import requests

TELEGRAM_BOT_TOKEN = "seu_token_aqui"
TELEGRAM_CHAT_ID = "seu_chat_id_aqui"

campaign_history = []

def simulate_campaign_send(platform: str, name: str, hashtags: list, message: str):
    full_message = f"📢 Campanha: {name}\n🔖 Hashtags: {' '.join(hashtags)}\n💬 Mensagem:\n{message}"
    logging.info(f"Enviando campanha '{name}' para {platform}")

    if platform == "Telegram":
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}
            )
            response.raise_for_status()
            logging.info("Mensagem enviada para Telegram com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao enviar para Telegram: {e}")
    else:
        logging.info(f"[SIMULADO] Enviando para {platform} com hashtags {hashtags} e mensagem '{message}'")

# FastAPI Setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pasta estática
static_dir = Path("static")
static_dir.mkdir(parents=True, exist_ok=True)
index_html_path = static_dir / "index.html"
index_html_path.write_text("""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>MVP Campanha</title>
</head>
<body>
    <h1>Campanha de Divulgação</h1>
    <form id="campaignForm">
        <label>Nome: <input type="text" name="name" required></label><br>
        <label>Hashtags (separadas por vírgula): <input type="text" name="hashtags" required></label><br>
        <label>Mensagem:<br><textarea name="message" rows="4" cols="50" required></textarea></label><br>
        <button type="submit">Enviar Campanha</button>
    </form>
    <hr>
    <h2>Histórico de Campanhas</h2>
    <ul id="history"></ul>
    <hr>
    <h2>Logs ao Vivo</h2>
    <button onclick="loadLogs()">Ver Logs</button>
    <pre id="logs" style="background:#eee; padding:10px;"></pre>
    <script>
        const form = document.getElementById('campaignForm');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = {
                name: formData.get('name'),
                hashtags: formData.get('hashtags').split(',').map(h => h.trim()),
                message: formData.get('message')
            };
            const res = await fetch('/create-campaign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (res.ok) {
                alert('Campanha enviada!');
                loadHistory();
            }
        });

        async function loadHistory() {
            const res = await fetch('/campaigns');
            const data = await res.json();
            const historyEl = document.getElementById('history');
            historyEl.innerHTML = '';
            data.forEach(c => {
                const li = document.createElement('li');
                li.textContent = `${c.name} - ${c.hashtags.join(' ')} - ${c.message}`;
                historyEl.appendChild(li);
            });
        }

        async function loadLogs() {
            const res = await fetch('/logs');
            const data = await res.json();
            document.getElementById('logs').textContent = data.logs.join('\n');
        }

        loadHistory();
    </script>
</body>
</html>
""", encoding="utf-8")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    body = await request.body()
    logging.info(f"[ID {request_id}] Recebida requisição: {request.method} {request.url}")
    if body:
        try:
            decoded_body = body.decode('utf-8')
            logging.info(f"[ID {request_id}] Payload: {decoded_body}")
        except Exception as decode_error:
            logging.warning(f"[ID {request_id}] Não foi possível decodificar o payload: {decode_error}")
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logging.info(f"[ID {request_id}] Resposta enviada com status: {response.status_code} em {process_time:.2f} ms")
    response.headers["X-Request-ID"] = request_id
    return response

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return HTMLResponse(content=index_html_path.read_text(encoding="utf-8"), status_code=200)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API funcionando corretamente."}

@app.post("/create-campaign")
async def create_campaign(campaign: Campaign):
    try:
        simulate_campaign_send("Twitter", campaign.name, campaign.hashtags, campaign.message)
        simulate_campaign_send("Telegram", campaign.name, campaign.hashtags, campaign.message)
        campaign_history.append(campaign)
        return {"status": "success", "data": campaign.dict()}
    except Exception as e:
        logging.error(f"Erro ao criar campanha: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar campanha: {e}")

@app.get("/campaigns")
async def get_campaigns():
    return [campaign.dict() for campaign in campaign_history]

@app.get("/logs")
async def get_logs():
    try:
        log_path = Path(LOG_FILE)
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8")
            return {"logs": content.splitlines()[-100:]}
        else:
            return {"logs": []}
    except Exception as e:
        logging.error(f"Erro ao ler logs: {e}")
        raise HTTPException(status_code=500, detail="Erro ao acessar logs")
