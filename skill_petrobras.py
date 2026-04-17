import os
import threading
import requests
from datetime import datetime
from tkinter import filedialog
import customtkinter as ctk
import pdfplumber

VAULT = None  # preenchido pelo JarvisApp

TOPICOS = {
    "gestao de estoques": ("200 - Bloco I", "Gestao de Estoques"),
    "estoque": ("200 - Bloco I", "Gestao de Estoques"),
    "gestao de compras": ("200 - Bloco I", "Gestao de Compras"),
    "compras": ("200 - Bloco I", "Gestao de Compras"),
    "procurement": ("200 - Bloco I", "Gestao de Compras"),
    "supply chain": ("200 - Bloco I", "Supply Chain"),
    "cadeia de suprimentos": ("200 - Bloco I", "Supply Chain"),
    "gestao de contratos": ("200 - Bloco I", "Gestao de Contratos"),
    "contratos": ("200 - Bloco I", "Gestao de Contratos"),
    "logistica": ("200 - Bloco I", "Logistica Empresarial"),
    "logística": ("200 - Bloco I", "Logistica Empresarial"),
    "fornecedores": ("200 - Bloco I", "Gestao de Fornecedores"),
    "planejamento estrategico": ("200 - Bloco I", "Planejamento Estrategico"),
    "planejamento estratégico": ("200 - Bloco I", "Planejamento Estrategico"),
    "gestao de projetos": ("200 - Bloco I", "Gestao de Projetos"),
    "projetos": ("200 - Bloco I", "Gestao de Projetos"),
    "processos": ("200 - Bloco I", "Processos Organizacionais"),
    "indicadores": ("200 - Bloco I", "Indicadores de Desempenho"),
    "kpi": ("200 - Bloco I", "Indicadores de Desempenho"),
    "qualidade": ("200 - Bloco I", "Gestao de Qualidade"),
    "iso": ("200 - Bloco I", "Gestao de Qualidade"),
    "lei 13303": ("300 - Bloco II", "Lei 13303"),
    "13.303": ("300 - Bloco II", "Lei 13303"),
    "estatais": ("300 - Bloco II", "Lei 13303"),
    "rlcp": ("300 - Bloco II", "RLCP Petrobras"),
    "licitacao": ("300 - Bloco II", "RLCP Petrobras"),
    "licitação": ("300 - Bloco II", "RLCP Petrobras"),
    "compliance": ("300 - Bloco II", "Compliance"),
    "integridade": ("300 - Bloco II", "Compliance"),
    "governanca": ("300 - Bloco II", "Governanca Corporativa"),
    "governança": ("300 - Bloco II", "Governanca Corporativa"),
    "contabilidade geral": ("400 - Bloco III", "Contabilidade Geral"),
    "balanco": ("400 - Bloco III", "Contabilidade Geral"),
    "balanço": ("400 - Bloco III", "Contabilidade Geral"),
    "contabilidade gerencial": ("400 - Bloco III", "Contabilidade Gerencial"),
    "custos": ("400 - Bloco III", "Contabilidade Gerencial"),
    "demonstracoes": ("400 - Bloco III", "Analise de Demonstracoes"),
    "demonstrações": ("400 - Bloco III", "Analise de Demonstracoes"),
    "tributario": ("400 - Bloco III", "Tributario"),
    "tributário": ("400 - Bloco III", "Tributario"),
    "tributos": ("400 - Bloco III", "Tributario"),
    "portugues": ("100 - Basicos/Portugues", "Portugues"),
    "português": ("100 - Basicos/Portugues", "Portugues"),
    "ingles": ("100 - Basicos/Ingles", "Ingles"),
    "inglês": ("100 - Basicos/Ingles", "Ingles"),
    "matematica": ("100 - Basicos/Matematica", "Matematica"),
    "matemática": ("100 - Basicos/Matematica", "Matematica"),
    "raciocinio logico": ("100 - Basicos/Matematica", "Matematica"),
}

