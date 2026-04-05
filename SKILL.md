---
name: lei-doubao-browser
description: 豆包浏览器自动化 - 通过 Chrome Debug 模式 + agent-browser 实现 AI 像真人一样操控浏览器，继承已有登录状态，支持抖音、微博、豆包等需要登录的站点，以及 AI 图片和视频生成功能。
version: 1.3.0
required_permissions:
  - shell
---

# 豆包浏览器自动化

## 核心思路

通过 Chrome Debug 模式 + 独立用户数据目录，让 AI 继承你已有的登录状态（Cookies、密码、表单数据），无需手动登录、不需要插件，AI 可以直接控制浏览器操作任何已登录的网站。

## 工作原理

1. Chrome 安全机制：不允许在默认用户数据目录上开启远程调试端口
2. 解决方案：复制已有登录状态到独立目录，用该目录启动带调试端口的 Chrome
3. agent-browser 通过 Chrome DevTools Protocol (CDP) 连接并控制浏览器

## 目录结构

```
lei-doubao-browser/
├── SKILL.md              # 本文件
├── README.md             # 详细文档
└── scripts/
    ├── start.sh           # 启动 Chrome Debug 浏览器
    ├── check_login.py     # 登录验证脚本（未登录时弹出二维码）
    ├── generate_image.py  # AI 图片生成脚本
    ├── generate_video.py  # AI 视频生成脚本
    └── analyze_video.py   # 视频链接分析 + 脚本生成（无需登录）
```

## 快速开始

### 第一步：启动 Chrome Debug 浏览器

```bash
bash ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/start.sh
```

浏览器会在后台启动，监听 `9222` 端口。

### 第二步：连接并控制浏览器

```bash
# 连接 CDP
agent-browser connect http://127.0.0.1:9222

# 打开网页
agent-browser open https://www.doubao.com/

# 查看页面元素
agent-browser snapshot -i

# 截图
agent-browser screenshot /tmp/output.png

# 发消息（找到输入框后）
agent-browser fill @e38 "你好"
agent-browser press Enter
```

## 常用命令

### 页面操作
```bash
agent-browser open <url>                    # 打开网页
agent-browser snapshot -i                    # 获取页面元素
agent-browser screenshot [path]              # 截图
agent-browser wait --load networkidle        # 等待加载完成
```

### 元素交互
```bash
agent-browser click @e1                      # 点击元素
agent-browser fill @e2 "文本"               # 填写输入框
agent-browser press Enter                    # 按回车
agent-browser scroll down 500                # 向下滚动
```

### 多标签管理
```bash
# 查看所有标签页
curl -s http://127.0.0.1:9222/json/list

# 切换到指定标签（通过 CDP ws URL）
agent-browser goto <ws-url>
```

## 登录验证

每次打开豆包页面后，必须先验证登录状态，未登录则无法使用 AI 创作功能。

```bash
# 启动浏览器后，运行登录验证
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/check_login.py
```

### 验证流程

1. 打开豆包页面
2. 检测右上角是否有「登录」按钮
3. 有按钮 → 点击按钮 → 检测到二维码弹窗 → 截图提示用户扫码
4. 无按钮 → 已登录，继续后续操作

### 未登录处理

脚本检测到未登录时会：
- 自动点击登录按钮
- 弹出二维码登录框
- 截图保存到 `~/.openclaw/workspace/doubao/loginImgs/` 目录
- 提示用户扫码登录
- 脚本退出（需用户登录后重新运行）

## 登录状态同步

如果需要在 Debug 浏览器中登录新网站：

1. 在 Debug 浏览器中手动登录一次
2. 登录状态会自动保存在 `~/.config/chromium-debug/` 目录
3. 下次启动时自动继承

如需从其他浏览器同步新的登录状态，复制对应 cookies 即可：
```bash
cp <源浏览器cookies路径> ~/.config/chromium-debug/Default/Cookies
```

## 优势对比

| 特性 | 插件模式 | Chrome Debug 模式 |
|------|---------|------------------|
| 首次使用 | 需手动点击插件 | 自动连接 |
| AI 重启后 | 需重新点击 | 自动重连 |
| 登录状态 | 需手动登录 | 自动继承 |
| 反爬虫风险 | 易被识别 | 真实浏览器指纹 |
| 多标签支持 | 可能中断 | 完全支持 |

