#!/usr/bin/env python3
"""
浏览器标签页管理工具
功能：关闭多余标签页，保留至少一个空白页
"""

import subprocess, json, time, http.client

CDP_HOST = '127.0.0.1'
CDP_PORT = 9222


def check_chrome():
    """检查 Chrome 是否运行"""
    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=3)
        c.request('GET', '/json/version')
        c.getresponse().read(); c.close()
        return True
    except:
        return False


def run(cmd, timeout=12):
    """执行 agent-browser 命令"""
    try:
        r = subprocess.run(f'agent-browser --cdp {CDP_PORT} {cmd}', shell=True,
                         capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return ''


def close_all_tabs(exclude_id=''):
    """关闭所有标签页，可选排除指定 ID

    关闭浏览器中除 exclude_id 外的所有标签页，
    如果关闭后没有任何标签页残留，则创建一个 about:blank 空白页。
    """
    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
        c.request('GET', '/json/list')
        pages = json.loads(c.getresponse().read()); c.close()

        remaining = [p for p in pages if p.get('id') != exclude_id]
        closed = 0
        for page in remaining:
            target_id = page.get('id', '')
            if target_id:
                c2 = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
                c2.request('DELETE', f'/json/close/{target_id}')
                c2.getresponse().read(); c2.close()
                closed += 1

        print(f'🔚 已关闭标签页 ({closed}个)' + (f'，保留标签页 {exclude_id}' if exclude_id else ''))

        # 确保至少保留一个标签页
        if exclude_id:
            c3 = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
            c3.request('GET', '/json/list')
            still_open = json.loads(c3.getresponse().read()); c3.close()
            if not still_open:
                print('⚠️ 无标签页残留，创建空白页...')
                run('open "about:blank"', timeout=5)
    except Exception as e:
        print(f'⚠️ 关闭标签页失败: {e}')


def close_other_tabs():
    """关闭除当前活动标签页外的所有标签页，保留至少一个空白页"""
    try:
        c = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
        c.request('GET', '/json/list')
        pages = json.loads(c.getresponse().read()); c.close()

        if not pages:
            # 没有标签页，创建空白页
            run('open "about:blank"', timeout=5)
            print('🔚 已创建空白页')
            return

        # 保留最后一个（通常是当前活动页），关闭其余
        keep_id = pages[-1].get('id', '')
        others = [p for p in pages[:-1] if p.get('id')]
        closed = 0
        for page in others:
            target_id = page.get('id', '')
            c2 = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
            c2.request('DELETE', f'/json/close/{target_id}')
            c2.getresponse().read(); c2.close()
            closed += 1

        # 如果全部关闭了（只剩一个且是当前页），确保它是 about:blank
        c3 = http.client.HTTPConnection(CDP_HOST, CDP_PORT, timeout=5)
        c3.request('GET', '/json/list')
        still_open = json.loads(c3.getresponse().read()); c3.close()

        if not still_open:
            run('open "about:blank"', timeout=5)
            print('🔚 已关闭所有标签页，创建空白页')
        else:
            print(f'🔚 已关闭 {closed} 个标签页，保留 1 个')
    except Exception as e:
        print(f'⚠️ 关闭标签页失败: {e}')
