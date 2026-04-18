import os
import json
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ddgs import DDGS
from database import init_db, save_message, get_history, clear_history, save_diary, get_diary, save_task, get_tasks, complete_task, save_memory, get_memory, get_message_count

# ============================================================
# CONFIGURACAO
# ============================================================
ASSISTANT_NAME = "Jarvis"
USER_NAME = "Xande"

def get_system_prompt():
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    data_hora = now.strftime("%d/%m/%Y %H:%M")
    memory = get_memory()
    memory_section = f"\n\nMEMÓRIA SOBRE {USER_NAME}:\n{memory}" if memory else ""
    return f"""Você é {ASSISTANT_NAME}, um assistente virtual altamente inteligente, sofisticado e leal,
inspirado no J.A.R.V.I.S do Homem de Ferro. Você fala de forma educada, precisa e ligeiramente formal,
sempre chamando o usuário de "{USER_NAME}".
A data e hora atual é: {data_hora} (horário de Brasília).
Você é capaz de ajudar com qualquer tarefa: responder perguntas, dar informações,
fazer cálculos, ajudar com tecnologia, estudos, tarefas diárias, e muito mais.
Quando precisar de informações atuais, notícias, clima, cotações ou qualquer dado recente, use a ferramenta de busca.
SEMPRE escreva em português do Brasil correto, com todos os acentos, cedilhas e til (ç, ã, õ, é, á, etc.).
NUNCA omita acentuação. Use gramática formal e correta.
NUNCA use emojis nas respostas. As respostas serão convertidas em voz e emojis serão lidos literalmente.
Mantenha respostas curtas quando possível.{memory_section}"""

def _update_memory():
    try:
        history = get_history(limit=40)
        if not history:
            return
        mem_client = anthropic.Anthropic()
        response = mem_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=f"""Você é um sistema de memória. Analise o histórico de conversas e extraia
fatos importantes sobre o usuário chamado {USER_NAME}: preferências, hábitos, objetivos,
informações pessoais, projetos em andamento, etc.
Seja conciso. Liste apenas fatos relevantes em bullets. Máximo 15 itens.
Responda em português do Brasil com acentuação correta.""",
            messages=[{"role": "user", "content": f"Histórico:\n{json.dumps(history, ensure_ascii=False)}"}]
        )
        memory_text = response.content[0].text
        save_memory(memory_text)
    except Exception as e:
        print(f"Erro ao atualizar memória: {e}")

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
def _extract_text(content) -> str:
    """Extrai apenas texto de content (str ou lista de blocos). Ignora tool_use/tool_result."""
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(t for t in texts if t).strip()
    if isinstance(content, str):
        s = content.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    texts = [b.get("text", "") for b in parsed if isinstance(b, dict) and b.get("type") == "text"]
                    result = " ".join(t for t in texts if t).strip()
                    if result:
                        return result
                    # lista sem blocos de texto (ex: só tool_use) → descarta
                    return ""
            except (ValueError, TypeError):
                pass
        return s
    return ""


def sanitize_history(history):
    """
    Normaliza o histórico para a API da Anthropic:
    - Extrai apenas texto puro, descartando tool_use/tool_result de sessões passadas
    - Elimina mensagens vazias
    - Garante alternância user/assistant sem roles consecutivos iguais
    - Garante que começa com 'user'
    """
    clean = []
    for msg in history:
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue
        text = _extract_text(msg.get("content", ""))
        if not text:
            continue
        if clean and clean[-1]["role"] == role:
            continue  # descarta consecutivos com mesmo role
        clean.append({"role": role, "content": text})

    while clean and clean[0]["role"] != "user":
        clean.pop(0)

    return clean


@app.post("/chat")
def chat(req: ChatRequest):
    save_message("user", req.message)
    history = sanitize_history(get_history(limit=20))

    try:
        tools = [SEARCH_TOOL, DIARY_TOOL]

        # Mais tokens para resumos, flashcards e modo estudo (mensagens longas)
        msg_len = len(req.message)
        if msg_len > 8000:
            max_tok = 8192   # resumo/flashcard de PDF grande
        elif msg_len > 2000:
            max_tok = 4096   # modo estudo / perguntas com contexto
        elif msg_len > 500:
            max_tok = 2048   # respostas medias
        else:
            max_tok = 1024   # chat normal

        # Primeira chamada
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tok,
            system=get_system_prompt(),
            tools=tools,
            messages=history
        )

        diary_title = None
        diary_content = None

        # Se Claude quer usar ferramentas
        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if tool_use_blocks:
                # Executa TODOS os tool_use blocks e coleta um tool_result para cada um
                tool_results = []
                for tb in tool_use_blocks:
                    if tb.name == "search_web":
                        result_text = do_search(tb.input.get("query", req.message))
                    elif tb.name == "save_diary":
                        diary_title = tb.input.get("title", "")
                        diary_content = tb.input.get("content", "")
                        save_diary(diary_title, diary_content)
                        result_text = "Entrada salva no diario com sucesso."
                    else:
                        result_text = "Ferramenta desconhecida."
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tb.id,
                        "content": result_text
                    })

                # Monta assistant_content com todos os blocos da resposta
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
                history.append({"role": "user", "content": tool_results})

                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=max_tok,
                    system=get_system_prompt(),
                    tools=tools,
                    messages=history
                )

        reply = next((b.text for b in response.content if hasattr(b, "text")), "Nao consegui processar sua solicitacao.")
        reply = remove_emojis(reply)
        save_message("assistant", reply)

        result = {"reply": reply}
        if diary_title is not None and diary_content is not None:
            result["diary_saved"] = True
            result["diary_title"] = diary_title
            result["diary_content"] = diary_content

        # Atualiza memoria a cada 10 mensagens
        if get_message_count() % 10 == 0:
            threading.Thread(target=_update_memory, daemon=True).start()

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
