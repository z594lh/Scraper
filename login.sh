#!/bin/bash
# 无显示器环境（如虚拟机）下的登录入口：终端输入手机号 + 短信验证码
set -e
cd "$(dirname "$0")"
exec xvfb-run -a -s "-screen 0 1440x960x24" .venv/bin/python pzds.py login
