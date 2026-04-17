import customtkinter as ctk
import threading
import speech_recognition as sr
import math
import tempfile
import os
import shutil
import requests
from datetime import datetime
from tkinter import filedialog
from PIL import ImageGrab
import pdfplumber
from youtube_transcript_api import YouTubeTranscriptApi
import pygame
import asyncio
import edge_tts
from config import ASSISTANT_NAME, USER_NAME, LANGUAGE, OBSIDIAN_VAULT
from skill_petrobras import PetrobrasStudy, QuizWindow

SERVER_URL = "https://web-production-b9c17.up.railway.app"

# ============================================================
# CONFIGURACAO VISUAL
# ============================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ============================================================
# CLASSE PRINCIPAL DO JARVIS
# ============================================================
class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{ASSISTANT_NAME} - Assistente Virtual")
        self.geometry("900x700")
        self.resizable(True, True)
        self.configure(fg_color="#050d1a")

        # Estado
        self.is_listening = False
        self.is_speaking = False
        self.study_pdf = None  # (filename, text) quando em modo estudo
        self.obsidian_vault = OBSIDIAN_VAULT
        self.petrobras = PetrobrasStudy(self)
        self.quiz = QuizWindow(self)

        # Vozes disponiveis (edge-tts, gratuito)
        self.voices = {
            "Antonio (BR Masculino)": "pt-BR-AntonioNeural",
            "Francisca (BR Feminino)": "pt-BR-FranciscaNeural",
        }
        self.current_voice = "pt-BR-AntonioNeural"
        pygame.mixer.init()

        # Inicializa reconhecimento de voz
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 2.5
        self.recognizer.non_speaking_duration = 2.0

        # Constroi interface
        self._build_ui()

        # Animacao
        self.animation_angle = 0
        self.pulse_size = 0
        self.pulse_growing = True
        self._animate()

        # Mensagem de boas-vindas
        self.after(800, self._welcome)

    # --------------------------------------------------------
    # VOZ
    # --------------------------------------------------------
    def _clean_for_speech(self, text):
        import re
        text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)  # **bold** e *italic*
        text = re.sub(r'#{1,6}\s*', '', text)                # # titulos
        text = re.sub(r'^\s*[-•]\s*', '', text, flags=re.MULTILINE)  # listas
        text = re.sub(r'`{1,3}.*?`{1,3}', '', text)         # `codigo`
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # [link](url)
        text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)    # _italico_
        text = re.sub(r'\n{2,}', '. ', text)                 # quebras de linha
        text = re.sub(r'\n', ' ', text)
        text = re.sub(r'\s{2,}', ' ', text)
        return text.strip()

    def _speak(self, text):
        if not text or not text.strip():
            return
        text = self._clean_for_speech(text)
        # Trunca em 500 chars na primeira frase completa
        if len(text) > 500:
            trunc = text[:500]
            last_period = max(trunc.rfind("."), trunc.rfind("!"), trunc.rfind("?"))
            text = trunc[:last_period + 1] if last_period > 100 else trunc
        self.is_speaking = True
        self._set_status("Falando...", "#00bfff")
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name

            asyncio.run(self._tts_to_file(text, tmp_path))

            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Erro TTS: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            self.is_speaking = False
            self.after(0, lambda: self._set_status("Aguardando...", "#1a6b8a"))

    async def _tts_to_file(self, text, path):
        communicate = edge_tts.Communicate(text, self.current_voice)
        await communicate.save(path)

    # --------------------------------------------------------
    # INTERFACE
    # --------------------------------------------------------
    def _build_ui(self):
        # --- Titulo ---
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(pady=(20, 0))

        ctk.CTkLabel(
            title_frame,
            text=f"J.A.R.V.I.S",
            font=ctk.CTkFont(family="Courier New", size=36, weight="bold"),
            text_color="#00bfff"
        ).pack()

        ctk.CTkLabel(
            title_frame,
            text="Just A Rather Very Intelligent System",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color="#1a6b8a"
        ).pack()

        # --- Canvas de animacao ---
        self.canvas = ctk.CTkCanvas(
            self,
            width=200,
            height=200,
            bg="#050d1a",
            highlightthickness=0
        )
        self.canvas.pack(pady=10)

        # --- Status ---
        self.status_label = ctk.CTkLabel(
            self,
            text="Inicializando...",
            font=ctk.CTkFont(family="Courier New", size=13),
            text_color="#1a6b8a"
        )
        self.status_label.pack(pady=(0, 5))

        # --- Banner de estudo (oculto por padrao) ---
        self.study_banner = ctk.CTkFrame(self, fg_color="#0a1a00", corner_radius=8,
                                         border_width=1, border_color="#00ff88")
        # nao faz pack aqui — aparece apenas no modo estudo

        banner_inner = ctk.CTkFrame(self.study_banner, fg_color="transparent")
        banner_inner.pack(fill="x", padx=12, pady=6)

        self.study_label = ctk.CTkLabel(
            banner_inner,
            text="",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            text_color="#00ff88"
        )
        self.study_label.pack(side="left")

        ctk.CTkButton(
            banner_inner,
            text="Encerrar Estudo",
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#1a3300", hover_color="#2a5500",
            text_color="#00ff88", border_width=1, border_color="#00ff88",
            width=120, height=28, corner_radius=6,
            command=self._stop_study_mode
        ).pack(side="right")

        # --- Chat ---
        self.chat_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="#060f20",
            corner_radius=12,
            border_width=1,
            border_color="#0a2a4a"
        )
        self.chat_frame.pack(fill="both", expand=True, padx=20, pady=(5, 10))

        # --- Linha inferior ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.text_input = ctk.CTkEntry(
            bottom_frame,
            placeholder_text="Digite uma mensagem ou use o microfone...",
            font=ctk.CTkFont(family="Courier New", size=13),
            fg_color="#060f20",
            border_color="#0a3a6a",
            text_color="#a0d4f5",
            height=46,
            corner_radius=12
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_input.bind("<Return>", lambda e: self._send_text())

        self.send_btn = ctk.CTkButton(
            bottom_frame,
            text="Enviar",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            fg_color="#003a6a", hover_color="#005a9a",
            text_color="#00bfff",
            width=80, height=46, corner_radius=12,
            command=self._send_text
        )
        self.send_btn.pack(side="left", padx=(0, 8))

        self.mic_btn = ctk.CTkButton(
            bottom_frame,
            text="🎤",
            font=ctk.CTkFont(size=18),
            fg_color="#001a3a", hover_color="#002a5a",
            text_color="#00bfff",
            border_width=1, border_color="#0a3a6a",
            width=46, height=46, corner_radius=12,
            command=self._toggle_listen
        )
        self.mic_btn.pack(side="left", padx=(0, 8))

        self.menu_btn = ctk.CTkButton(
            bottom_frame,
            text="⊕",
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color="#001a3a", hover_color="#002a5a",
            text_color="#00bfff",
            border_width=1, border_color="#0a3a6a",
            width=46, height=46, corner_radius=12,
            command=self._toggle_menu
        )
        self.menu_btn.pack(side="left")

        # --- Menu flutuante (oculto por padrao) ---
        self._menu_aberto = False
        self.menu_popup = ctk.CTkFrame(
            self,
            fg_color="#070f20",
            corner_radius=14,
            border_width=1,
            border_color="#0a3a6a"
        )

        itens = [
            ("📓  Diario",    "#001a3a", "#0a3a6a", "#a0d4f5", self._open_diary),
            ("🛢   Petrobras", "#003a00", "#00ff88", "#00ff88", self.petrobras.open_window),
        ]

        for i, (label, fg, borda, tc, cmd) in enumerate(itens):
            row, col = divmod(i, 2)
            btn = ctk.CTkButton(
                self.menu_popup,
                text=label,
                font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                fg_color=fg, hover_color="#004a8a",
                text_color=tc,
                border_width=1, border_color=borda,
                height=44, corner_radius=10,
                anchor="w",
                command=lambda c=cmd: [self._fechar_menu(), c()]
            )
            btn.grid(row=row, column=col, padx=8, pady=5, sticky="ew")

        self.menu_popup.grid_columnconfigure(0, weight=1)
        self.menu_popup.grid_columnconfigure(1, weight=1)

        # Seletor de voz discreto dentro do popup
        voice_row = ctk.CTkFrame(self.menu_popup, fg_color="transparent")
        voice_row.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(voice_row, text="Voz:",
                     font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(side="left", padx=(4, 6))

        self.voice_menu = ctk.CTkOptionMenu(
            voice_row,
            values=list(self.voices.keys()),
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#0a0a2a", button_color="#003a6a",
            text_color="#a0d4f5",
            height=32, corner_radius=8,
            command=self._change_voice
        )
        self.voice_menu.pack(side="left", fill="x", expand=True)

    def _change_voice(self, choice):
        self.current_voice = self.voices[choice]

    def _toggle_menu(self):
        if self._menu_aberto:
            self._fechar_menu()
        else:
            self.menu_popup.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-70)
            self.menu_popup.lift()
            self._menu_aberto = True
            self.menu_btn.configure(text="✕")

    def _fechar_menu(self):
        self.menu_popup.place_forget()
        self._menu_aberto = False
        self.menu_btn.configure(text="⊕")

    def _set_status(self, text, color="#1a6b8a"):
        self.status_label.configure(text=text, text_color=color)

    def _add_message(self, sender, text, color):
        frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        frame.pack(fill="x", pady=3, padx=5)

        prefix = ctk.CTkLabel(
            frame,
            text=f"[{sender}]",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            text_color=color,
            width=90,
            anchor="w"
        )
        prefix.pack(side="left", padx=(0, 6))

        msg = ctk.CTkLabel(
            frame,
            text=text,
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color="#a0d4f5",
            wraplength=600,
            justify="left",
            anchor="w"
        )
        msg.pack(side="left", fill="x", expand=True)

        # Scroll para o final
        self.after(100, lambda: self.chat_frame._parent_canvas.yview_moveto(1.0))

    # --------------------------------------------------------
    # ANIMACAO
    # --------------------------------------------------------
    def _animate(self):
        self.canvas.delete("all")
        cx, cy = 100, 100

        # Circulos de fundo
        for i in range(4, 0, -1):
            r = 30 + i * 16
            alpha_color = ["#051020", "#061528", "#071830", "#081b38"][i - 1]
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    outline="#0a3a6a", width=1, fill=alpha_color)

        # Arcos girando
        for i in range(3):
            angle_offset = self.animation_angle + i * 120
            start = angle_offset % 360
            self.canvas.create_arc(
                cx - 55, cy - 55, cx + 55, cy + 55,
                start=start, extent=90,
                outline=["#00bfff", "#0080ff", "#004080"][i],
                width=2, style="arc"
            )

        # Circulo central pulsante
        if self.pulse_growing:
            self.pulse_size += 0.5
            if self.pulse_size >= 10:
                self.pulse_growing = False
        else:
            self.pulse_size -= 0.5
            if self.pulse_size <= 0:
                self.pulse_growing = True

        pr = 18 + self.pulse_size
        fill_color = "#003a6a" if not self.is_listening else "#004a8a"
        outline_color = "#00bfff" if not self.is_listening else "#00ffff"
        self.canvas.create_oval(cx - pr, cy - pr, cx + pr, cy + pr,
                                fill=fill_color, outline=outline_color, width=2)

        # Texto central
        center_text = "J" if not self.is_listening else "..."
        self.canvas.create_text(cx, cy, text=center_text,
                                fill="#00bfff",
                                font=("Courier New", 16, "bold"))

        # Pontos orbitando
        for i in range(6):
            angle = math.radians(self.animation_angle * 2 + i * 60)
            ox = cx + 72 * math.cos(angle)
            oy = cy + 72 * math.sin(angle)
            self.canvas.create_oval(ox - 3, oy - 3, ox + 3, oy + 3,
                                    fill="#00bfff", outline="")

        self.animation_angle = (self.animation_angle + 2) % 360
        self.after(30, self._animate)

    # --------------------------------------------------------
    # LOGICA
    # --------------------------------------------------------
    def _welcome(self):
        msg = f"Sistemas online. Bom dia, {USER_NAME}. Como posso ajudar?"
        self._add_message(ASSISTANT_NAME, msg, "#00bfff")
        self._speak(msg)
        self._set_status("Aguardando...", "#1a6b8a")

    def _send_text(self):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, "end")
        self._process_input(text)

    def _toggle_listen(self):
        if self.is_listening:
            return
        threading.Thread(target=self._listen_thread, daemon=True).start()

    def _listen_thread(self):
        self.is_listening = True
        self.after(0, lambda: self.mic_btn.configure(text="Ouvindo...", fg_color="#002a5a"))
        self.after(0, lambda: self._set_status("Ouvindo...", "#00ffff"))

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=12)

            self.after(0, lambda: self._set_status("Processando voz...", "#00bfff"))
            text = self.recognizer.recognize_google(audio, language=LANGUAGE)
            self.after(0, lambda: self._process_input(text))

        except sr.WaitTimeoutError:
            self.after(0, lambda: self._set_status("Nenhuma voz detectada.", "#ff6b35"))
        except sr.UnknownValueError:
            self.after(0, lambda: self._set_status("Nao entendi. Tente novamente.", "#ff6b35"))
        except Exception as e:
            self.after(0, lambda: self._set_status(f"Erro: {str(e)}", "#ff4444"))
        finally:
            self.is_listening = False
            self.after(0, lambda: self.mic_btn.configure(text="Microfone", fg_color="#001a3a"))

    def _detect_skill(self, text):
        """Detecta se o comando é uma skill e executa diretamente. Retorna True se foi skill."""
        t = text.lower().strip()

        # Nota do dia
        if any(k in t for k in ["nota do dia", "criar nota", "nota de hoje", "diário de hoje", "abrir diário"]):
            self._skill_today()
            return True

        # Revisão semanal
        if any(k in t for k in ["revisão semanal", "revisar semana", "relatório semanal", "review semanal"]):
            self._skill_weekly_review()
            return True

        # Importar trade
        if any(k in t for k in ["importar trade", "importar trades", "importar do diário"]):
            self._skill_import_trade()
            return True

        # Registrar / analisar trade
        if any(k in t for k in ["registrar trade", "registrar operação", "analisar trade", "novo trade"]):
            self._skill_trade()
            return True

        # Pesquisar — extrai o tema do comando
        for prefix in ["pesquisar sobre ", "pesquisar ", "pesquisa sobre ", "pesquisa ", "buscar sobre ", "buscar "]:
            if t.startswith(prefix):
                topic = text[len(prefix):].strip()
                if topic:
                    self._add_message(USER_NAME, f"[Pesquisa: {topic}]", "#bf7fff")
                    threading.Thread(target=self._run_skill_research, args=(topic,), daemon=True).start()
                    return True

        # Obsidian — ler nota
        for prefix in ["ler nota ", "ler ", "abrir nota ", "mostrar nota ", "ver nota "]:
            if t.startswith(prefix):
                termo = text[len(prefix):].strip()
                if termo:
                    threading.Thread(target=self._vault_read, args=(termo,), daemon=True).start()
                    return True

        # Obsidian — marcar status
        for status, emoji in [("dominado", "🟢 dominado"), ("revisar", "🟡 revisar"), ("pendente", "🔴 pendente")]:
            if f"marcar" in t and status in t:
                # extrai nome da nota do comando
                termo = t.replace("marcar", "").replace(f"como {status}", "").replace(status, "").strip()
                if termo:
                    threading.Thread(target=self._vault_set_status, args=(termo, emoji), daemon=True).start()
                    return True

        # Obsidian — listar notas de uma pasta
        for prefix in ["listar notas de ", "listar ", "notas de "]:
            if t.startswith(prefix):
                pasta = text[len(prefix):].strip()
                threading.Thread(target=self._vault_list, args=(pasta,), daemon=True).start()
                return True

        # Obsidian — adicionar conteudo a uma nota (ex: "adicionar X na nota Y")
        if t.startswith("adicionar ") and " na nota " in t:
            partes = text[len("adicionar "):].split(" na nota ", 1)
            if len(partes) == 2:
                conteudo, nota = partes[0].strip(), partes[1].strip()
                threading.Thread(target=self._vault_append, args=(nota, conteudo), daemon=True).start()
                return True

        # Analise de respostas do Obsidian
        for prefix in ["analisa minhas respostas de ", "corrigir questoes de ", "corrigir questões de ",
                        "analisar questoes de ", "analisar questões de ", "corrige questoes de ",
                        "corrige questões de ", "ver resultado de ", "resultado de "]:
            if t.startswith(prefix):
                tema = text[len(prefix):].strip()
                threading.Thread(target=self._analisar_respostas, args=(tema,), daemon=True).start()
                return True

        return False

    # --------------------------------------------------------
    # OBSIDIAN — OPERACOES DIRETAS
    # --------------------------------------------------------
    def _vault_find_note(self, termo):
        """Encontra o caminho de uma nota pelo nome (busca parcial)."""
        termo_lower = termo.lower().replace(" ", "")
        best = None
        best_score = 0
        for root, dirs, files in os.walk(OBSIDIAN_VAULT):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fname_lower = fname.lower().replace(" ", "").replace(".md", "")
                # score por letras em comum
                score = sum(1 for c in termo_lower if c in fname_lower)
                if termo_lower in fname_lower:
                    score += 100
                if score > best_score:
                    best_score = score
                    best = os.path.join(root, fname)
        return best if best_score > 2 else None

    def _vault_read(self, termo):
        path = self._vault_find_note(termo)
        if not path:
            self.after(0, lambda: self._add_message("ERRO", f"Nota '{termo}' nao encontrada.", "#ff4444"))
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        fname = os.path.basename(path)
        self.after(0, lambda: self._add_message("Obsidian", f"[{fname}]", "#bf7fff"))
        # Mostra e manda para IA comentar
        preview = content[:800] + ("..." if len(content) > 800 else "")
        self.after(0, lambda: self._add_message(ASSISTANT_NAME, preview, "#a0d4f5"))
        prompt = f"Esta e a nota '{fname}' do meu Obsidian:\n\n{content[:8000]}\n\nFaca um breve comentario sobre o conteudo e pergunte se quero continuar estudando ou se tenho duvidas."
        threading.Thread(target=self._get_ai_response, args=(prompt,), daemon=True).start()

    def _vault_set_status(self, termo, emoji):
        path = self._vault_find_note(termo)
        if not path:
            self.after(0, lambda: self._add_message("ERRO", f"Nota '{termo}' nao encontrada.", "#ff4444"))
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        import re
        # Atualiza o campo status no frontmatter
        if 'status:' in content:
            new_content = re.sub(r'status:.*', f'status: "{emoji}"', content)
        else:
            new_content = content.replace("---\n", f'---\nstatus: "{emoji}"\n', 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        fname = os.path.basename(path)
        msg = f"Status de '{fname}' atualizado para {emoji}."
        self.after(0, lambda: self._add_message(ASSISTANT_NAME, msg, "#00ff88"))
        self.after(0, lambda: self._speak(msg))

    def _vault_append(self, nota, conteudo):
        path = self._vault_find_note(nota)
        if not path:
            self.after(0, lambda: self._add_message("ERRO", f"Nota '{nota}' nao encontrada.", "#ff4444"))
            return
        now = datetime.now().strftime("%H:%M")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n\n> [{now}] {conteudo}")
        fname = os.path.basename(path)
        msg = f"Adicionado em '{fname}'."
        self.after(0, lambda: self._add_message(ASSISTANT_NAME, msg, "#00ff88"))
        self.after(0, lambda: self._speak(msg))

    def _analisar_respostas(self, tema):
        import re
        path = self._vault_find_note(tema + " questoes")
        if not path:
            path = self._vault_find_note(tema)
        if not path or "questoes" not in path.lower().replace("õ", "o").replace("ô", "o"):
            # busca especificamente na pasta 500 - Questoes
            path = None
            tema_lower = tema.lower()
            for root, dirs, files in os.walk(OBSIDIAN_VAULT):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if "questoes" not in root.lower().replace("õ", "o").replace("ô", "o") and \
                   "500" not in root:
                    continue
                for fname in files:
                    if fname.endswith(".md") and tema_lower.replace(" ", "") in fname.lower().replace(" ", ""):
                        path = os.path.join(root, fname)
                        break
                if path:
                    break
        if not path:
            msg = f"Nao encontrei o arquivo de questoes de '{tema}'."
            self.after(0, lambda: self._add_message("ERRO", msg, "#ff4444"))
            return

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extrai respostas marcadas: - [x] (A) ...
        respostas = {}
        for m in re.finditer(r'- \[x\] \(([A-E])\)', content, re.IGNORECASE):
            # Encontra a qual questão pertence (conta blocos de questão anteriores)
            pos = m.start()
            qs_antes = len(re.findall(r'\*\*Questão\s*(\d+)\*\*', content[:pos]))
            if qs_antes not in respostas:
                respostas[qs_antes] = m.group(1).upper()

        if not respostas:
            msg = "Nenhuma resposta marcada ainda. Marque suas respostas no Obsidian com - [x] antes de analisar."
            self.after(0, lambda: self._add_message(ASSISTANT_NAME, msg, "#ffaa00"))
            self._speak(msg)
            return

        # Extrai gabarito: **Q1: B** — explicação
        gabarito = {}
        for m in re.finditer(r'\*\*Q(\d+):\s*([A-E])\*\*', content):
            gabarito[int(m.group(1))] = m.group(2).upper()

        if not gabarito:
            msg = "Nao encontrei o gabarito no arquivo de questoes."
            self.after(0, lambda: self._add_message("ERRO", msg, "#ff4444"))
            return

        acertos = 0
        linhas = []
        for num in sorted(gabarito.keys()):
            resp = respostas.get(num, "—")
            correta = gabarito[num]
            if resp == correta:
                acertos += 1
                linhas.append(f"Q{num}: ✓ ({resp})")
            else:
                linhas.append(f"Q{num}: ✗ sua={resp} | certa={correta}")

        total = len(gabarito)
        pct = int(acertos / total * 100)
        resumo = f"Resultado: {acertos}/{total} ({pct}%)\n\n" + "\n".join(linhas)
        self.after(0, lambda: self._add_message(ASSISTANT_NAME, resumo, "#00ff88" if pct >= 70 else "#ffaa00"))
        fala = f"Você acertou {acertos} de {total} questões, {pct} por cento."
        self.after(0, lambda: self._speak(fala))

        # Salva score no frontmatter do arquivo de questoes
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    fm = content[3:end]
                    for campo in ["acertos", "total", "percentual", "ultima_avaliacao"]:
                        fm = re.sub(rf'\n{campo}:.*', '', fm)
                    fm = fm.rstrip() + f"\nacertos: {acertos}\ntotal: {total}\npercentual: {pct}\nultima_avaliacao: {today}\n"
                    novo_content = "---" + fm + "---" + content[end + 3:]
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(novo_content)
        except Exception:
            pass

    def _vault_list(self, pasta):
        pasta_lower = pasta.lower()
        notas = []
        for root, dirs, files in os.walk(OBSIDIAN_VAULT):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            folder = os.path.basename(root).lower()
            if pasta_lower in folder or pasta_lower in root.lower():
                for fname in files:
                    if fname.endswith(".md"):
                        notas.append(fname.replace(".md", ""))
        if notas:
            lista = "\n".join(f"- {n}" for n in notas)
            self.after(0, lambda: self._add_message(ASSISTANT_NAME, f"Notas em '{pasta}':\n{lista}", "#a0d4f5"))
        else:
            self.after(0, lambda: self._add_message(ASSISTANT_NAME, f"Nenhuma nota encontrada em '{pasta}'.", "#ff6b35"))

    def _search_vault(self, query):
        """Busca notas relevantes no vault pelo conteudo da pergunta."""
        try:
            results = []
            query_words = set(query.lower().split())
            stop = {"o", "a", "os", "as", "de", "do", "da", "e", "em", "que", "para", "com", "um", "uma"}
            query_words -= stop

            for root, dirs, files in os.walk(OBSIDIAN_VAULT):
                # Ignora pastas de sistema
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        score = sum(1 for w in query_words if w in content.lower())
                        if score > 0:
                            results.append((score, fname, content[:3000]))
                    except Exception:
                        continue

            results.sort(reverse=True)
            return results[:3]  # top 3 notas mais relevantes
        except Exception:
            return []

    def _process_input(self, text):
        if self._detect_skill(text):
            return
        if "youtube.com/watch" in text or "youtu.be/" in text:
            threading.Thread(target=self._process_youtube, args=(text.strip(),), daemon=True).start()
            return
        if text.strip().lower().endswith(".pdf") and os.path.isfile(text.strip()):
            threading.Thread(target=self._extract_and_study_pdf, args=(text.strip(),), daemon=True).start()
            return
        self._add_message(USER_NAME, text, "#ffaa00")
        self._set_status("Pensando...", "#00bfff")

        # Monta contexto: PDF ativo + notas relevantes do Obsidian
        context_parts = []

        if self.study_pdf:
            filename, pdf_text = self.study_pdf
            context_parts.append(f"[PDF em estudo: '{filename}']\n{pdf_text[:15000]}")

        vault_notes = self._search_vault(text)
        if vault_notes:
            notes_text = "\n\n---\n".join(
                f"[Nota: {fname}]\n{content}" for _, fname, content in vault_notes
            )
            context_parts.append(f"[Notas relevantes do Obsidian]\n{notes_text}")

        if context_parts:
            enriched = "\n\n===\n".join(context_parts) + f"\n\n===\nPergunta: {text}"
            threading.Thread(target=self._get_ai_response, args=(enriched,), daemon=True).start()
        else:
            threading.Thread(target=self._get_ai_response, args=(text,), daemon=True).start()

    def _get_ai_response(self, text):
        try:
            res = requests.post(
                f"{SERVER_URL}/chat",
                json={"message": text},
                timeout=120
            )
            res.raise_for_status()
            data = res.json()
            reply = data["reply"]

            # Se o servidor salvou no diario, salva tambem no Obsidian
            if data.get("diary_saved"):
                self.save_to_obsidian(
                    data.get("diary_title", ""),
                    data.get("diary_content", text)
                )

            self.after(0, lambda: self._add_message(ASSISTANT_NAME, reply, "#00bfff"))
            self.after(0, lambda: self._speak(reply))

        except Exception as e:
            msg = f"Erro ao contatar o servidor: {str(e)}"
            self.after(0, lambda: self._add_message("ERRO", msg, "#ff4444"))
            self.after(0, lambda: self._set_status("Erro.", "#ff4444"))

    # --------------------------------------------------------
    # DIARIO (Obsidian)
    # --------------------------------------------------------
    def _get_diary_folder(self):
        folder = os.path.join(OBSIDIAN_VAULT, "Diario JARVIS")
        os.makedirs(folder, exist_ok=True)
        return folder

    def _get_today_note_path(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self._get_diary_folder(), f"{today}.md")

    def save_to_obsidian(self, title, content, attachments=None):
        note_path = self._get_today_note_path()
        now = datetime.now().strftime("%H:%M")
        today = datetime.now().strftime("%Y-%m-%d")

        # Cria ou abre o arquivo do dia
        if not os.path.exists(note_path):
            header = f"# Diario - {today}\n\n"
        else:
            header = ""

        entry = f"## {now}"
        if title:
            entry += f" - {title}"
        entry += f"\n\n{content}\n"

        # Anexos
        if attachments:
            anexos_folder = os.path.join(self._get_diary_folder(), "anexos", today)
            os.makedirs(anexos_folder, exist_ok=True)
            entry += "\n**Anexos:**\n"
            for src_path in attachments:
                filename = os.path.basename(src_path)
                dst_path = os.path.join(anexos_folder, filename)
                shutil.copy2(src_path, dst_path)
                rel_path = os.path.join("anexos", today, filename).replace("\\", "/")
                ext = filename.split(".")[-1].lower()
                if ext in ["jpg", "jpeg", "png", "gif", "bmp", "webp"]:
                    entry += f"![[{rel_path}]]\n"
                else:
                    entry += f"[[{rel_path}]]\n"

        entry += "\n---\n\n"

        with open(note_path, "a", encoding="utf-8") as f:
            f.write(header + entry)

    def _open_diary(self):
        win = ctk.CTkToplevel(self)
        win.title("Diario - JARVIS")
        win.geometry("700x600")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        ctk.CTkLabel(win, text="DIARIO", font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
                     text_color="#00bfff").pack(pady=(16, 4))

        # Campo nova entrada
        entry_frame = ctk.CTkFrame(win, fg_color="transparent")
        entry_frame.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(entry_frame, text="Titulo (opcional):", font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(anchor="w")
        title_input = ctk.CTkEntry(entry_frame, fg_color="#060f20", border_color="#0a3a6a",
                                   text_color="#a0d4f5", font=ctk.CTkFont(family="Courier New", size=12))
        title_input.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(entry_frame, text="Texto:", font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(anchor="w")
        content_input = ctk.CTkTextbox(entry_frame, fg_color="#060f20", border_color="#0a3a6a",
                                       text_color="#a0d4f5", font=ctk.CTkFont(family="Courier New", size=12),
                                       height=80)
        content_input.pack(fill="x", pady=(2, 6))

        # Anexos selecionados
        selected_files = []
        files_label = ctk.CTkLabel(entry_frame, text="Nenhum arquivo selecionado",
                                   font=ctk.CTkFont(family="Courier New", size=10),
                                   text_color="#1a6b8a")
        files_label.pack(anchor="w")

        def pick_files():
            files = filedialog.askopenfilenames(
                title="Selecionar arquivos",
                filetypes=[("Todos os arquivos", "*.*"), ("Imagens", "*.jpg *.jpeg *.png *.gif"),
                           ("PDF", "*.pdf"), ("Documentos", "*.docx *.txt")]
            )
            if files:
                selected_files.clear()
                selected_files.extend(files)
                nomes = ", ".join(os.path.basename(f) for f in files)
                files_label.configure(text=nomes, text_color="#00bfff")

        btn_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=6)

        ctk.CTkButton(btn_frame, text="Anexar Arquivo/Foto", fg_color="#001a3a", hover_color="#002a5a",
                      text_color="#00bfff", border_width=1, border_color="#0a3a6a",
                      font=ctk.CTkFont(family="Courier New", size=12),
                      command=pick_files).pack(side="left", padx=(0, 8))

        # Botao de captura de tela
        countdown_label = ctk.CTkLabel(btn_frame, text="",
                                       font=ctk.CTkFont(family="Courier New", size=12),
                                       text_color="#ffaa00")
        countdown_label.pack(side="left", padx=(0, 8))

        def capture_screen():
            def do_capture():
                for i in range(3, 0, -1):
                    win.after(0, lambda n=i: countdown_label.configure(text=f"Capturando em {n}..."))
                    import time
                    time.sleep(1)
                win.after(0, win.withdraw)
                time.sleep(0.3)
                screenshot = ImageGrab.grab()
                win.after(0, win.deiconify)
                now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                tmp_dir = tempfile.gettempdir()
                tmp_path = os.path.join(tmp_dir, f"jarvis_print_{now_str}.png")
                screenshot.save(tmp_path)
                selected_files.append(tmp_path)
                nome = os.path.basename(tmp_path)
                nomes_atuais = files_label.cget("text")
                if nomes_atuais == "Nenhum arquivo selecionado":
                    win.after(0, lambda: files_label.configure(text=nome, text_color="#00bfff"))
                else:
                    win.after(0, lambda: files_label.configure(text=f"{nomes_atuais}, {nome}", text_color="#00bfff"))
                win.after(0, lambda: countdown_label.configure(text=""))

            threading.Thread(target=do_capture, daemon=True).start()

        ctk.CTkButton(btn_frame, text="Capturar Tela", fg_color="#001a3a", hover_color="#002a5a",
                      text_color="#00bfff", border_width=1, border_color="#0a3a6a",
                      font=ctk.CTkFont(family="Courier New", size=12),
                      command=capture_screen).pack(side="left", padx=(0, 8))

        def save_entry():
            title = title_input.get().strip()
            content = content_input.get("1.0", "end").strip()
            if not content and not selected_files:
                return
            self.save_to_obsidian(title, content or "(sem texto)", selected_files or None)
            title_input.delete(0, "end")
            content_input.delete("1.0", "end")
            selected_files.clear()
            files_label.configure(text="Nenhum arquivo selecionado", text_color="#1a6b8a")
            load_entries()

        ctk.CTkButton(btn_frame, text="Salvar no Obsidian", fg_color="#003a6a", hover_color="#005a9a",
                      text_color="#00bfff", font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                      command=save_entry).pack(side="left")

        # Entradas existentes
        ctk.CTkLabel(win, text="Entradas recentes:", font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(anchor="w", padx=16)

        entries_frame = ctk.CTkScrollableFrame(win, fg_color="#060f20", corner_radius=8,
                                                border_width=1, border_color="#0a2a4a")
        entries_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        def load_entries():
            for w in entries_frame.winfo_children():
                w.destroy()
            diary_folder = self._get_diary_folder()
            try:
                files = sorted(
                    [f for f in os.listdir(diary_folder) if f.endswith(".md")],
                    reverse=True
                )[:10]
                for fname in files:
                    fpath = os.path.join(diary_folder, fname)
                    date = fname.replace(".md", "")
                    with open(fpath, "r", encoding="utf-8") as f:
                        preview = f.read()[:300]

                    card = ctk.CTkFrame(entries_frame, fg_color="#070f20", corner_radius=6)
                    card.pack(fill="x", pady=3, padx=4)
                    ctk.CTkLabel(card, text=date, font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                                 text_color="#00bfff").pack(anchor="w", padx=8, pady=(4, 0))
                    ctk.CTkLabel(card, text=preview + "...", font=ctk.CTkFont(family="Courier New", size=10),
                                 text_color="#a0d4f5", wraplength=580, justify="left").pack(anchor="w", padx=8, pady=(0, 6))
            except Exception as e:
                ctk.CTkLabel(entries_frame, text="Nenhuma entrada encontrada.", text_color="#1a6b8a").pack(pady=10)

        load_entries()


    # --------------------------------------------------------
    # SKILLS
    # --------------------------------------------------------
    def _open_skills(self):
        win = ctk.CTkToplevel(self)
        win.title("Skills - JARVIS")
        win.geometry("420x380")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        ctk.CTkLabel(win, text="SKILLS DO OBSIDIAN",
                     font=ctk.CTkFont(family="Courier New", size=16, weight="bold"),
                     text_color="#bf7fff").pack(pady=(16, 4))
        ctk.CTkLabel(win, text="Escolha uma skill para executar:",
                     font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(pady=(0, 12))

        skills = [
            ("Nota do Dia (/today)", "#003a6a", "#00bfff", self._skill_today),
            ("Revisao Semanal (/weekly-review)", "#003a6a", "#00bfff", self._skill_weekly_review),
            ("Pesquisar e Salvar (/research)", "#003a6a", "#00bfff", self._skill_research),
            ("Registrar Trade (/trade)", "#1a003a", "#bf7fff", self._skill_trade),
            ("Importar Trade do Diario", "#0a1a00", "#00ff88", self._skill_import_trade),
        ]

        for label, fg, tc, cmd in skills:
            ctk.CTkButton(win, text=label,
                          font=ctk.CTkFont(family="Courier New", size=13),
                          fg_color=fg, hover_color="#005a9a",
                          text_color=tc, height=44, corner_radius=10,
                          command=lambda c=cmd, w=win: [w.destroy(), c()]
                          ).pack(fill="x", padx=20, pady=5)

    def _skill_import_trade(self):
        diary_folder = os.path.join(OBSIDIAN_VAULT, "Diario JARVIS")
        files = sorted([f for f in os.listdir(diary_folder) if f.endswith(".md")], reverse=True)
        if not files:
            self._add_message("ERRO", "Nenhuma nota encontrada no diário.", "#ff4444")
            return

        # Le a nota mais recente
        latest = os.path.join(diary_folder, files[0])
        with open(latest, "r", encoding="utf-8") as f:
            content = f.read()

        self._add_message(USER_NAME, f"[Importando trade de: {files[0]}]", "#00ff88")
        threading.Thread(target=self._run_import_trade, args=(content, files[0]),daemon=True).start()

    def _run_import_trade(self, diary_content, filename):
        try:
            self.after(0, lambda: self._set_status("Analisando trade do diário...", "#00ff88"))
            prompt = f"""Analise o conteúdo deste diário e extraia todas as operações de trade registradas.
Para cada operação encontrada, faça uma análise completa incluindo:
- Dados da operação
- Relação risco/retorno
- Avaliação da qualidade
- Pontos positivos e de melhoria
- Nota geral (0-10)

Conteúdo do diário ({filename}):
{diary_content}"""

            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=60)
            analysis = res.json()["reply"]

            today = datetime.now().strftime("%Y-%m-%d")
            trade_path = os.path.join(OBSIDIAN_VAULT, "Trades", f"{today}-importado-diario.md")
            os.makedirs(os.path.dirname(trade_path), exist_ok=True)
            with open(trade_path, "w", encoding="utf-8") as f:
                f.write(f"# Trades Importados do Diário - {today}\n\n")
                f.write(f"**Origem:** {filename}\n\n")
                f.write(f"## Análise JARVIS\n\n{analysis}")

            self.after(0, lambda: self._add_message(ASSISTANT_NAME, analysis, "#00bfff"))
            self.after(0, lambda: self._speak("Trade importado do diário e analisado com sucesso."))
        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", str(e), "#ff4444"))

    def _skill_today(self):
        self._add_message(USER_NAME, "[Skill: Nota do Dia]", "#bf7fff")
        threading.Thread(target=self._run_skill_today, daemon=True).start()

    def _run_skill_today(self):
        try:
            self.after(0, lambda: self._set_status("Gerando nota do dia...", "#bf7fff"))
            today = datetime.now().strftime("%Y-%m-%d")
            note_path = os.path.join(OBSIDIAN_VAULT, "Diario JARVIS", f"{today}.md")

            if os.path.exists(note_path):
                msg = f"Nota do dia já existe: {note_path}"
                self.after(0, lambda: self._add_message(ASSISTANT_NAME, msg, "#00bfff"))
                self.after(0, lambda: self._speak(msg))
                return

            prompt = f"""Crie uma nota diária para hoje ({today}) no meu diário de trading e estudos.
Retorne APENAS o conteúdo markdown da nota, sem explicações adicionais.
Use este formato:
# Diário - {today}

## Prioridades do Dia
- [ ]
- [ ]
- [ ]

## Trades
(registrar operações aqui)

## Estudos
(anotar o que aprendi)

## Reflexões
(pensamentos do dia)

## Tarefas Pendentes
- [ ] """

            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=30)
            content = res.json()["reply"]

            with open(note_path, "w", encoding="utf-8") as f:
                f.write(content)

            msg = f"Nota do dia criada no Obsidian: {today}"
            self.after(0, lambda: self._add_message(ASSISTANT_NAME, msg, "#00bfff"))
            self.after(0, lambda: self._speak(msg))
        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", str(e), "#ff4444"))

    def _skill_weekly_review(self):
        self._add_message(USER_NAME, "[Skill: Revisão Semanal]", "#bf7fff")
        threading.Thread(target=self._run_skill_weekly, daemon=True).start()

    def _run_skill_weekly(self):
        try:
            self.after(0, lambda: self._set_status("Analisando semana...", "#bf7fff"))
            diary_folder = os.path.join(OBSIDIAN_VAULT, "Diario JARVIS")
            files = sorted([f for f in os.listdir(diary_folder) if f.endswith(".md")], reverse=True)[:7]

            all_content = ""
            for fname in files:
                fpath = os.path.join(diary_folder, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    all_content += f"\n\n### {fname}\n{f.read()}"

            if not all_content:
                msg = "Nenhuma nota encontrada para revisar."
                self.after(0, lambda: self._add_message(ASSISTANT_NAME, msg, "#00bfff"))
                return

            prompt = f"Faça uma revisão semanal detalhada das minhas notas. Analise trades, estudos, padrões e dê feedback honesto:\n\n{all_content[:6000]}"
            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=60)
            review = res.json()["reply"]

            today = datetime.now().strftime("%Y-%m-%d")
            review_path = os.path.join(OBSIDIAN_VAULT, "Trades", f"revisao-semanal-{today}.md")
            os.makedirs(os.path.dirname(review_path), exist_ok=True)
            with open(review_path, "w", encoding="utf-8") as f:
                f.write(f"# Revisão Semanal - {today}\n\n{review}")

            self.after(0, lambda: self._add_message(ASSISTANT_NAME, review, "#00bfff"))
            self.after(0, lambda: self._speak(f"Revisão semanal gerada e salva no Obsidian, Xande."))
        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", str(e), "#ff4444"))

    def _skill_research(self):
        win = ctk.CTkToplevel(self)
        win.title("Pesquisar")
        win.geometry("420x160")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        ctk.CTkLabel(win, text="Tema da pesquisa:",
                     font=ctk.CTkFont(family="Courier New", size=12),
                     text_color="#1a6b8a").pack(pady=(16, 4), padx=20, anchor="w")

        inp = ctk.CTkEntry(win, fg_color="#060f20", border_color="#0a3a6a",
                           text_color="#a0d4f5", font=ctk.CTkFont(family="Courier New", size=12), height=40)
        inp.pack(fill="x", padx=20, pady=4)

        def run():
            topic = inp.get().strip()
            if not topic:
                return
            win.destroy()
            self._add_message(USER_NAME, f"[Pesquisa: {topic}]", "#bf7fff")
            threading.Thread(target=self._run_skill_research, args=(topic,), daemon=True).start()

        ctk.CTkButton(win, text="Pesquisar e Salvar no Obsidian",
                      fg_color="#003a6a", text_color="#00bfff",
                      font=ctk.CTkFont(family="Courier New", size=12),
                      height=40, command=run).pack(fill="x", padx=20, pady=8)
        inp.bind("<Return>", lambda e: run())

    def _run_skill_research(self, topic):
        try:
            self.after(0, lambda: self._set_status(f"Pesquisando: {topic}...", "#bf7fff"))
            prompt = f"""Pesquise sobre '{topic}' e me retorne um relatório completo em markdown com:
- Resumo executivo
- Pontos principais
- Aplicação prática para trading (se relevante)
- Conclusão

Retorne APENAS o conteúdo markdown."""

            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=60)
            content = res.json()["reply"]

            safe_topic = "".join(c for c in topic if c.isalnum() or c in " -_").strip()
            research_path = os.path.join(OBSIDIAN_VAULT, "Recursos", f"{safe_topic}.md")
            os.makedirs(os.path.dirname(research_path), exist_ok=True)
            with open(research_path, "w", encoding="utf-8") as f:
                f.write(f"# {topic}\n\n{content}")

            self.after(0, lambda: self._add_message(ASSISTANT_NAME, content[:500] + "...", "#00bfff"))
            self.after(0, lambda: self._speak(f"Pesquisa sobre {topic} salva no Obsidian."))
        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", str(e), "#ff4444"))

    def _skill_trade(self):
        win = ctk.CTkToplevel(self)
        win.title("Registrar Trade")
        win.geometry("450x350")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        ctk.CTkLabel(win, text="REGISTRAR TRADE",
                     font=ctk.CTkFont(family="Courier New", size=14, weight="bold"),
                     text_color="#bf7fff").pack(pady=(12, 8))

        fields = {}
        labels = ["Ativo", "Entrada", "Saída", "Stop Loss", "Resultado (pips/pontos)"]
        for lbl in labels:
            ctk.CTkLabel(win, text=lbl + ":", font=ctk.CTkFont(family="Courier New", size=11),
                         text_color="#1a6b8a").pack(anchor="w", padx=20)
            e = ctk.CTkEntry(win, fg_color="#060f20", border_color="#0a3a6a",
                             text_color="#a0d4f5", font=ctk.CTkFont(family="Courier New", size=12), height=32)
            e.pack(fill="x", padx=20, pady=(0, 4))
            fields[lbl] = e

        def run():
            data = {k: v.get().strip() for k, v in fields.items()}
            win.destroy()
            self._add_message(USER_NAME, f"[Trade: {data.get('Ativo', '')}]", "#bf7fff")
            threading.Thread(target=self._run_skill_trade, args=(data,), daemon=True).start()

        ctk.CTkButton(win, text="Analisar e Salvar no Obsidian",
                      fg_color="#1a003a", text_color="#bf7fff",
                      font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                      height=40, command=run).pack(fill="x", padx=20, pady=8)

    def _run_skill_trade(self, data):
        try:
            self.after(0, lambda: self._set_status("Analisando trade...", "#bf7fff"))
            prompt = f"""Analise este trade e dê um feedback detalhado:
Ativo: {data.get('Ativo')}
Entrada: {data.get('Entrada')}
Saída: {data.get('Saída')}
Stop Loss: {data.get('Stop Loss')}
Resultado: {data.get('Resultado (pips/pontos)')}

Calcule a relação risco/retorno, avalie a qualidade da operação e sugira melhorias.
Retorne a análise em markdown."""

            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=30)
            analysis = res.json()["reply"]

            today = datetime.now().strftime("%Y-%m-%d")
            ativo = data.get("Ativo", "trade").replace("/", "-")
            trade_path = os.path.join(OBSIDIAN_VAULT, "Trades", f"{today}-{ativo}.md")
            os.makedirs(os.path.dirname(trade_path), exist_ok=True)
            with open(trade_path, "w", encoding="utf-8") as f:
                f.write(f"# Trade - {ativo} - {today}\n\n")
                for k, v in data.items():
                    f.write(f"**{k}:** {v}\n")
                f.write(f"\n## Análise JARVIS\n\n{analysis}")

            self.after(0, lambda: self._add_message(ASSISTANT_NAME, analysis, "#00bfff"))
            self.after(0, lambda: self._speak(f"Trade analisado e salvo no Obsidian."))
        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", str(e), "#ff4444"))

    # --------------------------------------------------------
    # YOUTUBE
    # --------------------------------------------------------
    def _open_youtube(self):
        win = ctk.CTkToplevel(self)
        win.title("YouTube - JARVIS")
        win.geometry("500x200")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        ctk.CTkLabel(win, text="ANALISAR VIDEO DO YOUTUBE",
                     font=ctk.CTkFont(family="Courier New", size=14, weight="bold"),
                     text_color="#00bfff").pack(pady=(16, 8))

        ctk.CTkLabel(win, text="Cole o link do vídeo:",
                     font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(anchor="w", padx=20)

        url_input = ctk.CTkEntry(win, fg_color="#060f20", border_color="#0a3a6a",
                                 text_color="#a0d4f5", font=ctk.CTkFont(family="Courier New", size=12),
                                 height=40)
        url_input.pack(fill="x", padx=20, pady=8)

        def analisar():
            url = url_input.get().strip()
            if not url:
                return
            win.destroy()
            threading.Thread(target=self._process_youtube, args=(url,), daemon=True).start()

        ctk.CTkButton(win, text="Analisar Vídeo", fg_color="#003a6a", hover_color="#005a9a",
                      text_color="#00bfff", font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                      height=40, command=analisar).pack(fill="x", padx=20, pady=(0, 16))

        url_input.bind("<Return>", lambda e: analisar())

    def _process_youtube(self, url):
        try:
            self.after(0, lambda: self._set_status("Buscando transcrição...", "#00bfff"))
            self.after(0, lambda: self._add_message(USER_NAME, f"[YouTube: {url}]", "#ffaa00"))

            # Extrai o ID do video
            if "v=" in url:
                video_id = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
            else:
                raise ValueError("Link inválido")

            # Busca transcricao
            ytt = YouTubeTranscriptApi()
            try:
                transcript_list = ytt.fetch(video_id, languages=["pt", "pt-BR", "en"])
            except Exception:
                transcript_list = ytt.fetch(video_id)
            transcript = " ".join([t.text for t in transcript_list])

            if not transcript:
                raise ValueError("Vídeo sem transcrição disponível")

            prompt = f"Analisei a transcrição de um vídeo do YouTube. Faça um resumo completo e detalhado, explicando os pontos principais de forma didática:\n\n{transcript[:8000]}"

            self.after(0, lambda: self._set_status("JARVIS analisando vídeo...", "#00bfff"))
            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=60)
            res.raise_for_status()
            reply = res.json()["reply"]

            self.after(0, lambda: self._add_message(ASSISTANT_NAME, reply, "#00bfff"))
            self.after(0, lambda: self._speak(reply))

        except Exception as e:
            msg = f"Erro ao processar vídeo: {str(e)}"
            self.after(0, lambda: self._add_message("ERRO", msg, "#ff4444"))
            self.after(0, lambda: self._set_status("Erro.", "#ff4444"))

    # --------------------------------------------------------
    # PDF / MODO ESTUDO
    # --------------------------------------------------------
    def _open_pdf(self):
        path = filedialog.askopenfilename(
            title="Selecionar PDF",
            filetypes=[("PDF", "*.pdf")]
        )
        if not path:
            return

        self._set_status("Lendo PDF...", "#00bfff")
        threading.Thread(target=self._extract_and_study_pdf, args=(path,), daemon=True).start()

    def _extract_and_study_pdf(self, path):
        try:
            text = ""
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:60]:
                    text += page.extract_text() or ""

            if not text.strip():
                self.after(0, lambda: self._add_message("ERRO", "Nao foi possivel extrair texto do PDF.", "#ff4444"))
                return

            filename = os.path.basename(path)
            self.after(0, lambda: self._add_message(USER_NAME, f"[PDF: {filename}]", "#ffaa00"))
            self.after(0, lambda: self._set_status("Gerando material de estudo...", "#00ff88"))

            # Ativa modo estudo para perguntas futuras
            self.after(0, lambda: self._start_study_mode(filename, text, silent=True))

            # Gera todo o material em uma unica chamada
            prompt = f"""Analise o PDF '{filename}' e gere um material de estudo completo com as seguintes secoes em markdown:

## Resumo Completo
Resumo detalhado e didatico de todos os topicos principais do documento.

## Flashcards
Liste pelo menos 15 flashcards no formato:
**P:** (pergunta)
**R:** (resposta)

## Exercicios
Crie pelo menos 8 exercicios de fixacao com gabarito ao final.

## Mapa Mental
Represente a estrutura do documento em hierarquia de topicos:
### Tema Central: [titulo principal]
- **Topico 1**
  - Subtopico 1.1
  - Subtopico 1.2
- **Topico 2**
  ...

Conteudo do PDF:
{text[:22000]}"""

            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=180)
            res.raise_for_status()
            material = res.json()["reply"]

            # Salva no Obsidian - pasta Estudos
            self.after(0, lambda: self._save_study_to_obsidian(filename, material))

            # Mostra resumo no chat (primeiros 600 chars) e avisa que foi salvo
            preview = material[:600] + "..." if len(material) > 600 else material
            self.after(0, lambda: self._add_message(ASSISTANT_NAME, preview, "#00bfff"))
            saved_msg = f"Material completo salvo no Obsidian em Estudos/{os.path.splitext(filename)[0]}."
            self.after(0, lambda: self._add_message(ASSISTANT_NAME, saved_msg, "#00ff88"))
            self.after(0, lambda: self._speak(f"Material de estudo gerado e salvo no Obsidian. Pode me fazer perguntas sobre o conteudo."))

        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", f"Erro ao processar PDF: {str(e)}", "#ff4444"))
            self.after(0, lambda: self._set_status("Erro.", "#ff4444"))

    def _save_study_to_obsidian(self, filename, material):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            basename = os.path.splitext(filename)[0]
            study_folder = os.path.join(OBSIDIAN_VAULT, "Estudos")
            os.makedirs(study_folder, exist_ok=True)
            note_path = os.path.join(study_folder, f"{basename}.md")

            header = f"---\ntags: [estudo, pdf]\ndata: {today}\nfonte: {filename}\n---\n\n# {basename}\n\n"
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(header + material)
        except Exception as e:
            self.after(0, lambda: self._add_message("ERRO", f"Erro ao salvar no Obsidian: {str(e)}", "#ff4444"))

    def _start_study_mode(self, filename, text, silent=False):
        self.study_pdf = (filename, text)
        short_name = filename if len(filename) <= 40 else filename[:37] + "..."
        self.study_label.configure(text=f"Modo Estudo ativo: {short_name}")
        self.study_banner.pack(fill="x", padx=20, pady=(0, 6), before=self.chat_frame)

        if not silent:
            intro = f"[Modo Estudo: {filename}]"
            self._add_message(USER_NAME, intro, "#00ff88")
            prompt = (f"Acabei de carregar o PDF '{filename}' para estudarmos juntos. "
                      f"Aqui esta o conteudo:\n\n{text[:20000]}\n\n"
                      f"Apresente-se como meu tutor e me diga o tema e estrutura principal do documento.")
            threading.Thread(target=self._get_ai_response, args=(prompt,), daemon=True).start()

    def _stop_study_mode(self):
        self.study_pdf = None
        self.study_banner.pack_forget()
        self._add_message(ASSISTANT_NAME, "Modo de estudo encerrado.", "#00ff88")


# ============================================================
# INICIAR
# ============================================================
if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
