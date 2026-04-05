#!/usr/bin/env python3
"""
豆包发送消息脚本 v3
功能：向豆包发送消息并获取回复
用法: python3 send_message.py "你的问题"

前置条件：
1. 先运行 start.sh 启动 Chrome Debug 浏览器
2. 先在浏览器中手动登录豆包
"""

import subprocess, json, sys, time, os, re, http.client, asyncio, websockets

CDP_PORT = 9222

def get_doubao_page():
    """获取豆包页面"""
    try:
        conn = http.client.HTTPConnection('127.0.0.1', CDP_PORT, timeout=10)
        conn.request('GET', '/json/list')
        pages = json.loads(conn.getresponse().read())
        conn.close()
        for p in pages:
            if 'doubao' in p.get('url', '').lower():
                return p
        return pages[0] if pages else None
    except Exception as e:
        print(f'❌ 获取页面失败: {e}')
        return None

async def cdp_eval(ws_url, js):
    """在页面中执行JS并返回结果"""
    try:
        ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=10)
        mid = 1
        async def send(method, params=None):
            nonlocal mid
            await ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
            mid += 1
            while True:
                r = await asyncio.wait_for(ws.recv(), timeout=10)
                d = json.loads(r)
                if d.get('id') == mid - 1:
                    return d
        rv = await send('Runtime.evaluate', {'expression': js, 'returnByValue': True})
        await ws.close()
        return rv.get('result', {}).get('result', {}).get('value', '')
    except Exception as e:
        return f'error: {e}'

async def cdp_send_enter(ws_url):
    """通过CDP发送Enter键"""
    try:
        ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=10)
        mid = 1
        async def send(method, params=None):
            nonlocal mid
            await ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
            mid += 1
            while True:
                r = await asyncio.wait_for(ws.recv(), timeout=10)
                d = json.loads(r)
                if d.get('id') == mid - 1:
                    return d
        await send('Input.dispatchKeyEvent', {'type': 'keyDown', 'modifiers': 0, 'windowsVirtualKeyCode': 13, 'key': 'Enter', 'code': 'Enter'})
        await send('Input.dispatchKeyEvent', {'type': 'keyUp', 'modifiers': 0, 'windowsVirtualKeyCode': 13, 'key': 'Enter', 'code': 'Enter'})
        await ws.close()
        return True
    except Exception as e:
        return f'error: {e}'

def check_login_status(ws_url):
    """检查登录状态"""
    result = asyncio.run(cdp_eval(ws_url, '''
        (function() {
            var text = document.body.innerText;
            if (text.includes('抖音一键登录') || text.includes('登录以解锁')) {
                return 'popup';
            }
            if (text.includes('登录') && text.includes('注册')) {
                return 'not_logged_in';
            }
            // 检查右上角用户头像
            var avatars = document.querySelectorAll('[class*="avatar"], [class*="user"]');
            for (var a of avatars) {
                if (a.offsetHeight > 0) return 'logged_in';
            }
            // 检查是否有发送按钮
            var sendBtn = document.querySelector('[class*="send"], [class*="submit"]');
            if (sendBtn) return 'logged_in';
            return 'unknown';
        })()
    '''))
    return result

def close_popup(ws_url):
    """关闭弹窗"""
    asyncio.run(cdp_eval(ws_url, '''
        (function() {
            // 按ESC关闭弹窗
            document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true}));
        })()
    '''))
    time.sleep(0.5)

