---
name: lei-doubao-browser
description: 豆包浏览器自动化 - 通过 Chrome Debug 模式 + agent-browser 实现 AI 像真人一样操控浏览器，继承已有登录状态，支持抖音、微博、豆包等需要登录的站点，以及 AI 图片和视频生成功能。
version: 1.2.0
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
    ├── start.sh          # 启动 Chrome Debug 浏览器
    ├── generate_image.py # AI 图片生成脚本
    └── generate_video.py # AI 视频生成脚本
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

## AI 图片生成

通过豆包的 AI 创作功能，使用 Seedream 4.5 模型生成图片。

### 使用方式

```bash
# 启动浏览器（如果还没启动）
bash ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/start.sh

# 生成图片（输出到 ~/doubao/imgs/）
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_image.py "一只可爱的小柴犬在海边冲浪"
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_image.py "穿着和服的猫娘" ~/doubao/imgs
```

### 生成流程

1. 自动打开豆包页面
2. 点击「AI 创作」进入创作模式
3. 填写提示词
4. 按回车提交生成
5. 等待 30 秒生成完成
6. 提取图片 URL 并下载（4张，384x216，带水印）
7. 保存到指定目录

### 输出示例

```
📁 输出目录: /home/lei/doubao/imgs
🔧 检查 Chrome...
✅ Chrome 运行中
🌐 打开豆包...
🎨 进入 AI 创作...
   clicked
🔍 找图片描述输入框...
   ✅ 找到 @e43
✍️ 填写: 一只可爱的小柴犬在海边冲浪
🚀 提交...
⏳ 等待生成（30秒）...
📥 获取图片...
   第 1 次: 找到 4 张 ✅
   第 1 张... ✅ 162KB
   第 2 张... ✅ 158KB
   第 3 张... ✅ 156KB
   第 4 张... ✅ 164KB

========================================
✅ 完成！保存 4 张 → /home/lei/doubao/imgs
📝 一只可爱的小柴犬在海边冲浪
========================================
```

### 输出说明

- **图片数量**: 每次生成 4 张
- **图片尺寸**: 384x216（豆包 CDN 默认尺寸）
- **图片格式**: PNG/JPG
- **文件名**: `{提示词前25字}_{序号}_{时间戳}.png`
- **存储位置**: 默认 `~/doubao/imgs/`

---

## AI 视频生成

通过豆包的「视频生成」功能，使用 Seedance 2.0 Fast 模型生成视频。

### 使用方式

```bash
# 生成视频（输出到 ~/doubao/videos/）
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_video.py "一只小猫在草地上奔跑"
python3 ~/.openclaw/workspace/skills/lei-doubao-browser/scripts/generate_video.py "大熊猫吃竹子" ~/doubao/videos
```

### 生成流程

1. 自动打开豆包页面
2. 点击「视频生成」按钮
3. 填写视频描述
4. 按回车提交生成
5. 等待 1-3 分钟视频生成完成
6. 自动点击播放获取视频 URL
7. 下载视频到本地（MP4 格式）

### 输出示例

```
📁 输出目录: /home/lei/doubao/videos
🔧 检查 Chrome...
✅ Chrome 运行中
🌐 打开豆包...
🎬 进入视频生成模式...
   clicked
   视频输入框 @e34
✍️ 填写: 一只小猫在草地上奔跑
🚀 提交生成...
⏳ 等待视频生成（最多 180 秒）...
   ✅ 视频生成完成，耗时 150 秒
📥 下载视频...
   ✅ 4MB → 一只小猫在草地上奔跑_1775060795.mp4

========================================
✅ 完成！
📁 /home/lei/doubao/videos/一只小猫在草地上奔跑_1775060795.mp4
📝 一只小猫在草地上奔跑
========================================
```

### 输出说明

- **视频格式**: MP4 (H.264)
- **视频大小**: 通常 3-8MB
- **文件名**: `{提示词前20字}_{时间戳}.mp4`
- **存储位置**: 默认 `~/doubao/videos/`
- **生成时间**: 1-3 分钟
