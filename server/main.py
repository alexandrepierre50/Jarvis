import os
import json
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
from database import init_db, save_message, get_history, clear_history, save_diary, get_diary, save_task, get_tasks, complete_task

# ============================================================
# CONFIGURACAO
# ============================================================
ASSISTANT_NAME = "Jarvis"
USER_NAME = "Senhor"

SYSTEM_PROMPT = f"""Voce e {ASSISTANT_NAME}, um assistente virtual altamente inteligente, sofisticado e leal,
inspirado no JARVIS do Homem de Ferro. Voce fala de forma educada, precisa e ligeiramente formal,
sempre chamando o usuario de "{USER_NAME}".
Voce e capaz de ajudar com qualquer tarefa: responder perguntas, dar informacoes,
fazer calculos, ajudar com tecnologia, estudos, tarefas diarias, e muito mais.
Quando precisar de informacoes atuais, noticias, clima, cotacoes ou qualquer dado recente, use a ferramenta de busca.
Responda sempre em portugues do Brasil, de forma concisa e direta.
Mantenha respostas curtas quando possivel, pois serao convertidas em voz."""

# ============================================================
# FERRAMENTA DE BUSCA
# ============================================================
SEARCH_TOOL = {
    "name": "search_web",
    "description": "Pesquisa informacoes atuais na internet. Use quando precisar de noticias recentes, clima, cotacoes, eventos atuais ou qualquer informacao que possa ter mudado.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "O termo de busca em portugues ou ingles"
            }
        },
        "required": ["query"]
    }
}

def do_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        if not results:
            return "Nenhum resultado encontrado."
        output = []
        for r in results:
            output.append(f"Titulo: {r.get('title', '')}\nResumo: {r.get('body', '')}\nFonte: {r.get('href', '')}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Erro na busca: {str(e)}"

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

client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY do ambiente automaticamente

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
        # Primeira chamada — Claude pode pedir uma busca
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=[SEARCH_TOOL],
            messages=history
        )

        # Se Claude quer buscar na internet
        if response.stop_reason == "tool_use":
            tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)

            if tool_use_block:
                query = tool_use_block.input.get("query", req.message)
                search_result = do_search(query)

                # Monta o historico com o resultado da busca
                assistant_content = []
                for b in response.content:
                    if b.type == "text":
                        assistant_content.append({"type": "text", "text": b.text})
                    elif b.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": b.id,
                            "name": b.name,
                            "input": b.input
                        })

                history.append({"role": "assistant", "content": assistant_content})
                history.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": search_result
                    }]
                })

                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    tools=[SEARCH_TOOL],
                    messages=history
                )

        reply = next((b.text for b in response.content if hasattr(b, "text")), "Nao consegui processar sua solicitacao.")
        save_message("assistant", reply)
        return {"reply": reply}

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Chave de API invalida.")
    except Exception as e:
        import traceback
        traceback.print_exc()
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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
pwa_path = os.path.abspath(os.path.join(BASE_DIR, "..", "pwa"))

if os.path.exists(pwa_path):
    app.mount("/static", StaticFiles(directory=pwa_path), name="static")

@app.get("/")
def root():
    index = os.path.join(pwa_path, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"status": "Jarvis API online"}

@app.get("/{filename}")
def serve_pwa_file(filename: str):
    filepath = os.path.join(pwa_path, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    return {"error": "File not found"}

# ============================================================
# INICIAR
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
