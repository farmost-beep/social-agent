"""social_cli - Social-CLI v3.0 统一入口

从 Claude Code 内部 skill 升级为独立 CLI 工具。

特点：
- 标准 argparse 子命令（status/todos/enrich/health/draft/config/chat）
- 可通过 `pip install -e .` 安装为系统命令 `social`
- 兼容现有 src/ 包，不破坏数据格式
- 底层使用 LLM 抽象层（v3.0 升级）
"""
__version__ = "4.0.2"