BLOCOS = {
    "200 - Bloco I": "Bloco I — Administração e Logística",
    "300 - Bloco II": "Bloco II — Legislação",
    "400 - Bloco III": "Bloco III — Contabilidade e Tributário",
    "100 - Basicos/Portugues": "Básicos — Português",
    "100 - Basicos/Ingles": "Básicos — Inglês",
    "100 - Basicos/Matematica": "Básicos — Matemática",
}


def detectar_pasta(texto_pdf, filename):
    texto_lower = (texto_pdf[:3000] + filename).lower()
    for chave, (pasta, nome) in TOPICOS.items():
        if chave in texto_lower:
            return pasta, nome
    return "Estudos", os.path.splitext(filename)[0]


class PetrobrasStudy:
    def __init__(self, app):
        self.app = app
        global VAULT
        VAULT = app.obsidian_vault if hasattr(app, "obsidian_vault") else self._get_vault()

    def _get_vault(self):
        try:
            from config import OBSIDIAN_VAULT
            return OBSIDIAN_VAULT
        except Exception:
            return "E:\\obsidian"

    def open_window(self):
        win = ctk.CTkToplevel(self.app)
        win.title("Petrobras — Carregar Aula")
        win.geometry("480x280")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        ctk.CTkLabel(win, text="PETROBRAS — CARREGAR AULA",
                     font=ctk.CTkFont(family="Courier New", size=14, weight="bold"),
                     text_color="#00ff88").pack(pady=(16, 4))

        # Campo de link da aula
        ctk.CTkLabel(win, text="Link da aula (opcional):",
                     font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(anchor="w", padx=20)
        link_input = ctk.CTkEntry(win, placeholder_text="https://hotmart.com/...",
                                  fg_color="#060f20", border_color="#0a3a6a",
                                  text_color="#a0d4f5",
                                  font=ctk.CTkFont(family="Courier New", size=12), height=36)
        link_input.pack(fill="x", padx=20, pady=(2, 12))

        # Seletor de bloco manual
        ctk.CTkLabel(win, text="Bloco (deixe em branco para detectar automaticamente):",
                     font=ctk.CTkFont(family="Courier New", size=11),
                     text_color="#1a6b8a").pack(anchor="w", padx=20)

        bloco_var = ctk.StringVar(value="Detectar automaticamente")
        bloco_menu = ctk.CTkOptionMenu(
            win,
            values=["Detectar automaticamente",
                    "Básicos — Português", "Básicos — Inglês", "Básicos — Matemática",
                    "Bloco I — Administração e Logística",
                    "Bloco II — Legislação",
                    "Bloco III — Contabilidade e Tributário"],
            variable=bloco_var,
            fg_color="#060f20", button_color="#003a6a",
            font=ctk.CTkFont(family="Courier New", size=12)
        )
        bloco_menu.pack(fill="x", padx=20, pady=(2, 16))

        def selecionar_pdf():
            path = filedialog.askopenfilename(
                parent=win,
                title="Selecionar PDF da aula",
                filetypes=[("PDF", "*.pdf")]
            )
            if not path:
                return
            link = link_input.get().strip()
            bloco_escolhido = bloco_var.get()
            win.destroy()
            threading.Thread(
                target=self.processar,
                args=(path, link, bloco_escolhido),
                daemon=True
            ).start()

        ctk.CTkButton(win, text="Selecionar PDF da Aula",
                      font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                      fg_color="#0a2a00", hover_color="#1a4a00",
                      text_color="#00ff88", border_width=1, border_color="#00ff88",
                      height=44, corner_radius=10,
                      command=selecionar_pdf).pack(fill="x", padx=20)

    def processar(self, path, link, bloco_escolhido):
        try:
            filename = os.path.basename(path)
            self.app.after(0, lambda: self.app._add_message("Xande", f"[Petrobras PDF: {filename}]", "#00ff88"))
            self.app.after(0, lambda: self.app._set_status("Lendo PDF...", "#00ff88"))

            texto = ""
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:60]:
                    texto += page.extract_text() or ""

            if not texto.strip():
                self.app.after(0, lambda: self.app._add_message("ERRO", "Nao foi possivel extrair texto do PDF.", "#ff4444"))
                return

            # Detecta pasta de destino
            if bloco_escolhido == "Detectar automaticamente":
                pasta, nome_nota = detectar_pasta(texto, filename)
            else:
                pasta = next((k for k, v in BLOCOS.items() if v == bloco_escolhido), "Estudos")
                nome_nota = os.path.splitext(filename)[0]

            self.app.after(0, lambda: self.app._set_status(f"Gerando material: {nome_nota}...", "#00ff88"))

            # Monta link da aula se fornecido
            secao_video = ""
            if link:
                secao_video = f"\n## Aula em Video\n\n[Assistir aula]({link})\n"

            prompt = f"""Analise o PDF '{filename}' (tema: {nome_nota}) e gere material completo de estudo para concurso da Petrobras (banca Cesgranrio) com as seguintes secoes em markdown:

## Resumo Completo
Resumo detalhado e didatico de todos os topicos do documento, com exemplos praticos.

## Pontos-Chave para a Prova
Liste os 10 conceitos mais provaveis de cair na prova Cesgranrio.

## Flashcards
Minimo de 20 flashcards no formato:
**P:** (pergunta objetiva)
**R:** (resposta direta)

## Exercicios Estilo Cesgranrio
Crie 10 questoes de multipla escolha (A a E) com gabarito e explicacao ao final.

## Mapa Mental
### Tema Central: {nome_nota}
- **Topico 1**
  - Subtopico 1.1
  - Subtopico 1.2
(continue com todos os topicos)

Conteudo do PDF:
{texto[:22000]}"""

            from config import ELEVENLABS_API_KEY
            server_url = self.app.__class__.__module__
            SERVER_URL = "https://web-production-b9c17.up.railway.app"

            res = requests.post(f"{SERVER_URL}/chat", json={"message": prompt}, timeout=180)
            res.raise_for_status()
            material = res.json()["reply"]

            # Salva no Obsidian
            self._salvar_obsidian(pasta, nome_nota, filename, material, secao_video, link)

            preview = material[:500] + "..." if len(material) > 500 else material
            self.app.after(0, lambda: self.app._add_message("Jarvis", preview, "#00bfff"))
            msg_salvo = f"Material salvo em: {pasta}/{nome_nota}.md"
            self.app.after(0, lambda: self.app._add_message("Jarvis", msg_salvo, "#00ff88"))
            self.app.after(0, lambda: self.app._set_status("Aguardando...", "#1a6b8a"))

            # Ativa modo estudo
            self.app.after(0, lambda: self.app._start_study_mode(filename, texto, silent=True))
            self.app.after(0, lambda: self.app._speak(f"Material de {nome_nota} gerado e salvo no Obsidian."))

        except Exception as e:
            self.app.after(0, lambda: self.app._add_message("ERRO", f"Erro: {str(e)}", "#ff4444"))
            self.app.after(0, lambda: self.app._set_status("Erro.", "#ff4444"))

    def _separar_questoes(self, material):
        """Separa a secao de exercicios. Reformata para gabarito apenas no final."""
        import re
        padrao = re.compile(r'(##\s*Exerc[ií]cios.*?)(?=\n##\s|\Z)', re.DOTALL | re.IGNORECASE)
        match = padrao.search(material)
        if not match:
            return material, None

        bloco = match.group(1).strip()
        material_limpo = (material[:match.start()].strip() + "\n\n" + material[match.end():].strip()).strip()

        # Separa gabarito inline e coloca no final
        q_pattern = re.compile(
            r'(\*\*Questão\s*\d+\*\*.*?)'
            r'(\*\*Gabarito:\s*[A-E]\*\*.*?)(?=\*\*Questão|\Z)',
            re.DOTALL
        )
        questoes_limpas = []
        gabaritosfinal = []
        num = 1
        for m in q_pattern.finditer(bloco):
            enunciado = m.group(1).strip()
            gabarito_raw = m.group(2).strip()
            # Extrai letra e explicacao
            letra = re.search(r'Gabarito:\s*([A-E])', gabarito_raw)
            letra = letra.group(1) if letra else "?"
            explicacao = re.sub(r'\*\*Gabarito:\s*[A-E]\*\*\s*', '', gabarito_raw).strip()
            # Converte opcoes "(A) texto" em checkboxes "- [ ] (A) texto"
            enunciado = re.sub(r'^\(([A-E])\)', r'- [ ] (\1)', enunciado, flags=re.MULTILINE)
            questoes_limpas.append(enunciado)
            gabaritosfinal.append(f"**Q{num}: {letra}** — {explicacao}")
            num += 1

        if questoes_limpas:
            corpo = "\n\n---\n\n".join(questoes_limpas)
            rodape = "\n\n---\n\n## Gabarito\n\n" + "\n\n".join(gabaritosfinal)
            questoes_formatadas = "## Exercícios Estilo Cesgranrio\n\n" + corpo + rodape
        else:
            questoes_formatadas = bloco  # fallback se nao conseguiu parsear

        return material_limpo, questoes_formatadas

    def _pasta_questoes(self, pasta):
        """Retorna a subpasta de questoes correspondente ao bloco."""
        mapa = {
            "200 - Bloco I": "500 - Questoes/Bloco I",
            "300 - Bloco II": "500 - Questoes/Bloco II",
            "400 - Bloco III": "500 - Questoes/Bloco III",
            "100 - Basicos/Portugues": "500 - Questoes/Basicos",
            "100 - Basicos/Ingles": "500 - Questoes/Basicos",
            "100 - Basicos/Matematica": "500 - Questoes/Basicos",
        }
        return mapa.get(pasta, "500 - Questoes")

    def _salvar_obsidian(self, pasta, nome_nota, filename, material, secao_video, link):
        vault = self._get_vault()
        today = datetime.now().strftime("%Y-%m-%d")

        # Separa questoes do material principal
        material_principal, questoes = self._separar_questoes(material)

        pasta_destino = os.path.join(vault, pasta)
        os.makedirs(pasta_destino, exist_ok=True)
        note_path = os.path.join(pasta_destino, f"{nome_nota}.md")

        # Salva questoes em 500 - Questoes se existirem
        if questoes:
            pasta_q = os.path.join(vault, self._pasta_questoes(pasta))
            os.makedirs(pasta_q, exist_ok=True)
            q_path = os.path.join(pasta_q, f"{nome_nota} — Questoes.md")
            with open(q_path, "w", encoding="utf-8") as f:
                f.write(f"---\ntitulo: \"{nome_nota} — Questoes\"\nbloco: \"{pasta}\"\ndata: {today}\ntags: [petrobras, questoes]\n---\n\n")
                f.write(f"# Questoes — {nome_nota}\n\n")
                f.write(f"> Fonte: [[{pasta}/{nome_nota}|{nome_nota}]]\n\n")
                f.write(questoes)
            material = material_principal + f"\n\n> Questoes salvas em [[{self._pasta_questoes(pasta)}/{nome_nota} — Questoes|Questoes — {nome_nota}]]\n"

        video_frontmatter = f'\nvideo_aula: "{link}"' if link else ""
        header = (
            f"---\n"
            f"titulo: \"{nome_nota}\"\n"
            f"bloco: \"{pasta}\"\n"
            f"data: {today}\n"
            f"status: \"🟡 revisar\"\n"
            f"fonte: \"{filename}\"\n"
            f"tags: [petrobras, estudo]\n"
            f"{video_frontmatter}"
            f"---\n\n"
            f"# {nome_nota}\n"
            f"{secao_video}\n"
        )

        with open(note_path, "w", encoding="utf-8") as f:
            f.write(header + material)


