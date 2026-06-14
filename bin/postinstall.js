#!/usr/bin/env node
/**
 * social-agent — npm postinstall 脚本
 * 自动安装 Python 依赖并初始化数据目录
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const python = process.platform === 'win32' ? 'python' : 'python3';

function run(cmd, opts = {}) {
  try {
    execSync(cmd, { cwd: ROOT, stdio: 'inherit', ...opts });
    return true;
  } catch {
    return false;
  }
}

console.log('\n:: social-agent 安装中...\n');

// 1. 检查 Python
try {
  const ver = execSync(`${python} --version`, { cwd: ROOT }).toString().trim();
  console.log(`✓ ${ver}`);
} catch {
  console.warn('⚠ 未检测到 Python 3，请先安装: https://www.python.org/downloads/');
}

// 2. 安装 Python 依赖
console.log('\n:: 安装 Python 依赖...');
run(`pip3 install -r requirements.txt -q`) || run(`pip install -r requirements.txt -q`);
console.log('✓ 依赖安装完成');

// 3. 初始化数据目录
const dataDir = path.join(ROOT, 'data');
const templateDir = path.join(ROOT, 'data_template');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}
if (fs.existsSync(templateDir)) {
  const files = fs.readdirSync(templateDir);
  for (const f of files) {
    const dest = path.join(dataDir, f);
    if (!fs.existsSync(dest)) {
      fs.copyFileSync(path.join(templateDir, f), dest);
    }
  }
  if (files.length) console.log('✓ 数据初始化完成');
}

// 4. 验证
try {
  execSync(`${python} -c "from src.engine import *; print('✓ 引擎加载正常')"`, { cwd: ROOT });
} catch {
  console.warn('⚠ 引擎验证未通过，尝试: pip3 install -r requirements.txt');
}

console.log('\n✓ social-agent 安装完成！');
console.log(`  运行: npx social-agent dashboard\n`);