## 技术细节

- **Chrome 路径**: `~/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome`
- **用户数据目录**: `~/.config/chromium-debug/`
- **CDP 端口**: `9222`
- **启动参数**: `--remote-debugging-port=9222 --user-data-dir=... --no-sandbox`

---

## AI 创作工作流

### 完整流程（两种路径）

```
打开豆包页面
    │
    ▼
┌─────────────────────┐
│   登录验证 check_login.py   │
└─────────────────────┘
    │
    ├── 未登录 → 点击登录按钮 → 截图保存到 ~/.openclaw/workspace/doubao/loginImgs/ → 提示用户扫码 → 脚本退出
    │
    └── 已登录 → 点击「AI 创作」→ 选择生成模式
                                │
                                ├── 图片模式 → generate_image.py
                                └── 视频模式 → generate_video.py
```

### 路径一：未登录

用户尚未登录时，运行 `check_login.py` 会：
1. 检测到右上角有「登录」按钮
2. 自动点击登录按钮
3. 弹出二维码登录框
4. 截图保存到 `~/.openclaw/workspace/doubao/loginImgs/login_qr_{时间戳}.png`
5. 打印截图路径，提示用户扫码
6. 脚本退出（用户扫码后需重新运行）

### 路径二：已登录

用户已登录时，运行图片或视频脚本会：
1. 打开豆包页面
2. 验证登录状态（已登录，无按钮）
3. 点击「AI 创作」进入创作模式
4. 执行对应生成脚本

---

## 豆包对话（发送消息）

通过 CDP 直接控制 Chrome，向豆包发送消息并获取回复。

### 使用方式

```bash
# 1. 先启动 Chrome Debug 浏览器
bash ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/start.sh

# 2. 在浏览器中手动登录豆包（只需一次）
# 登录后状态保存在 ~/.config/chromium-debug/

# 3. 发送消息给豆包
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/send_message.py "你好，你是谁？"
```

### 前置条件

1. **必须先登录豆包**（在浏览器中手动登录一次，登录状态会保存在 `~/.config/chromium-debug/`）
2. 未登录状态下豆包不会回复消息

### 输出示例

```
📤 发送: 你好，你是谁？
✅ 找到豆包页面
🖊️ 填写消息...
🚀 发送消息...
⏳ 等待豆包回复（最多60秒）...
==================================================
🤖 豆包回复:
你好！我是豆包，是字节跳动公司开发的 AI 智能助手...
==================================================
```

---

## AI 图片生成

通过豆包的 AI 创作功能，使用 Seedream 4.5 模型生成图片。

### 使用方式

```bash
# 启动浏览器（如果还没启动）
bash ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/start.sh

# 生成图片（输出到 ~/.openclaw/workspace/doubao/imgs/）
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_image.py "一只可爱的小柴犬在海边冲浪"
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_image.py "穿着和服的猫娘" ~/.openclaw/workspace/doubao/imgs
```

### 生成流程

1. 打开豆包页面
2. 验证登录状态（未登录则弹出二维码，脚本退出）
3. 点击「AI 创作」进入创作模式
4. 填写提示词
5. 按回车提交生成
6. 等待 30 秒生成完成
7. 提取图片 URL 并下载（4张，384x216，带水印）
8. 保存到指定目录

### 输出示例

```
📁 输出目录: ~/.openclaw/workspace/doubao/imgs
🔧 检查 Chrome...
✅ Chrome 运行中
🌐 打开豆包...
🔐 验证登录状态...
   检测结果: found: 右上角登录按钮, 位置:1121,10
🔐 检测到未登录，开始登录流程...
🖱️ 点击登录按钮...
   找到登录按钮 @e7，点击...
🔍 检查登录弹窗...
   ✅ 检测到二维码登录框
📸 截图保存...
==================================================
⚠️ 未登录，请扫描二维码登陆
📁 截图: ~/.openclaw/workspace/doubao/loginImgs/login_qr_1775197667.png
==================================================

# 下面是已登录时的完整输出：
🔐 验证登录状态...
✅ 登录验证通过
🎨 进入 AI 创作页面...
🔍 找图片描述输入框...
   ✅ 找到 @e43
✍️ 填写: 一只可爱的小柴犬在海边冲浪
🚀 点击生成按钮...
⏳ 等待生成（30秒）...
📥 获取图片...
   第 1 次: 找到 4 张 ✅
   第 1 张... ✅ 162KB
   第 2 张... ✅ 158KB
   第 3 张... ✅ 156KB
   第 4 张... ✅ 164KB

========================================
✅ 完成！保存 4 张 → ~/.openclaw/workspace/doubao/imgs
📝 一只可爱的小柴犬在海边冲浪
========================================
```

