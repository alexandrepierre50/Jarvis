import os
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import init_db, save_message, get_history, clear_history, save_diary, get_diary, save_task, get_tasks, complete_task

# ============================================================
# CONFIGURACAO
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ASSISTANT_NAME = "Jarvis"
USER_NAME = "Senhor"

SYSTEM_PROMPT = f"""Voce e {ASSISTANT_NAME}, um assistente virtual altamente inteligente, sofisticado e leal,
inspirado no JARVIS do Homem de Ferro. Voce fala de forma educada, precisa e ligeiramente formal,
sempre chamando o usuario de "{USER_NAME}".
Voce e capaz de ajudar com qualquer tarefa: responder perguntas, dar informacoes,
fazer calculos, ajudar com tecnologia, estudos, tarefas diarias, e muito mais.
Responda sempre em portugues do Brasil, de forma concisa e direta.
Mantenha respostas curtas quando possivel, pois serao convertidas em voz."""

# ============================================================
# APP
# ============================================================
app = FastAPI(title="Jarvis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================================
# MODELOS
# ============================================================
class ChatRequest(BaseModel):
    message: str

class DiaryRequest(BaseModel):
    title: str = ""
    content: str

class TaskRequest(BaseModel):
    title: str

# ============================================================
# ROTAS - CHAT
# ============================================================
@app.post("/chat")
def chat(req: ChatRequest):
    save_message("user", req.message)
    history = get_history(limit=20)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=history
        )
        reply = response.content[0].text
        save_message("assistant", reply)
        return {"reply": reply}
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Chave de API invalida.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def history():
    return get_history(limit=50)

@app.delete("/history")
def delete_history():
    clear_history()
    return {"ok": True}

# ============================================================
# ROTAS - DIARIO
# ============================================================
@app.post("/diary")
def add_diary(req: DiaryRequest):
    save_diary(req.title, req.content)
    return {"ok": True}

@app.get("/diary")
def list_diary():
    return get_diary()

# ============================================================
# ROTAS - TAREFAS
# ============================================================
@app.post("/tasks")
def add_task(req: TaskRequest):
    save_task(req.title)
    return {"ok": True}

@app.get("/tasks")
def list_tasks():
    return get_tasks()

@app.patch("/tasks/{task_id}/complete")
def done_task(task_id: int):
    complete_task(task_id)
    return {"ok": True}

# ============================================================
# SERVIR PWA
# ============================================================
pwa_path = os.path.join(os.path.dirname(__file__), "..", "pwa")
if os.path.exists(pwa_path):
    app.mount("/app", StaticFiles(directory=pwa_path, html=True), name="pwa")

@app.get("/")
def root():
    index = os.path.join(pwa_path, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"status": "Jarvis API online"}

# ============================================================
# INICIAR
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
