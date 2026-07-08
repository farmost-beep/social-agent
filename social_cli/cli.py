"""social_cli CLI 入口 - Social-CLI v3.0

统一入口，支持以下子命令：
- status     联系人状态总览
- todos      待办列表
- enrich     批量画像补全（v2.5 规划）
- health     关系健康分（v2.5 规划）
- draft      AI拟稿
- config     配置管理
- chat       与AI对话
- version    版本信息

设计原则：
- argparse 标准库，零新依赖
- 各子命令独立函数，便于单测
- 错误返回字符串，不抛异常（与 ai.py 一致）
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# 包内相对导入
from . import __version__

# ── 项目根定位 ──
# 全局 `social` 命令启动时 cwd 不一定是项目根，需要主动定位
# 否则 `from src.social import ...` 会 ImportError

_PROJECT_ROOT: Optional[Path] = None


def _find_project_root() -> Optional[Path]:
    """定位 social-agent 项目根目录

    优先级：
    1. 环境变量 SOCIAL_AGENT_HOME
    2. 向上 5 层找含 config/ 的目录
    3. 向上 5 层找含 data/contacts.json 的目录
    4. 当前工作目录（兜底）
    """
    # 1. 环境变量
    env = os.environ.get("SOCIAL_AGENT_HOME")
    if env and (Path(env) / "config").is_dir():
        return Path(env)

    # 2/3. 从社会_cli 包位置向上找
    # social_cli 在 .../social-agent/social_cli/，向上 1 层就是项目根
    pkg_parent = Path(__file__).resolve().parent.parent
    if (pkg_parent / "config").is_dir():
        return pkg_parent

    # 从 cwd 向上找
    cwd = Path.cwd()
    p = cwd
    for _ in range(5):
        if (p / "config").is_dir() and (p / "src").is_dir():
            return p
        if (p / "data" / "contacts.json").exists():
            return p
        p = p.parent
        if p == p.parent:
            break

    return None


def _ensure_project_path() -> Optional[Path]:
    """确保 social-agent 项目根和 src/ 在 sys.path 中，返回项目根或 None

    src/social.py 使用 `from engine import *` 风格（不带 src. 前缀），
    所以需要把 src/ 目录加到 sys.path，而不是项目根。
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    root = _find_project_root()
    if root is None:
        return None

    # 1. 把 src/ 目录加到 sys.path（让 `from engine import *` 工作）
    src_dir = root / "src"
    if src_dir.is_dir():
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)

    # 2. 同时把项目根加进去（让 `from src.llm import ...` 工作）
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    # 3. 切换 cwd 到项目根（让 engine.py 的默认 data_dir=./data 解析正确）
    if Path.cwd() != root:
        os.chdir(root)

    _PROJECT_ROOT = root
    return root


# 启动时自动定位
_ensure_project_path()


# ── 子命令实现 ──
# v3.0 最小版：先实现"读取类"和"配置类"命令
# 写入类命令（enrich等）暂时转发到旧 src/ 实现

def cmd_status(args) -> int:
    """联系人状态总览。v3.0 先转发到旧实现。"""
    root = _ensure_project_path()
    if root is None:
        print("✗ 找不到 social-agent 项目根，请设置 SOCIAL_AGENT_HOME 环境变量")
        return 1
    try:
        from src.social import cmd_dashboard  # type: ignore
        return cmd_dashboard(args)
    except ImportError as e:
        print(f"✗ 无法加载 src.social: {e}")
        print(f"  当前项目根: {root}")
        return 1