### 输出说明

- **图片数量**: 每次生成 4 张
- **图片尺寸**: 384x216（豆包 CDN 默认尺寸）
- **图片格式**: PNG/JPG
- **文件名**: `{提示词前25字}_{序号}_{时间戳}.png`
- **存储位置**: 默认 `~/.openclaw/workspace/doubao/imgs/`

---

## AI 视频分析 + 脚本生成

通过豆包分析抖音等视频链接，自动生成视频脚本。**无需登录豆包**。

### 使用方式

```bash
# 分析视频并生成脚本（保存到 scripts.json）
b ~/.openclaw/workspace/doubao/sheet/scripts/manual/add_script.sh --analyze "https://v.douyin.com/xxx"
```

### 工作流程

1. 启动**全新的** Chrome Debug 浏览器（每次都是新实例）
2. 打开豆包网站
3. 找到输入框，发送视频链接
4. 豆包自动分析视频内容并生成脚本
5. 提取豆包的回复，保存到 `doubao/sheet/scripts/data/scripts.json`

### 输出说明

- **保存位置**: `~/.openclaw/workspace/doubao/sheet/scripts/data/scripts.json`
- **分析内容**: 视频内容、风格、节奏分析 + 可直接拍摄的脚本
- **无需登录**: 豆包支持未登录用户发送消息
- **脚本格式**: JSON（包含 id, title, category, platform, content, tags 等字段）

### 适用场景

当你看到好的抖音视频，想借鉴其脚本时：
1. 复制视频链接
2. 发送给我：`分析这个视频并生成脚本：[链接]`
3. 我自动调用豆包分析，保存脚本到库中

---

## AI 视频生成

通过豆包的「视频生成」功能，使用 Seedance 2.0 Fast 模型生成视频。

### 使用方式

```bash
# 生成视频（输出到 ~/.openclaw/workspace/doubao/videos/）
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_video.py "一只小猫在草地上奔跑"
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_video.py "大熊猫吃竹子" ~/.openclaw/workspace/doubao/videos
```

### 生成流程

1. 打开豆包页面
2. 验证登录状态（未登录则弹出二维码，脚本退出）
3. 点击「AI 创作」进入创作模式
4. 点击「视频」Tab 切换到视频模式
5. 填写视频描述
6. 按回车提交生成
7. 等待 1-3 分钟视频生成完成
8. 自动点击播放获取视频 URL
9. 下载视频到本地（MP4 格式）

### 输出示例

```
📁 输出目录: ~/.openclaw/workspace/doubao/videos
🔧 检查 Chrome...
✅ Chrome 运行中
🌐 打开豆包...
🔐 验证登录状态...
✅ 登录验证通过
🎨 进入 AI 创作页面...
🎬 进入视频生成模式...
   视频tab按钮点击: clicked
   视频输入框 @e34
✍️ 填写: 一只小猫在草地上奔跑
🚀 点击发送按钮...
⏳ 等待视频生成（最多 180 秒）...
   ✅ 视频生成完成，耗时 150 秒
📥 下载视频...
   ✅ 4MB → 一只小猫在草地上奔跑_1775060795.mp4

========================================
✅ 完成！
📁 ~/.openclaw/workspace/doubao/videos/一只小猫在草地上奔跑_1775060795.mp4
📝 一只小猫在草地上奔跑
========================================
```

### 输出说明

- **视频格式**: MP4 (H.264)
- **视频大小**: 通常 3-8MB
- **文件名**: `{提示词前20字}_{时间戳}.mp4`
- **存储位置**: 默认 `~/.openclaw/workspace/doubao/videos/`
- **生成时间**: 1-3 分钟
