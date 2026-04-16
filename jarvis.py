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
from elevenlabs.client import ElevenLabs
import pygame
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ASSISTANT_NAME, USER_NAME, LANGUAGE, OBSIDIAN_VAULT

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

        # Inicializa ElevenLabs
        self.eleven = ElevenLabs(api_key=ELEVENLABS_API_KEY)
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
    def _speak(self, text):
        self.is_speaking = True
        self._set_status("Falando...", "#00bfff")
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text):
        try:
            audio = self.eleven.text_to_speech.convert(
                voice_id=ELEVENLABS_VOICE_ID,
                text=text,
                model_id="eleven_multilingual_v2"
            )
            # Salva em arquivo temporario e toca
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                for chunk in audio:
                    f.write(chunk)
                tmp_path = f.name

            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            os.unlink(tmp_path)
        except Exception as e:
            print(f"Erro TTS: {e}")
        finally:
            self.is_speaking = False
            self.after(0, lambda: self._set_status("Aguardando...", "#1a6b8a"))

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
            height=42,
            corner_radius=10
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_input.bind("<Return>", lambda e: self._send_text())

        self.send_btn = ctk.CTkButton(
            bottom_frame,
            text="Enviar",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            fg_color="#003a6a",
            hover_color="#005a9a",
            text_color="#00bfff",
            width=80,
            height=42,
            corner_radius=10,
            command=self._send_text
        )
        self.send_btn.pack(side="left", padx=(0, 8))

        self.mic_btn = ctk.CTkButton(
            bottom_frame,
            text="Microfone",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            fg_color="#001a3a",
            hover_color="#002a5a",
            text_color="#00bfff",
            border_width=1,
            border_color="#0a3a6a",
            width=100,
            height=42,
            corner_radius=10,
            command=self._toggle_listen
        )
        self.mic_btn.pack(side="left", padx=(0, 8))

        self.diary_btn = ctk.CTkButton(
            bottom_frame,
            text="Diario",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            fg_color="#001a3a",
            hover_color="#002a5a",
            text_color="#00bfff",
            border_width=1,
            border_color="#0a3a6a",
            width=80,
            height=42,
            corner_radius=10,
            command=self._open_diary
        )
        self.diary_btn.pack(side="left")

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

    def _process_input(self, text):
        self._add_message(USER_NAME, text, "#ffaa00")
        self._set_status("Pensando...", "#00bfff")
        threading.Thread(target=self._get_ai_response, args=(text,), daemon=True).start()

    def _get_ai_response(self, text):
        try:
            res = requests.post(
                f"{SERVER_URL}/chat",
                json={"message": text},
                timeout=30
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


# ============================================================
# INICIAR
# ============================================================
if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
