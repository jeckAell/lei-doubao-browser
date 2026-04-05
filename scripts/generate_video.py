#!/usr/bin/env python3
"""
豆包 AI 视频生成脚本
用法: python3 generate_video.py "视频描述" [输出目录] [参考图目录]
"""

import subprocess, json, sys, time, os, re, http.client, urllib.request

CDP_HOST = '127.0.0.1'
CDP_PORT = 9222
PROMPT = sys.argv[1] if len(sys.argv) > 1 else None
OUTPUT_DIR = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/.openclaw/workspace/doubao/videos')
REF_IMAGES_DIR = os.path.expanduser(sys.argv[3] if len(sys.argv) > 3 else '') if len(sys.argv) > 3 else ''

if not PROMPT:
    print('用法: python3 generate_video.py "视频描述" [输出目录]')
    sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f'📁 输出目录: {OUTPUT_DIR}')

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
            return ref
        if not best:
            best = ref
    return best

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

def download_video(url, path):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Referer': 'https://www.doubao.com/',
            'Accept': '*/*'
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 65536
            with open(path, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk: break
                    f.write(chunk)
                    downloaded += len(chunk)
            return downloaded
    except Exception as e:
        return f'error: {e}'

def click_element_by_text(kw):
    """通过 JS 点击包含指定文本的元素"""
    js = f'''
        (function() {{
            var els = document.querySelectorAll("button, a, [role=\\'button\\']");
            for (var el of els) {{
                if (el.textContent.trim() === "{kw}") {{
                    el.scrollIntoView({{block: "center"}});
                    el.click();
                    return "clicked";
                }}
            }}
            return "not found";
        }})()
    '''
    return cdp_js(js)

def wait_for_video():
    """等待视频生成完成，返回视频URL"""
    print('⏳ 等待视频生成（最多 180 秒）...')
    start = time.time()
    
    while time.time() - start < 180:
        elapsed = int(time.time() - start)
        
        status = cdp_js('''
            (function() {
                var txt = document.body.innerText || "";
                if (txt.includes("视频生成好啦") || txt.includes("你的视频生成好啦")) return "ready";
                return "waiting";
            })()
        ''')
        
        if 'ready' in status:
            print(f'   ✅ 视频生成完成，耗时 {elapsed} 秒')
            time.sleep(1)
            
            # 点击播放按钮
            cdp_js('''
                (function() {
                    var playBtn = document.querySelector("[class*=\'play-icon\']");
                    if (playBtn) playBtn.click();
                })()
            ''')
            time.sleep(2)
            
            # 提取视频 URL
            for _ in range(5):
                url = cdp_js('''
                    (function() {
                        var video = document.querySelector("video");
                        if (video && video.src && video.src.includes("douyinvod")) return video.src;
                        return "no video yet";
                    })()
                ''')
                if url and 'douyinvod' in url:
                    return url
                time.sleep(1)
            return url
        
        print(f'   {elapsed}s: 等待中...')
        time.sleep(10)
    
    return None

def click_video_tab_button():
    """点击视频 tab 按钮（与图片按钮同组的那一个）"""
    js = '''
        (function() {
            // 方案1：找包含"图像"和"视频"两个子元素的父容器按钮
            var buttons = document.querySelectorAll("button");
            for (var btn of buttons) {
                var txt = btn.textContent.trim();
                if (txt === "图像 视频" || txt === "图像视频" || txt === "图片/视频") {
                    // 在这个按钮组内找视频子元素
                    var children = btn.querySelectorAll("*, [class]");
                    for (var child of children) {
                        var ct = child.textContent.trim();
                        if (ct === "视频") {
                            child.scrollIntoView({block: "center"});
                            child.click();
                            return "clicked 视频 child in 图像 视频 button";
                        }
                    }
                    // 如果没有子元素直接包含"视频"，尝试直接点击按钮本身（内部可能有tab切换）
                    btn.scrollIntoView({block: "center"});
                    btn.click();
                    return "clicked 图像 视频 button (parent)";
                }
            }

            // 方案2：找直接文本为"视频"的元素
            for (var btn of buttons) {
                if (btn.textContent.trim() === "视频") {
                    btn.scrollIntoView({block: "center"});
                    btn.click();
                    return "clicked 视频";
                }
            }

            // 方案3：查找 role=tab 且 text 包含视频
            var tabs = document.querySelectorAll("[role='tab'], [class*='tab']");
            for (var tab of tabs) {
                var txt = tab.textContent.trim();
                if (txt.includes("视频")) {
                    tab.scrollIntoView({block: "center"});
                    tab.click();
                    return "clicked tab with 视频";
                }
            }

            return "not found";
        })()
    '''
    result = cdp_js(js)
    print(f'   视频tab按钮点击: {result}')
    return result

def click_ref_images_button():
    """点击参考图按钮"""
    js = '''
        (function() {
            // 尝试多种方式找参考图按钮
            var selectors = [
                'button:has-text("参考图")',
                '[class*="ref-image"]',
                '[class*="reference-image"]',
                '[class*="upload"]'
            ];

            var btns = document.querySelectorAll("button, div[role='button']");
            for (var btn of btns) {
                var txt = btn.textContent.trim();
                if (txt === "参考图" || txt.includes("参考图")) {
                    btn.scrollIntoView({block: "center"});
                    btn.click();
                    return "clicked: " + txt;
                }
            }

            // 尝试找图片上传相关的按钮
            var uploadArea = document.querySelector('[class*="upload"], [class*="image-upload"], [class*="ref"]');
            if (uploadArea) {
                uploadArea.click();
                return "clicked upload area";
            }

            return "not found";
        })()
    '''
    result = cdp_js(js)
    print(f'   参考图按钮点击: {result}')
    return result

def upload_ref_image(image_path):
    """上传单张参考图 - 使用 CDP DOM.setFileInputFiles"""
    import asyncio, websockets

    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
        c.request('GET', '/json/list')
        pages = json.loads(c.getresponse().read()); c.close()
        ws_url = next((p['webSocketDebuggerUrl'] for p in pages if p.get('type') == 'page'), pages[0]['webSocketDebuggerUrl'])

        async def do():
            nonlocal ws_url
            ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=10)
            mid = 1
            async def send(m, p=None):
                nonlocal mid
                await ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); mid += 1
                while True:
                    r = await asyncio.wait_for(ws.recv(), timeout=5)
                    d = json.loads(r)
                    if d.get('id') == mid - 1: return d

            # 获取 DOM 文档
            doc = await send('DOM.getDocument', {'depth': 0})
            root_id = doc.get('result', {}).get('root', {}).get('nodeId', 0)
            if not root_id:
                await ws.close()
                return {'error': 'no root nodeId'}

            # 查找 file input 的 backend node ID
            result = await send('DOM.querySelectorAll', {
                'nodeId': root_id,
                'selector': 'input[type="file"]'
            })
            node_ids = result.get('result', {}).get('nodeIds', [])
            if not node_ids:
                await ws.close()
                return {'error': 'no file input found'}

            file_input_node_id = node_ids[0]

            # 使用绝对路径
            abs_path = os.path.abspath(image_path)

            # 设置文件
            set_result = await send('DOM.setFileInputFiles', {
                'files': [abs_path],
                'nodeId': file_input_node_id
            })
            await ws.close()
            return set_result

        result = asyncio.run(do())
        if result and 'error' not in str(result):
            return True
        print(f'   上传结果: {result}')
        return False
    except Exception as e:
        print(f'   上传出错: {e}')
        return False

