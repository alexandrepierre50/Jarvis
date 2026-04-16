import os
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ddgs import DDGS
from database import init_db, save_message, get_history, clear_history, save_diary, get_diary, save_task, get_tasks, complete_task

# ============================================================
# CONFIGURACAO
# ============================================================
ASSISTANT_NAME = "Jarvis"
USER_NAME = "Xande"

def get_system_prompt():
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    data_hora = now.strftime("%d/%m/%Y %H:%M")
    return f"""Voce e {ASSISTANT_NAME}, um assistente virtual altamente inteligente, sofisticado e leal,
inspirado no JARVIS do Homem de Ferro. Voce fala de forma educada, precisa e ligeiramente formal,
sempre chamando o usuario de "{USER_NAME}".
A data e hora atual e: {data_hora} (horario de Brasilia).
Voce e capaz de ajudar com qualquer tarefa: responder perguntas, dar informacoes,
fazer calculos, ajudar com tecnologia, estudos, tarefas diarias, e muito mais.
Quando precisar de informacoes atuais, noticias, clima, cotacoes ou qualquer dado recente, use a ferramenta de busca.
Responda sempre em portugues do Brasil, de forma concisa e direta.
NUNCA use emojis nas respostas. As respostas serao convertidas em voz e emojis serao lidos literalmente.
Mantenha respostas curtas quando possivel."""

def remove_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF\u2700-\u27BF]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()

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
        with DDGS(timeout=8) as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "Nenhum resultado encontrado."
        output = []
        for r in results:
            output.append(f"Titulo: {r.get('title', '')}\nResumo: {r.get('body', '')}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Nao foi possivel buscar informacoes no momento: {str(e)}"

DIARY_TOOL = {
    "name": "save_diary",
    "description": "Salva uma entrada no diario do usuario. Use quando o usuario pedir para anotar, registrar ou salvar algo no diario.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Titulo curto da entrada"
            },
            "content": {
                "type": "string",
                "description": "Conteudo completo a ser salvo no diario"
            }
        },
        "required": ["content"]
    }
}

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

_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"[JARVIS] API key encontrada: {'sim' if _api_key else 'NAO'} | primeiros chars: {_api_key[:8] if _api_key else 'vazio'}")
client = anthropic.Anthropic(api_key=_api_key if _api_key else None)

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
        tools = [SEARCH_TOOL, DIARY_TOOL]

        # Primeira chamada
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=get_system_prompt(),
            tools=tools,
            messages=history
        )

        # Se Claude quer usar uma ferramenta
        if response.stop_reason == "tool_use":
            tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)

            if tool_use_block:
                # Executa a ferramenta correta
                if tool_use_block.name == "search_web":
                    query = tool_use_block.input.get("query", req.message)
                    tool_result = do_search(query)
                elif tool_use_block.name == "save_diary":
                    diary_title = tool_use_block.input.get("title", "")
                    diary_content = tool_use_block.input.get("content", "")
                    save_diary(diary_title, diary_content)
                    tool_result = "Entrada salva no diario com sucesso."
                else:
                    tool_result = "Ferramenta desconhecida."

                # Monta historico com resultado
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
                        "content": tool_result
                    }]
                })

                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=512,
                    system=get_system_prompt(),
                    tools=tools,
                    messages=history
                )

        reply = next((b.text for b in response.content if hasattr(b, "text")), "Nao consegui processar sua solicitacao.")
        reply = remove_emojis(reply)
        save_message("assistant", reply)

        result = {"reply": reply}
        if "diary_title" in locals() and "diary_content" in locals():
            result["diary_saved"] = True
            result["diary_title"] = diary_title
            result["diary_content"] = diary_content
        return result

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
