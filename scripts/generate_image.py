#!/usr/bin/env python3
"""
豆包 AI 图片生成脚本
用法: python3 generate_image.py "图片描述" [输出目录]
"""

import subprocess, json, sys, time, os, re, http.client, urllib.request

def find_chrome_port():
    """自动发现 Chrome 调试端口"""
    for env_var in ['AGENT_BROWSER_CDP_PORT', 'AGENT_BROWSER_STREAM_PORT']:
        port = os.environ.get(env_var)
        if port:
            try:
                int(port)
                return int(port)
            except ValueError:
                pass
    for port in list(range(9222, 9300)) + list(range(46000, 47000)):
        try:
            c = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
            c.request('GET', '/json/version')
            r = c.getresponse()
            if r.status == 200:
                c.close()
                return port
            c.close()
        except:
            pass
    return None

CDP_HOST = '127.0.0.1'
PROMPT = sys.argv[1] if len(sys.argv) > 1 else None
OUTPUT_DIR = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/doubao/imgs')

if not PROMPT:
    print('用法: python3 generate_image.py "图片描述" [输出目录]')
    sys.exit(1)

CDP_PORT = find_chrome_port()
if CDP_PORT is None:
    print('❌ 未发现 Chrome 调试端口，请先启动 Chrome (--remote-debugging-port=XXXX)')
    sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f'📁 输出目录: {OUTPUT_DIR}')