def get_image_files(directory):
    """获取目录中的所有图片文件"""
    if not directory or not os.path.isdir(directory):
        return []

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    image_files = []

    for filename in os.listdir(directory):
        ext = os.path.splitext(filename.lower())[1]
        if ext in image_extensions:
            full_path = os.path.join(directory, filename)
            if os.path.isfile(full_path):
                image_files.append(full_path)

    return sorted(image_files)

def upload_ref_images():
    """上传所有参考图"""
    if not REF_IMAGES_DIR:
        return

    image_files = get_image_files(REF_IMAGES_DIR)
    if not image_files:
        print(f'⚠️ 参考图目录为空或不存在: {REF_IMAGES_DIR}')
        return

    print(f'📷 开始上传 {len(image_files)} 张参考图...')

    for i, image_path in enumerate(image_files, 1):
        print(f'   [{i}/{len(image_files)}] 上传: {os.path.basename(image_path)}')

        # 点击参考图按钮
        result = click_ref_images_button()
        if 'not found' in result:
            # 尝试截图看看页面状态
            print(f'   ⚠️ 未找到参考图按钮，尝试截图诊断...')
            run(f'screenshot /tmp/ref_btn_debug_{int(time.time())}.png', timeout=5)
            continue

        # 等待文件输入框出现
        print(f'   等待文件选择框...')
        time.sleep(2)

        # 检查 file input 是否存在
        check = cdp_js('''
            (function() {
                var inputs = document.querySelectorAll('input[type="file"]');
                return "found " + inputs.length + " file inputs";
            })()
        ''')
        print(f'   文件输入框状态: {check}')

        # 上传图片
        if upload_ref_image(image_path):
            print(f'   ✅ 上传成功')
        else:
            print(f'   ❌ 上传失败')

        time.sleep(2)

