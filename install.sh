#!/usr/bin/env bash
#
# social-agent — 一键安装脚本
# 用法: bash <(curl -sL https://raw.githubusercontent.com/farmost-beep/social-agent/main/install.sh)
#   或: curl -sL https://raw.githubusercontent.com/farmost-beep/social-agent/main/install.sh | bash
#   或: ./install.sh

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}::${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

REPO="https://github.com/farmost-beep/social-agent.git"
SKILLS_DIR="${HOME}/.claude/skills"
TARGET="${SKILLS_DIR}/social-agent"

# ── 检查前置条件 ──────────────────────────────────────────────
info "检查前置条件..."

PY_VER=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "0")
if [ "$(echo "$PY_VER >= 3.9" | bc 2>/dev/null)" != "1" ]; then
  fail "需要 Python 3.9+，当前: $(python3 --version 2>/dev/null || echo '未安装')"
fi
ok "Python ${PY_VER}"

if ! command -v git &>/dev/null; then
  fail "需要 git，请先安装: brew install git / apt install git / 等"
fi
ok "git 已安装"

# ── 克隆/更新 ─────────────────────────────────────────────────
if [ -d "${TARGET}/.git" ]; then
  info "检测到已有安装，正在更新..."
  cd "${TARGET}"
  git pull --ff-only origin main
  ok "更新到最新版本"
else
  info "正在克隆仓库..."
  mkdir -p "${SKILLS_DIR}"
  git clone --depth 1 "${REPO}" "${TARGET}"
  ok "克隆完成"
fi

cd "${TARGET}"

# ── 安装 Python 依赖 ──────────────────────────────────────────
info "安装 Python 依赖..."
pip3 install -r requirements.txt --quiet 2>/dev/null
pip3 install -e . --quiet 2>/dev/null
ok "依赖安装完成"

# ── 初始化数据 ────────────────────────────────────────────────
if [ ! -f "data/contacts.json" ]; then
  info "初始化空数据..."
  cp -r data_template/* data/
  ok "数据初始化完成（空模板）"
else
  ok "数据目录已存在，跳过初始化"
fi

# ── 验证 ──────────────────────────────────────────────────────
info "验证安装..."
if python3 -c "from src.engine import *; print('引擎加载OK')" 2>/dev/null; then
  ok "引擎加载正常"
else
  warn "引擎加载异常，请检查依赖: pip3 install -r requirements.txt"
fi

DASHBOARD=$(python3 src/social.py dashboard 2>/dev/null | head -3)
if [ -n "$DASHBOARD" ]; then
  ok "CLI 可用"
else
  warn "CLI 测试未通过，可忽略（首次运行需先导入联系人）"
fi

# ── 总结 ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  social-agent 安装/更新完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${CYAN}📂${NC} 位置: ${TARGET}"
echo -e "  ${CYAN}⚡${NC} 在 Claude Code 中输入 ${YELLOW}/social-agent${NC} 即可使用"
echo ""
echo -e "  ${YELLOW}快速开始:${NC}"
echo -e "    cd ${TARGET}"
echo -e "    python3 src/social.py add-contact <ID> --name '姓名' --role '角色'"
echo -e "    python3 src/social.py dashboard"
echo ""
echo -e "  ${YELLOW}文档:${NC}"
echo -e "    README.md      — 使用说明"
echo -e "    docs/SPEC.md   — 设计规约"
echo ""
echo -e "  ${YELLOW}更新:${NC}"
echo -e "    重新运行本脚本即可"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
