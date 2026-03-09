@echo off
chcp 65001 >nul
echo ====================================
echo  Sistema Unificado Carvajal
echo ====================================
cd /d "%~dp0"
streamlit run app.py --server.port=8501
pause
