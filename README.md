# 社交关系AI管家

> 一个比你更记得住人情世故的AI管家。

让创业者在投资人、合伙人、客户面前，永远像做过功课——而且什么额外的事都不用做。

## 快速开始

```bash
# 添加联系人
python3 social.py add-contact zhangzong --name 张总 --role 投资人 --tags AI赛道 A轮

# 记录互动（自动提取待办）
python3 social.py log zhangzong --summary "TS条款沟通，法务审核中" --type meeting

# 查看待办
python3 social.py todos

# AI拟稿
python3 social.py draft zhangzong --tone 亲切

# 拟稿并发送到微信
python3 social.py send zhangzong --tone 亲切

# 查看所有联系人的最近状态
python3 social.py status

# 查看某个联系人详情
python3 social.py status zhangzong

# 仪表盘
python3 social.py dashboard

# 检查需跟进的关系
python3 social.py check
```

## 命令一览

| 命令 | 说明 |
|:----|:-----|
| `add-contact` | 添加联系人（投资人/合伙人/客户/导师）|
| `log` | 记录互动，自动提取待办 |
| `todos` | 查看待办列表（P0优先）|
| `done` | 完成待办 |
| `draft` | AI拟稿，支持语气调节 |
| `send` | 拟稿并推送到微信 |
| `status` | 查看联系人状态或时间线 |
| `dashboard` | 全局仪表盘 |
| `check` | 检查14天+未联系的关系 |

## 数据

所有数据存储在 `data/` 目录下，JSON格式，本地存储不上云。

| 文件 | 说明 |
|:----|:-----|
| `contacts.json` | 联系人库 |
| `timeline.json` | 互动时间线 |
| `todos.json` | 待办队列 |

## 依赖

- Claude Code（用于AI拟稿）
- Python 3.9+
- 微信推送（可选，需配置 wechat_push.py）
