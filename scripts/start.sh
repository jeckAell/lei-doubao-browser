#!/bin/bash
# Chrome Debug 启动脚本
# 功能：启动带调试端口的 Chrome，继承已有登录状态

CHROME="$HOME/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
USER_DATA="$HOME/.config/chromium-debug"
PORT=9222

# 杀掉已有实例
pkill -f "chrome-linux64/chrome" 2>/dev/null
sleep 1

# 清理锁文件
rm -rf "$USER_DATA/SingletonLock" "$USER_DATA/.lock" 2>/dev/null

# 启动调试浏览器
$CHROME \
  --remote-debugging-port=$PORT \
  --user-data-dir=$USER_DATA \
  --no-sandbox \
  2>&1 &

sleep 2

# 验证是否启动成功
if curl -s http://127.0.0.1:$PORT/json/version > /dev/null 2>&1; then
    echo "✅ Chrome Debug 启动成功"
    echo "   CDP: http://127.0.0.1:$PORT"
    echo "   连接: agent-browser connect http://127.0.0.1:$PORT"

    # 打开豆包
    agent-browser open https://www.doubao.com/
else
    echo "❌ 启动失败，请检查日志"
fi
