@echo off
rem Instalador único do horys-pixel (perfeicao.md C12): dependências, extensão do Aseprite (reempacotada),
rem plugin do Claude Code, horysd reiniciado e atalho do Horys Estúdio na área de trabalho.
rem Feche o Aseprite antes (a extensão é substituída).
setlocal
cd /d "%~dp0"
where uv >nul 2>nul || (echo [horys] instale o uv: https://docs.astral.sh/uv/ & exit /b 1)
echo [horys] dependencias...
uv sync || exit /b 1
echo [horys] extensao, plugin do Claude Code e skills...
uv run horys instalar --tudo || exit /b 1
echo [horys] reiniciando o horysd...
uv run horys reiniciar
echo [horys] atalho do Horys Estudio na area de trabalho...
> "%USERPROFILE%\Desktop\Horys Estudio.cmd" (
  echo @echo off
  echo cd /d "%~dp0"
  echo start "" /min uv run horys estudio --app
)
echo [horys] pronto. Abra o Aseprite e rode: uv run horys teste-vivo
endlocal
