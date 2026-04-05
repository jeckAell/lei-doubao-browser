#!/usr/bin/env python3
"""
豆包 AI 视频解析脚本
用法: python3 analyze_video.py "抖音视频链接或分享内容"

功能：分析抖音视频，提取视频脚本、特点、爆火原因，保存到视频脚本库
"""

import subprocess, json, sys, time, os, re, http.client

CDP_HOST = '127.0.0.1'
CDP_PORT = 9222
USER_INPUT = sys.argv[1] if len(sys.argv) > 1 else None
SCRIPTS_FILE = os.path.expanduser('~/.openclaw/workspace/doubao/sheet/scripts/data/scripts.json')

if not USER_INPUT:
    print('用法: python3 analyze_video.py "抖音视频链接或分享内容"')
    sys.exit(1)

EXTRA_PROMPT = "解析视频，分析出视频脚本、视频特点、爆火原因"

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
    for line in text.split('\n'):
        if kw not in line:
            continue
        m = re.search(r'ref=(e\d+)', line)
        if m:
            return m.group(1)
    return None

def cdp_js(js):
    """执行 JS 并返回结果字符串"""
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

def get_next_id(scripts):
    if not scripts:
        return 1
    return max(s.get('id', 0) for s in scripts) + 1

def extract_douyin_url(text):
    patterns = [
        r'https?://v\.douyin\.com/[a-zA-Z0-9]+',
        r'https?://www\.douyin\.com/video/\d+',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return None

def load_scripts():
    if not os.path.exists(SCRIPTS_FILE):
        return []
    try:
        with open(SCRIPTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_scripts(scripts):
    os.makedirs(os.path.dirname(SCRIPTS_FILE), exist_ok=True)
    with open(SCRIPTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(scripts, f, ensure_ascii=False, indent=2)

def get_ai_response():
    """从 window._ROUTER_DATA 提取 AI 回复"""
    result = cdp_js('''
        (function() {
            try {
                var data = window._ROUTER_DATA;
                if (!data) return "";
                var str = JSON.stringify(data);
                var idx = str.indexOf("\\"text\\":\\"");
                if (idx < 0) return "";
                var start = idx + 9;
                var end = start;
                while (end < str.length) {
                    if (str.charAt(end) === "\\"" && str.charAt(end-1) !== "\\\\") break;
                    end++;
                }
                return str.substring(start, end);
            } catch(e) { return "error:" + e.message; }
        })()
    ''')
    if result and len(result) > 50 and not result.startswith('error'):
        return result[:5000]

    full_json = cdp_js('JSON.stringify(window._ROUTER_DATA || {}).substring(0, 80000)')
    if full_json and len(full_json) > 1000:
        matches = re.findall(r'"text":"((?:[^"\\\\]|\\\\.){200,})"', full_json)
        if matches:
            return matches[-1][:5000]
    return ''

def parse_and_save(douyin_url, response_text):
    lines = [l.strip() for l in response_text.split('\n') if l.strip()]
    first_meaningful = next((l for l in lines if len(l) > 10), None)
    title = first_meaningful[:30] if first_meaningful else douyin_url

    tags = []
    tag_keywords = ['恐怖', '搞笑', '治愈', '萌宠', '美食', '剧情', '反转', '感动',
                    '可爱', '震撼', '温暖', '甜', '虐', '悬疑', '创意', '生活',
                    '日常', '挑战', '变装', '舞蹈', '唱歌', '知识', '干货', '技巧']
    for kw in tag_keywords:
        if kw in response_text:
            tags.append(kw)
    if not tags:
        tags = ['待分类']

    category = '待分类'
    for cat in ['剧情', '搞笑', '知识', '美食', '萌宠', '生活', '颜值', '音乐', '舞蹈', '游戏']:
        if cat in tags:
            category = cat
            break

    new_entry = {
        "id": 0,
        "title": title,
        "category": category,
        "platform": "抖音",
        "content": response_text[:5000],
        "tags": tags,
        "source": "analyze",
        "date": time.strftime('%Y-%m-%d'),
        "crawled_at": None
    }
    scripts = load_scripts()
    new_entry['id'] = get_next_id(scripts)
    scripts.append(new_entry)
    save_scripts(scripts)
    print(f'   ✅ 已保存: ID={new_entry["id"]} - {title}')
    return new_entry

def main():
    print('🔧 检查 Chrome...')
    if not check_chrome():
        print('❌ Chrome Debug 未启动，请先运行 start.sh'); sys.exit(1)
    print('✅ Chrome 运行中')

    douyin_url = extract_douyin_url(USER_INPUT)
    if not douyin_url:
        print('⚠️ 未检测到抖音链接')
        douyin_url = USER_INPUT[:100]
    print(f'📎 抖音链接: {douyin_url}')

    print('🌐 打开豆包...')
    run('open "https://www.doubao.com/chat/"', timeout=10)
    time.sleep(3)

    # 登录验证
    print('🔐 验证登录状态...')
    r = subprocess.run(['python3', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_login.py')])
    if r.returncode != 0:
        print('❌ 登录验证失败，请扫码登录后重试'); sys.exit(1)
    print('✅ 登录验证通过')

    # 点击"新对话"
    print('💬 开始新对话...')
    snap = run('snapshot -i', timeout=8)
    new_conv_ref = find_ref(snap, '新对话')
    if new_conv_ref:
        run(f'click @{new_conv_ref}', timeout=8)
    time.sleep(3)

    # 找消息输入框
    print('🔍 找消息输入框...')
    ta_ref = None
    for attempt in range(5):
        snap = run('snapshot -i', timeout=8)
        ta_ref = find_ref(snap, '发消息')
        if ta_ref:
            print(f'   ✅ 找到 @{ta_ref}')
            break
        print(f'   第 {attempt+1} 次: 未找到，重试...')
        time.sleep(2)

    if not ta_ref:
        print('❌ 未找到消息输入框'); sys.exit(1)

    # 组合完整消息
    full_message = f'{USER_INPUT}\n\n{EXTRA_PROMPT}'

    # 填写消息
    print(f'✍️ 填写: {full_message[:50]}...')
    run(f'fill @{ta_ref} "{full_message}"', timeout=5)
    time.sleep(1)

    # 发送 - 使用 CDP 坐标点击（和 generate_image.py 完全一致的方式）
    print('🚀 发送消息...')
    send_result = cdp_js('''
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
    print(f'   发送: {send_result}')

    # 等待回复（固定 30 秒，和 generate_image.py 一致）
    print('⏳ 等待回复（60秒）...')
    time.sleep(60)

    # 获取回复
    print('📥 获取回复内容...')
    ai_response = get_ai_response()
    print(f'   回复长度: {len(ai_response)} 字')

    if len(ai_response) < 50:
        print('⚠️ 回复内容过短，截图保存')
        run(f'screenshot /tmp/analyze_response_{int(time.time())}.png', timeout=10)

    print('💾 保存到脚本库...')
    entry = parse_and_save(douyin_url, ai_response)

    print()
    print('=' * 40)
    print(f'✅ 完成！')
    print(f'📁 {SCRIPTS_FILE}')
    print(f'📝 {entry["title"]}')
    print(f'🏷️ {entry["tags"]}')
    print(f'📊 ID: {entry["id"]}')
    print('=' * 40)

if __name__ == '__main__':
    main()
