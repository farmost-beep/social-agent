"""社交关系AI管家 - 安装脚本"""
from setuptools import setup, find_packages

setup(
    name="social-agent",
    version="2.3.0",
    description="社交关系AI管家 - 自动追踪社交关系，帮你拟消息、记待办、维护人脉",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Contributors",
    url="https://github.com/farmost-beep/social-agent",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "pyyaml>=6.0",
    ],
    extras_require={
        "web": ["flask>=2.0"],
    },
    entry_points={
        "console_scripts": [
            "social-agent=src.cli:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
    ],
)
