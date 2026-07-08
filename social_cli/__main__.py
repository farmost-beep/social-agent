"""social_cli __main__ 入口

支持 `python -m social_cli` 调用
"""
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())