#!/bin/bash
# Chrome Debug 启动脚本
# 功能：启动带调试端口的 Chrome，不依赖图形界面
# 用法：./start.sh [test]
#   不带参数 - headless 无头模式（默认）
#   test 参数 - 测试模式，显示浏览器窗口

CHROME="$HOME/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
USER_DATA="$HOME/.config/chromium-debug"
PORT=9222
MODE="${1:-headless}"

# 杀掉已有实例
pkill -f "chrome.*${PORT}" 2>/dev/null
sleep 1

# 清理锁文件
rm -rf "$USER_DATA/SingletonLock" "$USER_DATA/.lock" 2>/dev/null

if [ "$MODE" = "test" ]; then
    echo "启动测试模式（可见浏览器窗口）..."
    $CHROME \
      --remote-debugging-port=$PORT \
      --user-data-dir=$USER_DATA \
      --no-sandbox \
      --disable-dev-shm-usage \
      > /tmp/chrome-debug.log 2>&1 &
else
    echo "启动 headless 模式..."
    $CHROME \
      --remote-debugging-port=$PORT \
      --user-data-dir=$USER_DATA \
      --no-sandbox \
      --disable-dev-shm-usage \
      --disable-gpu \
      --disable-software-rasterizer \
      --disable-extensions \
      --disable-background-networking \
      --disable-sync \
      --disable-translate \
      --no-first-run \
      --metrics-recording-only \
      --mute-audio \
      --no-default-browser-check \
      --headless=new \
      --ozone-platform=headless \
      --ozone-override-screen-size=800,600 \
      > /tmp/chrome-debug.log 2>&1 &
fi

# 等待 Chrome 启动（最多15秒）
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:$PORT/json/version > /dev/null 2>&1; then
        if [ "$MODE" = "test" ]; then
            echo "Chrome Debug 启动成功 (CDP $PORT, test mode)"
        else
            echo "Chrome Debug 启动成功 (CDP $PORT, headless)"
        fi
        exit 0
    fi
    sleep 1
done

echo "Chrome Debug 启动超时"
exit 1
