"""社交关系AI管家 - 安装脚本"""
from setuptools import setup, find_packages

setup(
    name="social-relationship-manager",
    version="2.3.0",
    description="社交关系AI管家 - 自动追踪社交关系，帮你拟消息、记待办、维护人脉",
    long_description=open("docs/README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Contributors",
    url="https://github.com/your-org/social-relationship-manager",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "pyyaml>=6.0",
        "easyocr>=1.7",
    ],
    extras_require={
        "web": ["flask>=2.0"],
        "pdf": ["reportlab>=4.0", "markdown>=3.0"],
    },
    entry_points={
        "console_scripts": [
            "srm=src.cli:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
    ],
)