def cmd_todos(args) -> int:
    """查看待办列表。v3.0 直接调 engine.list_todos()

    默认显示 pending 状态
    --all       : 显示全部（含 completed）
    --completed : 只显示已完成
    --recent N  : 显示最近 N 天内创建/完成的
    """
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from engine import list_todos, _load, TODOS_FILE
    except ImportError as e:
        print(f"✗ 无法加载 engine: {e}")
        return 1

    # 决定状态过滤
    if args.completed:
        status_filter = "completed"
        title = "✅ 已完成"
    elif args.all:
        status_filter = None  # 不过滤
        title = "📋 全部待办"
    else:
        status_filter = "pending"
        title = "📋 待办列表"

    # 取数据
    if args.all:
        todos = _load(TODOS_FILE)  # 全部
    else:
        todos = list_todos(status=status_filter)

    # 按 created 倒序（最新的在前）
    todos = sorted(todos, key=lambda t: t.get("created", ""), reverse=True)

    # 近期过滤
    if args.recent:
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=args.recent)).isoformat()
        todos = [t for t in todos if t.get("created", "") >= cutoff]

    if not todos:
        print(f"✓ {title}：无")
        return 0

    print(f"\n{title}（共 {len(todos)} 项）\n")
    today = __import__('datetime').date.today().isoformat()
    for i, t in enumerate(todos, 1):
        priority = t.get("priority", "P2")
        contact = t.get("contact", "—")
        task = t.get("task", "")[:55]
        due = t.get("due", "")
        status = t.get("status", "pending")
        created = t.get("created", "")[:10]

        # 状态图标
        if status == "completed":
            status_icon = "✅"
        elif due and due < today:
            status_icon = "⚠️"
        else:
            status_icon = "  "

        # 优先级图标
        pri_icon = "🔴" if priority == "P0" else ("🟡" if priority == "P1" else "  ")

        due_str = f" (到期 {due})" if due else ""
        new_str = f" 🆕" if created == today else ""
        print(f"  {status_icon}{pri_icon} {i:2d}. [{contact}]{due_str} {task}{new_str}")
    return 0


def cmd_enrich(args) -> int:
    """批量画像补全。v3.0 转发到旧实现。"""
    root = _ensure_project_path()
    if root is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from src.social import cmd_enrich  # type: ignore
        return cmd_enrich(args)
    except ImportError as e:
        print(f"✗ 无法加载 src.social: {e}")
        return 1


def cmd_health(args) -> int:
    """关系健康分。v3.0 暂未实现，提示用户。"""
    print("⚠ health 命令尚未在 v3.0 实现，请用 v2.5 的 src/social.py health")
    return 1


def cmd_draft(args) -> int:
    """AI拟稿。v3.0 使用新 LLM 抽象层。"""
    if not args.message:
        print("✗ 请提供要拟稿的提示（-m）或联系人名")
        return 1

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        # 动态导入 src.ai（兼容旧数据）
        from src.ai import draft_message  # type: ignore
        result = draft_message(
            contact_name=args.contact or "未知",
            context_summary=args.message,
            tone=args.tone,
        )
        print(result)
        return 0
    except ImportError as e:
        print(f"✗ 无法加载 src.ai: {e}")
        return 1


def cmd_config(args) -> int:
    """配置管理：查看/设置 LLM provider。"""
    if not args.action:
        # 无子命令时显示 help（与其他子命令行为一致）
        print("用法: social config {show,providers,set}")
        print()
        print("  show       显示当前 LLM 配置")
        print("  providers  列出可用 LLM providers")
        print("  set        设置配置（提示用环境变量）")
        print()
        print("试试: social config show")
        return 0

    if args.action == "show":
        return _config_show()
    elif args.action == "set":
        return _config_set(args.key, args.value)
    elif args.action == "providers":
        return _config_providers()
    return 1


def _config_show() -> int:
    """显示当前 LLM 配置"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from src.llm import list_providers
    except ImportError as e:
        print(f"✗ 无法加载 src.llm: {e}")
        return 1

    providers = list_providers()
    print(f"可用 providers: {', '.join(providers)}")
    print(f"当前默认: claude")
    print()
    print("环境变量:")
    import os
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_BASE_URL", "LLM_ENGINE"]:
        val = os.environ.get(var, "(未设置)")
        print(f"  {var} = {val[:20]}{'...' if len(val) > 20 else ''}")
    return 0


def _config_set(key: Optional[str], value: Optional[str]) -> int:
    """设置配置项（提示用户用环境变量）"""
    print("⚠ v3.0 配置通过环境变量管理：")
    print()
    print("切换 LLM provider:")
    print("  export LLM_ENGINE=openai   # 或 claude")
    print()
    print("设置 API Key:")
    print("  export ANTHROPIC_API_KEY=sk-ant-...")
    print("  export OPENAI_API_KEY=sk-...")
    print()
    print("自定义 base_url（用于代理/MiniMax等）:")
    print("  export ANTHROPIC_BASE_URL=https://proxy.example.com")
    print("  export OPENAI_BASE_URL=https://api.MiniMax.cn/v1")
    return 0


def _config_providers() -> int:
    """列出所有可用 provider"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from src.llm import list_providers
    except ImportError as e:
        print(f"✗ 无法加载 src.llm: {e}")
        return 1
    print("可用 LLM providers:")
    for p in list_providers():
        print(f"  - {p}")
    return 0


