#!/usr/bin/env python3
"""
豆包登陆验证脚本
功能：检测登录状态，未登录时弹出二维码登陆框并截图保存
用法: python3 check_login.py
"""

import subprocess, json, sys, time, os, re, http.client

CDP_HOST, CDP_PORT = '127.0.0.1', 9222
SCREENSHOT_DIR = os.path.expanduser('~/.openclaw/workspace/doubao/loginImgs')

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def check_chrome():
    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=3)
        c.request('GET', '/json/version')
        c.getresponse().read(); c.close()
        return True
    except:
        return False

def run(cmd, timeout=12):
    try:
        r = subprocess.run(f'agent-browser {cmd}', shell=True,
                         capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return ''

def cdp_js(js):
    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
        c.request('GET', '/json/list')
        pages = json.loads(c.getresponse().read()); c.close()
        ws_url = next((p['webSocketDebuggerUrl'] for p in pages if p.get('type') == 'page'), pages[0]['webSocketDebuggerUrl'])
        import asyncio, websockets
        async def do():
            ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=10)
            mid = 1
            async def send(m, p=None):
                nonlocal mid
                await ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); mid += 1
                while True:
                    r = await asyncio.wait_for(ws.recv(), timeout=5)
                    d = json.loads(r)
                    if d.get('id') == mid - 1: return d
            rv = await send('Runtime.evaluate', {'expression': js, 'returnByValue': True})
            await ws.close()
            return rv.get('result',{}).get('result',{}).get('value','') or ''
        return asyncio.run(do())
    except Exception as e:
        return f'error:{e}'

def find_ref(text, kw):
    """通过文本找 ref，优先匹配 button/link 元素"""
    for line in text.split('\n'):
        if f'"{kw}"' not in line and kw not in line:
            continue
        # 优先匹配 button 或 link 类型的元素（去掉行首的 "- " 或 "  - "）
        stripped = line.lstrip().lstrip('-').lstrip()
        if not (stripped.startswith('button') or stripped.startswith('link')):
            continue
        m = re.search(r'ref=(e\d+)', line)
        if m:
            return m.group(1)
    # 如果没找到 button/link，扩大范围找任意元素
    for line in text.split('\n'):
        if f'"{kw}"' not in line and kw not in line:
            continue
        m = re.search(r'ref=(e\d+)', line)
        if m:
            return m.group(1)
    return None

def check_login_button():
    """检测右上角是否有登录按钮"""
    snap = run('snapshot -i', timeout=8)

    # 检查 snapshot 中是否包含登录按钮
    # 登录按钮可能是: button "登录" 或 StaticText "登录"
    has_login_btn = (
        'button "登录"' in snap or
        'StaticText "登录"' in snap or
        '登录' in snap.split('button')[-1][:200] if 'button' in snap else False
    )

    # 尝试通过 JS 更精确地检测右上角登录按钮
    js_result = cdp_js('''
        (function() {
            // 查找可能包含"登录"文字的按钮或链接
            var els = document.querySelectorAll('button, a, [role="button"]');
            for (var el of els) {
                var txt = el.textContent.trim();
                if (txt === '登录' || txt === '登录/注册') {
                    var rect = el.getBoundingClientRect();
                    // 检查是否在页面右上角区域
                    if (rect.top < 100 && rect.right > window.innerWidth - 200) {
                        return 'found: 右上角登录按钮, 位置:' + Math.round(rect.left) + ',' + Math.round(rect.top);
                    }
                    return 'found: 登录按钮(位置:' + Math.round(rect.left) + ',' + Math.round(rect.top) + ')';
                }
            }
            return 'not found';
        })()
    ''')

    print(f'   检测结果: {js_result}')

    if 'not found' in js_result:
        return False
    return True

def click_login_button():
    """点击登录按钮弹出登录框"""
    # 先用 agent-browser 快照找到登录按钮
    snap = run('snapshot -i', timeout=8)
    ref = find_ref(snap, '登录')

    if ref:
        print(f'   找到登录按钮 @{ref}，点击...')
        run(f'click @{ref}', timeout=8)
        time.sleep(2)
        return True

    # 如果快照找不到，用 JS 点击
    js_result = cdp_js('''
        (function() {
            var els = document.querySelectorAll('button, a, [role="button"]');
            for (var el of els) {
                var txt = el.textContent.trim();
                if (txt === '登录' || txt === '登录/注册') {
                    el.scrollIntoView({block: "center"});
                    el.click();
                    return 'clicked';
                }
            }
            return 'not found';
        })()
    ''')
    print(f'   JS点击结果: {js_result}')
    time.sleep(2)
    return 'not found' not in js_result

def check_qrcode_dialog():
    """检查是否弹出包含二维码的登录框"""
    time.sleep(1)
    result = cdp_js('''
        (function() {
            // 查找登录弹窗
            var dialog = document.querySelector('[class*="login"], [class*="modal"], [class*="dialog"]');
            if (!dialog) {
                // 尝试查找包含"二维码"文字的元素
                var els = document.querySelectorAll('*');
                for (var el of els) {
                    if (el.textContent.includes('二维码') && el.offsetHeight > 0) {
                        return 'found: 包含二维码的对话框';
                    }
                }
                return 'no dialog found';
            }
            // 检查弹窗内是否包含二维码文字
            if (dialog.textContent.includes('二维码')) {
                return 'found: 登录弹窗包含二维码';
            }
            return 'dialog found but no 二维码';
        })()
    ''')
    return '二维码' in result

def take_screenshot():
    """截取整个页面并保存"""
    ts = int(time.time())
    filename = f'login_qr_{ts}.png'
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    result = run(f'screenshot "{filepath}"', timeout=10)
    if os.path.exists(filepath):
        return filepath
    return None

def main():
    print('🔧 检查 Chrome...')
    if not check_chrome():
        print('❌ Chrome Debug 未启动，请先运行 start.sh')
        sys.exit(1)
    print('✅ Chrome 运行中')

    print('🌐 检查豆包登录状态...')
    run('open "https://www.doubao.com/"', timeout=10)
    time.sleep(3)

    print('🔍 检测右上角登录按钮...')
    is_not_logged_in = check_login_button()

    if not is_not_logged_in:
        print()
        print('=' * 50)
        print('✅ 已登录')
        print('=' * 50)
        return

    # 未登录，开始登录流程
    print()
    print('🔐 检测到未登录，开始登录流程...')

    print('🖱️ 点击登录按钮...')
    click_login_button()
    time.sleep(2)

    print('🔍 检查登录弹窗...')
    has_qr = check_qrcode_dialog()
    if not has_qr:
        print('   等待弹窗出现...')
        time.sleep(2)
        has_qr = check_qrcode_dialog()

    if has_qr:
        print('   ✅ 检测到二维码登录框')
    else:
        print('   ⚠️ 未检测到二维码，但继续截图')

    print('📸 截图保存...')
    screenshot_path = take_screenshot()

    print()
    print('=' * 50)
    print('⚠️ 未登录，请扫描二维码登陆')
    if screenshot_path:
        print(f'📁 截图: {screenshot_path}')
    print('=' * 50)

if __name__ == '__main__':
    main()
