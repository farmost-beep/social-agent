"""社交关系AI管家 - 安装脚本

v3.0 升级：
- 保留原 social-agent 命令（v2 兼容）
- 新增 social 命令（v3 social_cli）
- 同时维护两个入口，平滑过渡
"""
from setuptools import setup, find_packages

setup(
    name="social-agent",
    version="3.0.0",
    description="社交关系AI管家 - 自动追踪社交关系，帮你拟消息、记待办、维护人脉",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Contributors",
    url="https://github.com/farmost-beep/social-agent",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "pyyaml>=6.0",
        "httpx>=0.24",  # v3.0 LLM 抽象层需要
    ],
    extras_require={
        "web": ["flask>=2.0"],
    },
    entry_points={
        "console_scripts": [
            # v2 命令（保留兼容）
            "social-agent=src.social:main",
            # v3 新命令（统一入口）
            "social=social_cli.cli:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
)