def cmd_chat(args) -> int:
    """与AI对话（直接调用 LLM）"""
    if not args.message:
        print("✗ 请提供消息内容")
        return 1

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        from src.llm import get_client
        client = get_client()
        system = "你是社交关系AI助手。"
        result = client.complete(args.message, system=system)
        print(result)
        return 0
    except Exception as e:
        print(f"✗ 调用失败: {e}")
        return 1


def cmd_version(args) -> int:
    """显示版本"""
    print(f"social-cli {__version__}")
    print(f"Python {sys.version.split()[0]}")
    print(f"路径: {Path(__file__).resolve().parent}")
    return 0


# ── argparse 框架 ──

def build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器"""
    parser = argparse.ArgumentParser(
        prog="social",
        description="社交关系AI管家 - Social-CLI v3.0",
        epilog="更多信息请查看 docs/SPEC.md",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # status
    p_status = subparsers.add_parser("status", help="联系人状态总览")

    # todos
    p_todos = subparsers.add_parser("todos", help="查看待办列表")
    p_todos.add_argument("--all", action="store_true", help="显示全部（含已完成）")
    p_todos.add_argument("--completed", action="store_true", help="只看已完成")
    p_todos.add_argument("--recent", type=int, metavar="N", help="只看最近 N 天创建")

    # enrich
    p_enrich = subparsers.add_parser("enrich", help="批量画像补全")
    p_enrich.add_argument("--batch", type=int, default=10, help="批次大小")
    p_enrich.add_argument("--dry-run", action="store_true", help="预览模式")
    p_enrich.add_argument("--force", action="store_true", help="重新处理")
    p_enrich.add_argument("--stats", action="store_true", help="只看统计")
    p_enrich.add_argument("--web", action="store_true", help="启用网络搜索")

    # health
    p_health = subparsers.add_parser("health", help="关系健康分")
    p_health.add_argument("contact", nargs="?", help="联系人（可选）")
    p_health.add_argument("--fix", action="store_true", help="只看需关注的")
    p_health.add_argument("--ranking", action="store_true", help="排行榜")

    # draft
    p_draft = subparsers.add_parser("draft", help="AI拟稿")
    p_draft.add_argument("-m", "--message", required=True, help="上下文摘要")
    p_draft.add_argument("-c", "--contact", help="联系人名称")
    p_draft.add_argument(
        "--tone", choices=["亲切", "正式", "简洁"],
        help="语气（默认从配置读取）"
    )

    # config
    p_config = subparsers.add_parser("config", help="配置管理")
    config_sub = p_config.add_subparsers(dest="action", help="操作")
    config_sub.add_parser("show", help="显示当前配置")
    config_sub.add_parser("providers", help="列出可用 providers")
    p_set = config_sub.add_parser("set", help="设置配置（提示用环境变量）")
    p_set.add_argument("key", nargs="?", help="配置键")
    p_set.add_argument("value", nargs="?", help="配置值")

    # chat
    p_chat = subparsers.add_parser("chat", help="与AI对话")
    p_chat.add_argument("message", help="消息内容")

    # version
    subparsers.add_parser("version", help="显示版本")

    return parser


# ── 主入口 ──

# 命令 → 处理函数的映射
_COMMANDS = {
    "status": cmd_status,
    "todos": cmd_todos,
    "enrich": cmd_enrich,
    "health": cmd_health,
    "draft": cmd_draft,
    "config": cmd_config,
    "chat": cmd_chat,
    "version": cmd_version,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 主入口

    Args:
        argv: 命令行参数（None 时用 sys.argv[1:]）

    Returns:
        退出码（0=成功，非0=失败）
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # 无子命令时显示帮助
    if not args.command:
        parser.print_help()
        return 0

    # 分发到对应处理函数
    handler = _COMMANDS.get(args.command)
    if handler is None:
        print(f"✗ 未知命令: {args.command}")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n⚠ 用户中断")
        return 130
    except Exception as e:
        print(f"✗ 异常: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())