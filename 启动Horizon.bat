@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "OBSIDIAN_NEWS_DIR=D:\kimyon\我的知识库\AI新闻日报"
cd /d "%~dp0"

if not exist ".venv\Scripts\horizon.exe" (
  echo Horizon 的运行环境还没有安装完成。
  echo 请不要继续操作，并让 Codex 检查安装状态。
  pause
  exit /b 1
)

echo 正在生成过去 24 小时的经营新闻日报，请稍候……
echo.
call ".venv\Scripts\horizon.exe" --hours 24

echo.
if errorlevel 1 (
  echo 运行没有成功。最常见的原因是 AI 密钥还没有填写或网络无法连接。
  echo 请把上面的错误截图发给 Codex，但不要把完整密钥发出来。
) else (
  echo 运行完成。日报保存在 data\summaries 文件夹中。
  if not exist "%OBSIDIAN_NEWS_DIR%" mkdir "%OBSIDIAN_NEWS_DIR%"
  copy /y "data\summaries\horizon-*-zh.md" "%OBSIDIAN_NEWS_DIR%\" >nul
  echo 日报也已经复制到 Obsidian 的 AI新闻日报 文件夹。
)
echo.
pause
