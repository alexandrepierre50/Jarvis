// ============================================================
// CONFIGURACAO
// ============================================================
const SERVER_URL = "https://web-production-b9c17.up.railway.app";

// ============================================================
// ELEMENTOS
// ============================================================
const chat        = document.getElementById("chat");
const statusEl    = document.getElementById("status");
const textInput   = document.getElementById("text-input");
const sendBtn     = document.getElementById("send-btn");
const micBtn      = document.getElementById("mic-btn");
const audioToggle  = document.getElementById("audio-toggle");
const voiceSelect  = document.getElementById("voice-select");
const orbCanvas    = document.getElementById("orb");
const ctx          = orbCanvas.getContext("2d");

// Carrega preferencia de audio salva
let audioEnabled = localStorage.getItem("audioEnabled") !== "false";
audioToggle.checked = audioEnabled;
audioToggle.addEventListener("change", () => {
  audioEnabled = audioToggle.checked;
  localStorage.setItem("audioEnabled", audioEnabled);
  if (!audioEnabled && synth) synth.cancel();
});

// Popula lista de vozes
function loadVoices() {
  const voices = synth.getVoices();
  if (!voices.length) return;
  voiceSelect.innerHTML = "";
  const savedVoice = localStorage.getItem("selectedVoice");
  voices.forEach((v, i) => {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `${v.name} (${v.lang})`;
    if (savedVoice === v.name) opt.selected = true;
    voiceSelect.appendChild(opt);
  });
}

voiceSelect.addEventListener("change", () => {
  const voices = synth.getVoices();
  const selected = voices[voiceSelect.value];
  if (selected) localStorage.setItem("selectedVoice", selected.name);
});

if (synth) {
  synth.onvoiceschanged = loadVoices;
  loadVoices();
}

// ============================================================
// ESTADO
// ============================================================
let isListening  = false;
let isSpeaking   = false;
let animAngle    = 0;
let pulseSize    = 0;
let pulseGrowing = true;
let recognition  = null;
let synth        = window.speechSynthesis;

