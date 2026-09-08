#!/bin/zsh
cd "/Users/qianyichen/Documents/自动化prompt生成/prompt-factory" || exit 1
/Users/qianyichen/.venvs/prompt-factory-fresh/bin/python -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