def main():
    print('🔧 检查 Chrome...')
    if not check_chrome():
        print('❌ Chrome Debug 未启动，请先运行 start.sh'); sys.exit(1)
    print('✅ Chrome 运行中')

    print('🌐 打开豆包...')
    run('open "https://www.doubao.com/"', timeout=10)
    time.sleep(3)

    # 登录验证
    print('🔐 验证登录状态...')
    r = subprocess.run(['python3', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_login.py')])
    if r.returncode != 0:
        print('❌ 登录验证失败，请扫码登录后重试'); sys.exit(1)
    print('✅ 登录验证通过')

    print('🎨 进入 AI 创作页面...')
    snap = run('snapshot -i', timeout=8)
    ai_ref = find_ref(snap, 'AI 创作')
    if ai_ref:
        run(f'click @{ai_ref}', timeout=8)
    time.sleep(4)

    print('🎬 进入视频生成模式...')
    click_video_tab_button()
    time.sleep(3)

    # 找视频输入框
    ta_ref = None
    for attempt in range(5):
        snap = run('snapshot -i', timeout=8)
        ta_ref = find_ref(snap, '添加照片，描述你想生成的视频')
        if ta_ref:
            print(f'   ✅ 找到 @{ta_ref}')
            break
        print(f'   第 {attempt+1} 次: 未找到输入框，重试...')
        time.sleep(2)

    if not ta_ref:
        # 尝试 JS 方式直接操作 DOM
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
            print('❌ 未找到视频描述输入框'); sys.exit(1)
        time.sleep(1)
        # 重新获取 snapshot 找 ref
        snap = run('snapshot -i', timeout=8)
        ta_ref = find_ref(snap, '添加照片，描述你想生成的视频')
        if not ta_ref:
            for line in snap.split('\n'):
                if 'ref=' in line and '添加照片' in line:
                    m = re.search(r'ref=(e\d+)', line)
                    if m:
                        ta_ref = m.group(1)
                        break

    if not ta_ref:
        print('❌ 未找到视频描述输入框'); sys.exit(1)

    print(f'   视频输入框 @{ta_ref}')

    # 上传参考图（在填写提示词之前）
    if REF_IMAGES_DIR:
        print(f'📁 参考图目录: {REF_IMAGES_DIR}')
        upload_ref_images()
        time.sleep(2)

    print(f'✍️ 填写: {PROMPT}')
    # 优先使用 JS 方式直接填写（更可靠）
    escaped_prompt = PROMPT.replace('"', '\\"')
    js_fill = cdp_js(f'''
        (function() {{
            var els = document.querySelectorAll("textarea, [contenteditable], input[type='text']");
            for (var i=0; i<els.length; i++) {{
                var el = els[i];
                if (el.offsetHeight > 0 && el.offsetWidth > 0) {{
                    el.scrollIntoView({{block:"center"}});
                    el.focus();
                    var ns = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set;
                    ns.call(el, "{escaped_prompt}");
                    el.dispatchEvent(new Event("input",{{bubbles:true}}));
                    el.dispatchEvent(new Event("change",{{bubbles:true}}));
                    return "filled:" + el.tagName;
                }}
            }}
            return "fill failed";
        }})()
    ''')
    if 'filled' in js_fill:
        print(f'   ✅ JS 填写成功')
    else:
        # fallback 到 fill 命令
        print(f'   JS 方式失败，尝试 fill 命令...')
        run(f'fill @{ta_ref} "{PROMPT}"', timeout=5)
    time.sleep(1)

    print('🚀 点击发送按钮...')
    cdp_js('''
        (function() {
            var btn = document.querySelector('[class*="send-btn-wrapper"]');
            if (!btn) return 'not found';
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

    # 等待视频生成
    video_url = wait_for_video()
    
    if not video_url or 'no video' in str(video_url) or 'error' in str(video_url):
        print(f'❌ 视频获取失败: {video_url}')
        run(f'screenshot {OUTPUT_DIR}/fail_{int(time.time())}.png', timeout=10)
        sys.exit(1)

    # 下载视频
    safe = re.sub(r'[^\w\u4e00-\u9fff\s]', '', PROMPT).strip()[:20] or 'video'
    ts = int(time.time())
    filename = f'{safe}_{ts}.mp4'
    filepath = f'{OUTPUT_DIR}/{filename}'
    
    print(f'📥 下载视频...')
    size = download_video(video_url, filepath)
    
    if isinstance(size, int):
        print(f'   ✅ {size//1024//1024}MB → {filename}')
    else:
        print(f'   ❌ {size}')
        sys.exit(1)

    print()
    print('=' * 40)
    print(f'✅ 完成！')
    print(f'📁 {filepath}')
    print(f'📝 {PROMPT}')
    print('=' * 40)

if __name__ == '__main__':
    main()
