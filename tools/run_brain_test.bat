@echo off
title Brain & Director Model Pre-Test Suite
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python brain_model_test_suite.py --endpoint "http://localhost:11434" --model "gemma4:latest"
pause