# ============================================================
# QUIZ WINDOW
# ============================================================
class QuizWindow:
    """Janela de quiz interativo a partir de um arquivo de questoes do vault."""

    def __init__(self, app):
        self.app = app

    def abrir(self):
        vault = self.app.obsidian_vault if hasattr(self.app, "obsidian_vault") else "E:\\obsidian"
        path = filedialog.askopenfilename(
            title="Selecionar arquivo de questoes",
            initialdir=os.path.join(vault, "500 - Questoes"),
            filetypes=[("Markdown", "*.md")]
        )
        if not path:
            return
        questoes = self._parsear(path)
        if not questoes:
            import tkinter.messagebox as mb
            mb.showerror("Erro", "Nenhuma questao encontrada no arquivo.")
            return
        self._mostrar(questoes, os.path.basename(path).replace(".md", ""))

    def _parsear(self, path):
        import re
        with open(path, "r", encoding="utf-8") as f:
            texto = f.read()

        # Remove secao de gabarito para nao contaminar
        texto = re.split(r'\n##\s*Gabarito', texto)[0]

        # Detecta blocos de questao
        blocos = re.split(r'\n(?=\*\*Questão\s*\d+)', texto)
        questoes = []
        for bloco in blocos:
            bloco = bloco.strip()
            if not bloco:
                continue
            # Extrai enunciado (tudo antes das alternativas)
            linhas = bloco.split("\n")
            enunciado_linhas = []
            alternativas = {}
            for linha in linhas:
                m = re.match(r'^\(([A-E])\)\s+(.*)', linha.strip())
                if m:
                    alternativas[m.group(1)] = m.group(2).strip()
                else:
                    enunciado_linhas.append(linha)
            enunciado = "\n".join(enunciado_linhas).strip()
            enunciado = re.sub(r'\*\*Questão\s*\d+\*\*\s*', '', enunciado).strip()
            if enunciado and len(alternativas) >= 4:
                questoes.append({"enunciado": enunciado, "alternativas": alternativas})
        return questoes

    def _mostrar(self, questoes, titulo):
        win = ctk.CTkToplevel(self.app)
        win.title(f"Quiz — {titulo}")
        win.geometry("700x620")
        win.configure(fg_color="#050d1a")
        win.grab_set()

        respostas = {}   # idx -> letra escolhida
        gabaritos = {}   # sera preenchido ao revelar
        idx = [0]        # questao atual

        # Cabecalho
        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 4))

        titulo_label = ctk.CTkLabel(header, text=titulo,
                                    font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                                    text_color="#00ff88")
        titulo_label.pack(side="left")

        self.progresso_label = ctk.CTkLabel(header, text="",
                                            font=ctk.CTkFont(family="Courier New", size=12),
                                            text_color="#1a6b8a")
        self.progresso_label.pack(side="right")

        # Enunciado
        enunciado_box = ctk.CTkTextbox(win, fg_color="#060f20", border_color="#0a3a6a",
                                       text_color="#a0d4f5",
                                       font=ctk.CTkFont(family="Courier New", size=12),
                                       height=140, wrap="word", state="disabled")
        enunciado_box.pack(fill="x", padx=20, pady=(8, 4))

        # Feedback
        feedback_label = ctk.CTkLabel(win, text="",
                                      font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                                      text_color="#ffaa00")
        feedback_label.pack(pady=(0, 4))

        # Frame de alternativas
        alt_frame = ctk.CTkFrame(win, fg_color="transparent")
        alt_frame.pack(fill="x", padx=20, pady=4)

        alt_buttons = {}

        # Navegacao
        nav = ctk.CTkFrame(win, fg_color="transparent")
        nav.pack(fill="x", padx=20, pady=8)

        anterior_btn = ctk.CTkButton(nav, text="Anterior",
                                     font=ctk.CTkFont(family="Courier New", size=12),
                                     fg_color="#001a3a", hover_color="#002a5a",
                                     text_color="#00bfff", width=100, height=36)
        anterior_btn.pack(side="left")

        proximo_btn = ctk.CTkButton(nav, text="Proxima",
                                    font=ctk.CTkFont(family="Courier New", size=12),
                                    fg_color="#003a6a", hover_color="#005a9a",
                                    text_color="#00bfff", width=100, height=36)
        proximo_btn.pack(side="left", padx=8)

        finalizar_btn = ctk.CTkButton(nav, text="Ver Resultado",
                                      font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
                                      fg_color="#1a0030", hover_color="#2a0050",
                                      text_color="#bf7fff", width=130, height=36)
        finalizar_btn.pack(side="right")

        def carregar_questao(i):
            q = questoes[i]
            # Enunciado
            enunciado_box.configure(state="normal")
            enunciado_box.delete("1.0", "end")
            enunciado_box.insert("1.0", q["enunciado"])
            enunciado_box.configure(state="disabled")

            # Limpa alternativas
            for w in alt_frame.winfo_children():
                w.destroy()
            alt_buttons.clear()
            feedback_label.configure(text="")

            resp_atual = respostas.get(i)
            for letra in sorted(q["alternativas"].keys()):
                texto_alt = q["alternativas"][letra]
                cor = "#003a6a" if resp_atual != letra else "#005a9a"
                borda = "#0a3a6a" if resp_atual != letra else "#00bfff"

                def marcar(l=letra, qi=i):
                    respostas[qi] = l
                    carregar_questao(qi)

                btn = ctk.CTkButton(alt_frame,
                                    text=f"({letra})  {texto_alt}",
                                    font=ctk.CTkFont(family="Courier New", size=12),
                                    fg_color=cor, hover_color="#005a9a",
                                    text_color="#a0d4f5",
                                    border_width=1, border_color=borda,
                                    anchor="w", height=36, corner_radius=6,
                                    command=marcar)
                btn.pack(fill="x", pady=2)
                alt_buttons[letra] = btn

            self.progresso_label.configure(
                text=f"Questão {i+1} de {len(questoes)}  |  Respondidas: {len(respostas)}"
            )

        def anterior():
            if idx[0] > 0:
                idx[0] -= 1
                carregar_questao(idx[0])

        def proximo():
            if idx[0] < len(questoes) - 1:
                idx[0] += 1
                carregar_questao(idx[0])

        def ver_resultado():
            acertos = 0
            detalhes = []
            # Busca gabarito no arquivo
            import re
            with open(path if hasattr(self, '_ultimo_path') else "", "r", encoding="utf-8") as f:
                conteudo = f.read()
            gab_match = re.findall(r'\*\*Q(\d+):\s*([A-E])\*\*', conteudo)
            gab_dict = {int(n): l for n, l in gab_match}

            for i, q in enumerate(questoes):
                resp = respostas.get(i, "—")
                correto = gab_dict.get(i + 1, "?")
                acertou = resp == correto
                if acertou:
                    acertos += 1
                detalhes.append(f"Q{i+1}: sua resposta ({resp}) | gabarito ({correto}) {'✓' if acertou else '✗'}")

            # Janela de resultado
            res_win = ctk.CTkToplevel(win)
            res_win.title("Resultado")
            res_win.geometry("500x500")
            res_win.configure(fg_color="#050d1a")
            res_win.grab_set()

            pct = int(acertos / len(questoes) * 100) if questoes else 0
            cor_nota = "#00ff88" if pct >= 70 else "#ffaa00" if pct >= 50 else "#ff4444"

            ctk.CTkLabel(res_win, text=f"{acertos}/{len(questoes)} corretas — {pct}%",
                         font=ctk.CTkFont(family="Courier New", size=22, weight="bold"),
                         text_color=cor_nota).pack(pady=(20, 4))

            msg = "Excelente!" if pct >= 80 else "Bom trabalho!" if pct >= 60 else "Continue estudando!"
            ctk.CTkLabel(res_win, text=msg,
                         font=ctk.CTkFont(family="Courier New", size=13),
                         text_color="#a0d4f5").pack(pady=(0, 12))

            caixa = ctk.CTkScrollableFrame(res_win, fg_color="#060f20",
                                           corner_radius=8, border_width=1,
                                           border_color="#0a2a4a")
            caixa.pack(fill="both", expand=True, padx=16, pady=(0, 16))

            for linha in detalhes:
                cor = "#00ff88" if "✓" in linha else "#ff4444"
                ctk.CTkLabel(caixa, text=linha,
                             font=ctk.CTkFont(family="Courier New", size=12),
                             text_color=cor, anchor="w").pack(fill="x", padx=8, pady=2)

        # Guarda path para uso no resultado
        self._ultimo_path = path

        anterior_btn.configure(command=anterior)
        proximo_btn.configure(command=proximo)
        finalizar_btn.configure(command=ver_resultado)

        carregar_questao(0)