print(f'🔌 Chrome CDP 端口: {CDP_PORT}')

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
        r = subprocess.run(f'agent-browser --cdp {CDP_PORT} {cmd}', shell=True,
                         capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return ''

def find_ref(text, kw):
    """通过文本找 ref，优先找 link 类型"""
    best = None
    for line in text.split('\n'):
        if f'"{kw}"' not in line and kw not in line:
            continue
        m = re.search(r'ref=(e\d+)', line)
        if not m:
            continue
        ref = m.group(1)
        if 'link "' in line:
            return ref  # link 类型优先返回
        if not best:
            best = ref
    return best

def is_logged_in():
    """检测是否已登录（无登录按钮即为已登录）"""
    snap = run('snapshot -i', timeout=8)
    return 'button "登录"' not in snap and 'StaticText "登录"' not in snap

def cdp_js(js):
    """执行 JS 并返回结果字符串"""
    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
        c.request('GET', '/json/list')
        pages = json.loads(c.getresponse().read()); c.close()
        # 优先使用 create-image 页面
        ws_url = next((p['webSocketDebuggerUrl'] for p in pages if 'create-image' in p.get('url', '')), pages[0]['webSocketDebuggerUrl'])
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

def get_image_urls():
    raw = cdp_js('''
        (function() {
            var s=new Set(),u=[];
            document.querySelectorAll("img").forEach(function(i){
                var src=i.src||i.currentSrc||'';
                if(src.indexOf("rc_gen_image")>-1&&!s.has(src)){s.add(src);u.push(src);}
            });
            return JSON.stringify(u);
        })()
    ''')
    try:
        if raw.startswith('"'):
            return json.loads(json.loads(raw))
        return json.loads(raw)
    except:
        return []

def download(url, path):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.doubao.com/'})
        with urllib.request.urlopen(req, timeout=15) as r:
            with open(path, 'wb') as f: f.write(r.read())
        return os.path.getsize(path)
    except:
        return None

def main():
    print('🔧 检查 Chrome...')
    if not check_chrome():
        print('❌ Chrome Debug 未启动，请先运行 start.sh'); sys.exit(1)
    print('✅ Chrome 运行中')

    print('🌐 打开豆包...')
    run('open "https://www.doubao.com/"', timeout=10)
    time.sleep(3)

    # 检查登录状态
    if not is_logged_in():
        print()
        print('🔐 检测到未登录，请手动登录后按回车继续...')
        print('   提示：在浏览器中点击"登录"按钮，用抖音 App 扫码登录')
        input()

    print('🎨 进入 AI 创作页面...')
    # 点击 AI 创作链接
    snap = run('snapshot -i', timeout=8)
    ai_ref = find_ref(snap, 'AI 创作')
    if ai_ref:
        run(f'click @{ai_ref}', timeout=8)
    time.sleep(4)

    print('🔍 找图片描述输入框...')
    ta_ref = None
    for attempt in range(5):
        snap = run('snapshot -i', timeout=8)
        ta_ref = find_ref(snap, '描述你想要的图片')
        if ta_ref: print(f'   ✅ 找到 @{ta_ref}'); break
        print(f'   第 {attempt+1} 次: 未找到，重试...')
        time.sleep(2)

    if not ta_ref:
        # 尝试 JS 方式
        print('   尝试 JS 方式...')
        js_result = cdp_js('''
            (function() {
                var els = document.querySelectorAll("textarea, [contenteditable], input[type='text']");
                for (var i=0; i<els.length; i++) {
                    var el = els[i];
                    if (el.offsetHeight > 0 && el.offsetWidth > 0) {
                        el.scrollIntoView({block:"center"});
                        el.focus();
                        var ns = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set;
                        ns.call(el, "test");
                        el.dispatchEvent(new Event("input",{bubbles:true}));
                        return "found:" + el.tagName;
                    }
                }
                return "not found visible input";
            })()
        ''')
        print(f'   {js_result}')
        if 'not found' in js_result:
            print('❌ 未找到输入框'); sys.exit(1)
        time.sleep(1)
        # 重新获取 snapshot 找 ref
        snap = run('snapshot -i', timeout=8)
        ta_ref = find_ref(snap, '描述你想要的图片')
        if not ta_ref:
            snap = run('snapshot -i', timeout=8)
            for line in snap.split('\n'):
                if 'ref=' in line and '描述你想要的图片' in line:
                    m = re.search(r'ref=(e\d+)', line)
                    if m: ta_ref = m.group(1); break

    if not ta_ref:
        print('❌ 未找到输入框'); sys.exit(1)

    print(f'✍️ 填写: {PROMPT}')
    run(f'fill @{ta_ref} "{PROMPT}"', timeout=5)
    time.sleep(1)

    print('🚀 点击生成按钮...')
    # 使用 CDP 鼠标点击坐标 (按钮中心约 x:1140, y:293)
    cdp_js('''
        (function() {
            var btn = document.querySelector('[class*="send-btn-wrapper"]');
            if (!btn) return 'btn not found';
            var rect = btn.getBoundingClientRect();
            var x = rect.left + rect.width / 2;
            var y = rect.top + rect.height / 2;
            var dispatch = function(x, y, type) {
                var evt = new MouseEvent(type, {bubbles: true, cancelable: true, clientX: x, clientY: y, view: window});
                document.elementFromPoint(x, y).dispatchEvent(evt);
            };
            dispatch(x, y, 'mousedown');
            dispatch(x, y, 'mouseup');
            dispatch(x, y, 'click');
            return 'clicked at ' + Math.round(x) + ',' + Math.round(y);
        })()
    ''')

    print('⏳ 等待生成（30秒）...')
    time.sleep(30)

    print('📥 获取图片...')
    urls = []
    for attempt in range(5):
        urls = get_image_urls()
        if len(urls) >= 4:
            print(f'   第 {attempt+1} 次: 找到 {len(urls)} 张 ✅')
            break
        print(f'   第 {attempt+1} 次: {len(urls)} 张，重试...')
        time.sleep(3)

    if not urls:
        print('❌ 未找到图片，保存截图...')
        run(f'screenshot {OUTPUT_DIR}/fail_{int(time.time())}.png', timeout=10)
        sys.exit(1)

    safe = re.sub(r'[^\w\u4e00-\u9fff\s]', '', PROMPT).strip()[:25] or 'img'
    ts = int(time.time())
    saved = 0
    for i, url in enumerate(urls[:4]):
        ext = 'png' if '.png' in url else 'jpg'
        path = f'{OUTPUT_DIR}/{safe}_{i+1}_{ts}.{ext}'
        print(f'   第 {i+1} 张... ', end='', flush=True)
        sz = download(url, path)
        if sz:
            print(f'✅ {sz//1024}KB')
            saved += 1
        else:
            print('❌')

    print()
    print('=' * 40)
    print(f'✅ 完成！保存 {saved} 张 → {OUTPUT_DIR}')
    print(f'📝 {PROMPT}')
    print('=' * 40)

if __name__ == '__main__':
    main()
