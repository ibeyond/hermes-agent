# Hermes Agent 使用说明 (中文)

## 项目概述

Hermes Agent 是由 Nous Research 开发的自改进 AI 代理。它能:
- 通过经验创建技能
- 使用中自动改进技能
- 支持 Telegram、Discord、Slack、WhatsApp 等 30+ 消息平台
- 内置 FTS5 跨会话记忆搜索
- 支持多种 LLM 后端(OpenAI、Anthropic、Gemini 等)

## 安装

### 1. 准备 Python 虚拟环境

使用 `uv` (推荐):
```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境
cd hermes-agent
uv venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
uv pip install -e .
```

### 2. 配置 HERMES_HOME

设置配置和数据的存储位置:

```bash
# 添加到 ~/.bashrc
echo 'export HERMES_HOME=/home/ibeyond/hermes-agent' >> ~/.bashrc
source ~/.bashrc
```

或者临时使用:
```bash
export HERMES_HOME=/home/ibeyond/hermes-agent
```

### 3. 初始化配置

```bash
hermes setup
```

## 基本使用

### 启动交互式 CLI

```bash
hermes chat
```

或使用 Python 直接调用:
```bash
cd hermes-agent
source .venv/bin/activate
export HERMES_HOME=/home/ibeyond/hermes-agent
python3 -m hermes_cli.main
```

### 启动消息网关 (Gateway)

网关允许通过 Telegram、Discord 等平台与 Hermes 交互。

#### 前台运行 (开发测试)
```bash
hermes gateway run
```

#### 详细日志模式
```bash
hermes gateway run -v     # INFO 级别
hermes gateway run -vv    # DEBUG 级别
```

#### 后台 systemd 服务 (生产)
```bash
# 安装为系统服务
hermes gateway install

# 启动/停止/重启
hermes gateway start
hermes gateway stop
hermes gateway restart

# 查看状态
hermes gateway status
```

### 配置消息平台

```bash
hermes gateway setup
```

支持的平台:
- Telegram
- Discord
- Slack
- WhatsApp
- Signal
- Matrix
- Mattermost
- Email
- SMS
- 钉钉
- 企业微信
- 微信
- 飞书
- 等等...

## 记忆系统

### 使用内置记忆工具

Hermes 提供 `memory` 工具来管理持久化记忆:

- `MEMORY.md` - Agent 的个人笔记
- `USER.md` - 关于用户的了解

### 集成 OpenViking 记忆

OpenViking 是字节跳动开源的上下文数据库,提供文件系统式知识管理。

#### 配置

在 `~/.hermes/.env` 添加:
```bash
OPENVIKING_ENDPOINT=http://127.0.0.1:1933
OPENVIKING_API_KEY=your_api_key  # 可选
OPENVIKING_ACCOUNT=default
OPENVIKING_USER=default
OPENVIKING_AGENT=hermes
```

#### 配置为默认记忆提供者

```bash
hermes config set memory.provider openviking
```

#### OpenViking 工具

| 工具 | 用途 |
|------|------|
| `viking_search` | 语义搜索 |
| `viking_read` | 读取内容 (L0/L1/L2) |
| `viking_browse` | 浏览目录 |
| `viking_remember` | 存储记忆 |
| `viking_add_resource` | 添加资源 |
| `viking_delete` | 删除资源 |

#### 路径结构

```
viking://
├── user/{user}/agent/{agent}/
│   └── memories/
│       ├── preferences/    # 用户偏好
│       ├── entities/       # 实体
│       ├── events/         # 事件
│       ├── cases/          # 案例
│       └── patterns/       # 模式
└── resources/
```

## 常用命令

### 模型管理
```bash
hermes model                  # 选择默认模型
hermes fallback list          # 查看备用模型
hermes config                 # 查看配置
```

### 技能管理
```bash
hermes skills                 # 列出技能
hermes skills install <name>  # 安装技能
```

### 插件管理
```bash
hermes plugins                # 列出插件
hermes memory                 # 记忆设置
```

### 会话管理
```bash
hermes sessions list          # 列出会话
hermes chat --resume <id>     # 恢复会话
```

### 定时任务
```bash
hermes cron list              # 列出定时任务
hermes cron add <expression>  # 添加任务
```

### 工具管理
```bash
hermes tools                  # 工具配置 UI
hermes mcp                    # MCP 服务器管理
```

## 配置位置

| 项目 | 位置 |
|------|------|
| 配置文件 | `$HERMES_HOME/config.yaml` |
| API keys | `$HERMES_HOME/.env` |
| 日志 | `$HERMES_HOME/logs/` |
| 会话 | `$HERMES_HOME/sessions.db` |
| 记忆 | `$HERMES_HOME/memories/` |
| 技能 | `$HERMES_HOME/skills/` |
| 插件 | `$HERMES_HOME/plugins/` |

## 环境变量

| 变量 | 说明 |
|------|------|
| `HERMES_NO_BROWSER=1` | 禁用 OAuth 流程中的自动浏览器打开。URL 仍会打印到终端，用户可手动打开。 |
| `HERMES_HOME` | 配置和数据存储位置 |
| `DISPLAY` / `WAYLAND_DISPLAY` | 图形浏览器检测（Linux 系统） |
| `BROWSER` | 指定浏览器程序 |

## 多 Profile 支持

Hermes 支持多个完全隔离的实例:

```bash
hermes -p coder config list   # coder profile
hermes -p personal chat       # personal profile
```

## 故障排除

### 重置配置
```bash
rm -rf $HERMES_HOME/*
hermes setup
```

### 查看日志
```bash
hermes logs --follow           # 实时跟踪
hermes logs --level ERROR      # 只看错误
hermes logs --session <id>     # 特定会话
```

### 健康检查
```bash
hermes doctor
```

### 系统诊断
```bash
hermes status
hermes security
```

## 开发

### 运行测试
```bash
bash scripts/run_tests.sh
```

### 创建功能分支
```bash
git checkout develop
git checkout -b feature/my-feature
```

### 提交 PR
```bash
git push origin feature/my-feature
# 在 GitHub 上创建 PR: feature/my-feature → develop
```

## 文档资源

- 官方文档: https://hermes-agent.nousresearch.com/docs/
- GitHub: https://github.com/NousResearch/hermes-agent
- Discord: https://discord.gg/NousResearch

## 许可

MIT License
