# lei-doubao-browser 详细文档

## 概述

通过 Chrome Debug 模式 + agent-browser 实现 AI 浏览器自动化，核心价值是**继承真实登录状态**，让 AI 可以像真人一样操作需要登录的网站。

## 原理详解

### 为什么需要独立数据目录？

Chrome 有个安全机制：**不允许在默认用户数据目录上开启远程调试端口**。这是为了防止恶意程序窃取浏览器数据。

但这也意味着：AI 如果想控制浏览器，必须用一个新的数据目录。而新目录是空的，没有任何网站的登录状态。

### 解决方案：复制登录状态

把当前浏览器的这些文件复制到新目录：
- `Cookies` - 网站登录凭证
- `Login Data` - 保存的密码
- `Web Data` - 表单自动填充
- `Preferences` / `Secure Preferences` - 浏览器设置
- `Local State` - 全局配置

复制后，新浏览器就"继承"了所有登录状态。

## 安装与配置

### 数据目录已配置

登录状态文件已复制到：
```
~/.config/chromium-debug/Default/
├── Cookies
├── Login Data
├── Web Data
├── Preferences
├── Secure Preferences
└── Local State
```

### 启动浏览器

```bash
# headless 无头模式（默认，不显示窗口）
bash ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/start.sh

# 测试模式（显示浏览器窗口，方便调试）
bash ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/start.sh test
```

输出：
```
启动 headless 模式...
Chrome Debug 启动成功 (CDP 9222, headless)
```

### 连接控制

```bash
agent-browser connect http://127.0.0.1:9222
```

### AI 图片生成

```bash
# 生成图片（自动打开豆包并生成）
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_image.py "一只可爱的小柴犬在海边冲浪" /tmp

# 截图保存在 /tmp/doubao_img_TIMESTAMP.png
```

## 使用示例

### 操作豆包

```bash
# 打开豆包
agent-browser open https://www.doubao.com/
agent-browser wait --load networkidle

# 发消息
agent-browser snapshot -i
agent-browser fill @e38 "你好"
agent-browser press Enter
```

### 操作微博

```bash
agent-browser open https://weibo.com/
agent-browser wait --load networkidle
# 已登录可直接浏览
```

### 操作知乎

```bash
agent-browser open https://www.zhihu.com/
agent-browser wait --load networkidle
# 已登录可直接浏览
```

## 维护

### 查看当前打开的标签页

```bash
curl -s http://127.0.0.1:9222/json/list | python3 -m json.tool
```

### 更新登录状态

在 Debug 浏览器中登录新网站后，状态自动保存。如需同步其他浏览器：
```bash
# 复制新的 cookies
cp <path-to-source-cookies> ~/.config/chromium-debug/Default/Cookies
```

### 关闭浏览器

```bash
pkill -f "chrome-linux64/chrome"
```

## 注意事项

1. **不要在公共电脑使用** - 调试端口只监听 127.0.0.1，但数据目录包含所有登录凭证
2. **定期备份** - 重要账号建议定期检查登录状态
3. **版本匹配** - Chrome for Testing 145 兼容性最佳