// ============================================================
// ANIMACAO ORB
// ============================================================
function drawOrb() {
  ctx.clearRect(0, 0, 180, 180);
  const cx = 90, cy = 90;

  // Circulos de fundo
  const bgColors = ["#051020", "#061528", "#071830", "#081b38"];
  for (let i = 4; i >= 1; i--) {
    const r = 22 + i * 14;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = "#0a3a6a";
    ctx.lineWidth = 1;
    ctx.fillStyle = bgColors[i - 1];
    ctx.fill();
    ctx.stroke();
  }

  // Arcos girando
  const arcColors = ["#00bfff", "#0080ff", "#004080"];
  for (let i = 0; i < 3; i++) {
    const start = ((animAngle + i * 120) % 360) * Math.PI / 180;
    ctx.beginPath();
    ctx.arc(cx, cy, 48, start, start + Math.PI / 2);
    ctx.strokeStyle = arcColors[i];
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Circulo central pulsante
  if (pulseGrowing) {
    pulseSize += 0.4;
    if (pulseSize >= 8) pulseGrowing = false;
  } else {
    pulseSize -= 0.4;
    if (pulseSize <= 0) pulseGrowing = true;
  }
  const pr = 16 + pulseSize;
  ctx.beginPath();
  ctx.arc(cx, cy, pr, 0, Math.PI * 2);
  ctx.fillStyle = isListening ? "#004a8a" : "#003a6a";
  ctx.fill();
  ctx.strokeStyle = isListening ? "#00ffff" : "#00bfff";
  ctx.lineWidth = 2;
  ctx.stroke();

  // Texto central
  ctx.fillStyle = "#00bfff";
  ctx.font = "bold 14px 'Courier New'";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(isListening ? "..." : "J", cx, cy);

  // Pontos orbitando
  for (let i = 0; i < 6; i++) {
    const angle = (animAngle * 2 + i * 60) * Math.PI / 180;
    const ox = cx + 62 * Math.cos(angle);
    const oy = cy + 62 * Math.sin(angle);
    ctx.beginPath();
    ctx.arc(ox, oy, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = "#00bfff";
    ctx.fill();
  }

  animAngle = (animAngle + 2) % 360;
  requestAnimationFrame(drawOrb);
}

drawOrb();

// ============================================================
// CHAT
// ============================================================
function addMessage(sender, text, senderClass) {
  const div = document.createElement("div");
  div.className = "message";

  const s = document.createElement("span");
  s.className = `message-sender ${senderClass}`;
  s.textContent = `[${sender}]`;

  const t = document.createElement("span");
  t.className = "message-text";
  t.textContent = text;

  div.appendChild(s);
  div.appendChild(t);

  // Botao de play para mensagens do Jarvis
  if (senderClass === "sender-jarvis") {
    const playBtn = document.createElement("button");
    playBtn.className = "play-btn";
    playBtn.textContent = "ouvir";
    playBtn.setAttribute("aria-label", "ouvir");
    playBtn.addEventListener("click", () => speak(text));
    div.appendChild(playBtn);
  }

  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function setStatus(text, color = "#1a6b8a") {
  statusEl.textContent = text;
  statusEl.style.color = color;
}

// ============================================================
// VOZ - FALAR
// ============================================================
function speak(text) {
  if (!synth) return;
  synth.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "pt-BR";
  utter.rate = 1.0;
  utter.pitch = 0.9;

  // Usa a voz selecionada pelo usuario
  const voices = synth.getVoices();
  const savedVoice = localStorage.getItem("selectedVoice");
  if (savedVoice) {
    const found = voices.find(v => v.name === savedVoice);
    if (found) utter.voice = found;
  } else {
    const ptVoice = voices.find(v => v.lang.startsWith("pt"));
    if (ptVoice) utter.voice = ptVoice;
  }

  if (!audioEnabled) return;

  utter.onstart = () => {
    isSpeaking = true;
    setStatus("Falando...", "#00bfff");
  };
  utter.onend = () => {
    isSpeaking = false;
    setStatus("Aguardando...", "#1a6b8a");
  };
  synth.speak(utter);
}

// ============================================================
// VOZ - OUVIR
// ============================================================
function startListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Seu navegador nao suporta reconhecimento de voz. Use o Chrome.");
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = "pt-BR";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isListening = true;
    micBtn.classList.add("listening");
    setStatus("Ouvindo...", "#00ffff");
  };

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    textInput.value = text;
    sendMessage(text);
  };

  recognition.onerror = (e) => {
    setStatus("Nao entendi. Tente novamente.", "#ff6b35");
  };

  recognition.onend = () => {
    isListening = false;
    micBtn.classList.remove("listening");
    setStatus("Aguardando...", "#1a6b8a");
  };

  recognition.start();
}

// ============================================================
// ENVIAR MENSAGEM
// ============================================================
async function sendMessage(text) {
  if (!text || !text.trim()) return;
  textInput.value = "";

  addMessage("Voce", text, "sender-user");
  setStatus("Pensando...", "#00bfff");

  try {
    const res = await fetch(`${SERVER_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    if (!res.ok) throw new Error(`Erro ${res.status}`);

    const data = await res.json();
    addMessage("Jarvis", data.reply, "sender-jarvis");
    speak(data.reply);

  } catch (err) {
    addMessage("Erro", "Nao foi possivel conectar ao servidor.", "sender-erro");
    setStatus("Erro de conexao.", "#ff4444");
  }
}

// ============================================================
// EVENTOS
// ============================================================
sendBtn.addEventListener("click", () => sendMessage(textInput.value));

textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage(textInput.value);
});

micBtn.addEventListener("click", () => {
  if (!isListening) startListening();
});

// Carrega vozes
if (synth) {
  synth.onvoiceschanged = () => synth.getVoices();
}

// ============================================================
// BOAS VINDAS
// ============================================================
window.addEventListener("load", () => {
  setTimeout(() => {
    const msg = "Sistemas online. Bom dia, Senhor. Como posso ajudar?";
    addMessage("Jarvis", msg, "sender-jarvis");
    speak(msg);
    setStatus("Aguardando...", "#1a6b8a");
  }, 800);
});

// ============================================================
// SERVICE WORKER (PWA offline)
// ============================================================
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