def send_message(message):
    """发送消息给豆包并获取回复"""
    page = get_doubao_page()
    if not page:
        print('❌ 未找到豆包页面，请先运行 start.sh')
        return None

    ws_url = page['webSocketDebuggerUrl']
    print(f'✅ 找到豆包页面: {page.get("title", "")[:40]}')

    # 检查登录状态
    login_status = check_login_status(ws_url)
    print(f'🔐 登录状态: {login_status}')

    if 'popup' in login_status:
        print('🔄 关闭登录弹窗...')
        close_popup(ws_url)

    if 'not_logged_in' in login_status:
        print('⚠️ 未登录！请先在浏览器中手动登录豆包')
        print('   登录后状态会自动保存，后续无需再登录')
        return None

    # 查找并点击输入框
    print('🖊️ 填写消息...')
    result = asyncio.run(cdp_eval(ws_url, f'''
        (function() {{
            // 找输入框
            var input = document.querySelector('input[placeholder*="发消息"], textarea[placeholder*="发消息"]');
            if (!input) {{
                // 尝试找可见的文本输入框
                var all = document.querySelectorAll('input, textarea');
                for (var el of all) {{
                    var style = window.getComputedStyle(el);
                    if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetHeight > 0) {{
                        if (el.className.includes('input') || el.placeholder?.includes('消息') || el.type === 'text') {{
                            input = el;
                            break;
                        }}
                    }}
                }}
            }}
            if (input) {{
                input.scrollIntoView({{block: 'center'}});
                input.focus();
                // 清空并填写
                input.value = '';
                input.value = "{message}";
                // 触发input事件
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                return 'filled';
            }}
            return 'input_not_found';
        }})()
    '''))
    print(f'   填写结果: {result}')

    time.sleep(0.3)

    # 点击发送按钮或按回车
    print('🚀 发送消息...')
    send_result = asyncio.run(cdp_eval(ws_url, '''
        (function() {
            // 方式1：找发送按钮点击
            var sendBtn = document.querySelector('[class*="send"], [class*="submit"], button[aria-label*="发送"], button[aria-label*="send"]');
            if (sendBtn && sendBtn.offsetHeight > 0) {
                sendBtn.click();
                return 'clicked_send_button';
            }
            return 'need_enter';
        })()
    '''))
    print(f'   发送结果: {send_result}')

    # 如果没有发送按钮，使用CDP发送Enter键
    if 'need_enter' in str(send_result):
        asyncio.run(cdp_send_enter(ws_url))
        print('   已通过CDP发送Enter键')

    print('⏳ 等待豆包回复（最多60秒）...')
    
    # 等待消息发送出去（检查输入框是否变空）
    for i in range(15):
        time.sleep(1)
        check = asyncio.run(cdp_eval(ws_url, f'''
            (function() {{
                var input = document.querySelector('input[placeholder*="发消息"], textarea[placeholder*="发消息"]');
                if (input && input.value.includes("{message[:10]}")) {{
                    return 'still_has_text';
                }}
                return 'text_sent';
            }})()
        '''))
        if 'text_sent' in str(check):
            print(f'   消息已发送 ({i+1}秒)')
            break
        if i == 14:
            print(f'   警告: 输入框仍有内容 ({i+1}秒)')

    # 额外等待让豆包生成回复
    time.sleep(5)

    # 轮询检查是否有新回复
    last_content = ''
    for i in range(55):
        time.sleep(1)
        content = asyncio.run(cdp_eval(ws_url, '''
            (function() {
                // 找对话区域的内容
                var msgs = [];
                // 尝试多种选择器
                var selectors = ['[class*="message"]', '[class*="bubble"]', '[class*="chat-item"]', '[class*="chat-message"]', '[class*="conversation"]'];
                selectors.forEach(function(sel) {
                    document.querySelectorAll(sel).forEach(function(el) {
                        if (el.offsetHeight > 0 && el.textContent.trim().length > 5) {
                            var txt = el.textContent.trim();
                            // 过滤掉侧边栏内容
                            if (!txt.includes('新对话') && !txt.includes('AI 创作') && !txt.includes('快速PPT') && !txt.includes('生成图像') && !txt.includes('帮我写作') && !txt.includes('翻译') && !txt.includes('编程')) {
                                msgs.push(txt.slice(0, 500));
                            }
                        }
                    });
                });
                return msgs.slice(-8).join('|||');
            })()
        '''))
        
        # 如果内容有变化，说明有回复
        if content and content != last_content and len(str(content)) > 20:
            print(f'   检测到回复变化 ({i+1}秒)')
            last_content = str(content)
        
        if i % 10 == 0 and i > 0:
            print(f'   等待中... {i}秒')
    
    # 最终获取回复
    print('📥 获取最终回复...')
    final_content = asyncio.run(cdp_eval(ws_url, '''
        (function() {
            // 获取页面上所有可能的回复内容
            var allText = document.body.innerText;
            // 返回最后3000字符，应该包含最新对话
            return allText.slice(-3000);
        })()
    '''))
    
    return str(final_content) if final_content else None

def extract_reply(full_text):
    """从页面文本中提取豆包的回复"""
    if not full_text:
        return None

    lines = full_text.split('\n')
    replies = []
    capture = False
    current = []

    # 需要过滤的关键词
    skip_keywords = ['新对话', 'AI 创作', '历史对话', '下载豆包', '关于豆包', '快速PPT', '登录', '生成图像', '帮我写作', '翻译', '编程', '发消息', '抖音一键登录', '登录以解锁', '搜索对话']

    # 追问关键词（豆包反问用户时）
    question_keywords = ['你觉得', '你想要', '你希望', '你希望我', '你是想', '你有什么', '可以告诉我', '你更喜欢', '你有没有', '请问']

    for line in lines:
        line = line.strip()
        # 跳过导航和侧边栏
        if any(kw in line for kw in skip_keywords):
            if capture and current:
                replies.append('\n'.join(current))
                current = []
            capture = False
            continue

        # 跳过推荐话题（通常是短句列表）
        if len(line) < 30 and any(kw in line for kw in ['短视频', '寒假作业', '办公室', '熬夜', '秒睡', '签名', '二次元', '十年', 'PPT', '图像', '编程', '翻译', '写作', '车', '回复', '下载豆包', '豆包电脑版', '内容由豆包 AI 生成', 'AI 创作', '新对话', '历史对话']):
            continue

        # 跳过豆包的追问（以问号结尾，且是反问）
        if any(line.endswith('？') or line.endswith('?') for _ in [line]) and any(kw in line for kw in question_keywords):
            capture = False
            current = []
            continue

        # 收集有意义的行
        if len(line) > 3:
            capture = True
            current.append(line)

    if current:
        replies.append('\n'.join(current))

    # 返回最后的回复（去掉可能的输入框内容）
    if replies:
        reply = replies[-1] if replies else None
        # 去掉输入框的内容
        if reply and '发消息' in reply:
            reply = reply.split('发消息')[0].strip()
        return reply
    return None

def main():
    if len(sys.argv) < 2:
        print('用法: python3 send_message.py "你的问题"')
        print('示例: python3 send_message.py "你好，你是谁？"')
        sys.exit(1)
    
    message = sys.argv[1]
    print(f'📤 发送: {message}')
    print()
    
    full_content = send_message(message)
    
    if full_content:
        reply = extract_reply(full_content)
        print()
        print('=' * 50)
        print('🤖 豆包回复:')
        print(reply[-1500:] if reply and len(reply) > 1500 else (reply or '未获取到有效回复'))
        print('=' * 50)
    else:
        print()
        print('❌ 未获取到回复')

if __name__ == '__main__':
    main()
