@echo off
echo ===============================================
echo    Instalando dependencias do JARVIS...
echo ===============================================
echo.
pip install -r requirements-desktop.txt
echo.
echo Instalando PyAudio...
pip install pyaudio
echo.
echo ===============================================
echo    Instalacao concluida!
echo    Agora abra o arquivo config.py e cole
echo    sua chave de API antes de iniciar.
echo ===============================================
pause
