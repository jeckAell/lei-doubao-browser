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

EXTRA_PROMPT = "解析视频，分析出视频脚本、视频特点、爆火原因，并为这个视频起一个简短有吸引力的标题。回复最后请以【标题: xxx】和【分类: xxx】格式标注视频标题和所属分区（如【标题: 这条视频为什么爆火】）【分类: 搞笑】"

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

def extract_title_from_input(text):
    """从分享内容中提取标题（通常在#标签或链接之前的中文内容）"""
    # 去掉链接部分
    text_without_url = re.sub(r'https?://\S+', '', text)
    # 去掉复制提示
    text_without_url = re.sub(r'复制此链接.*', '', text_without_url)
    # 去掉 # 标签（整块去除）
    text_without_tags = re.sub(r'#\S*', '', text_without_url)
    # 清理多余空白
    text_cleaned = re.sub(r'\s+', ' ', text_without_tags).strip()
    # 去掉开头的抖音格式信息如 "6.94 Syt:/ 07/04 a@N.Jv"
    text_cleaned = re.sub(r'^[\d.]+\s*Syt:.*?@\S+\s*', '', text_cleaned)
    # 去掉开头和结尾的 #残留和空白
    text_cleaned = text_cleaned.strip(' #')
    # 提取中文句子作为标题（排除含 # 的行）
    lines = text_cleaned.split(' ')
    for line in lines:
        line = line.strip()
        # 找第一个超过5个字符的中文句子，且不含 #
        if len(line) > 5 and re.search(r'[\u4e00-\u9fff]', line) and '#' not in line:
            return line
    return ''

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
    """从 DOM 元素 class='flow-markdown-body' 提取 AI 回复"""
    result = cdp_js('''
        (function() {
            var el = document.querySelector('[class*="flow-markdown-body"]');
            if (!el) return "";
            return el.innerText || el.textContent || "";
        })()
    ''')
    if result and len(result) > 50:
        return result[:5000]
    return ''

def trim_trailing_question(text):
    """去除豆包在回复末尾添加的连续询问"""
    # 匹配常见询问模式：要不要/是否/想不想等开头的问题
    patterns = [
        r'要不要我帮你',
        r'要不要',
        r'我可以帮你',
        r'需要我帮你',
        r'想不想',
        r'要不要再',
        r'需要我再',
    ]
    for p in patterns:
        idx = text.rfind(p)
        if idx > len(text) // 2:  # 在后半部分找到
            # 找到这个问句的结束位置（句号、问号或换行）
            remaining = text[idx:]
            m = re.search(r'[？?\n]', remaining)
            if m:
                return text[:idx].strip()
    return text

def parse_and_save(douyin_url, user_input, response_text):
    response_text = trim_trailing_question(response_text)

    # 从回复中提取标题标记（优先使用豆包返回的标题）
    title_match = re.search(r'【标题[：:]\s*([^】]+)】', response_text)
    if title_match:
        title = title_match.group(1).strip()
        # 去掉标题标记
        response_text = re.sub(r'【标题[：:]\s*[^】]+】\s*', '', response_text).rstrip()
    else:
        title = ''

    # 如果标题为空（豆包未返回标题），尝试从用户输入提取
    if not title:
        title = extract_title_from_input(user_input)
        # 如果用户输入也只是链接没有其他内容，标题为空
        if not title:
            title = douyin_url

    # 从回复中提取分类标记（支持全角或半角冒号）
    category_match = re.search(r'【分类[：:]\s*([^】]+)】', response_text)
    if category_match:
        category = category_match.group(1).strip()
        # 去掉分类标记后的回复内容
        response_text = re.sub(r'【分类[：:]\s*[^】]+】\s*$', '', response_text).rstrip()
    else:
        category = '待分类'

    tags = []
    tag_keywords = ['恐怖', '搞笑', '治愈', '萌宠', '美食', '剧情', '反转', '感动',
                    '可爱', '震撼', '温暖', '甜', '虐', '悬疑', '创意', '生活',
                    '日常', '挑战', '变装', '舞蹈', '唱歌', '知识', '干货', '技巧']
    for kw in tag_keywords:
        if kw in response_text:
            tags.append(kw)
    if not tags:
        tags = ['待分类']

    # 如果分类是待分类，从标签中推断
    if category == '待分类':
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

    # 发送 - 按回车键
    print('🚀 发送消息...')
    send_result = cdp_js('''
        (function() {
            var ta = document.querySelector("textarea");
            if (!ta) return "no textarea";
            ta.focus();
            ta.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
            ta.dispatchEvent(new KeyboardEvent("keyup", {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
            return "enter sent";
        })()
    ''')
    print(f'   发送: {send_result}')

    # 等待回复（固定 30 秒，和 generate_image.py 一致）
    print('⏳ 等待回复（60秒）...')
    time.sleep(60)

    # 获取回复
    print('📥 获取回复内容...')
    run(f'screenshot /tmp/response_check_{int(time.time())}.png', timeout=10)
    ai_response = get_ai_response()
    print(f'   回复长度: {len(ai_response)} 字')
    print(f'   回复预览: {ai_response[:200]}')

    if len(ai_response) < 50:
        print('⚠️ 回复内容过短，截图保存')
        run(f'screenshot /tmp/analyze_response_{int(time.time())}.png', timeout=10)

    print('💾 保存到脚本库...')
    entry = parse_and_save(douyin_url, USER_INPUT, ai_response)

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
