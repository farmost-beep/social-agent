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

// 3. 初始化数据目录（安全模式）
// ⚠ 绝不覆盖已有数据文件 — 即使目标为空也不替换
const dataDir = path.join(ROOT, 'data');
const templateDir = path.join(ROOT, 'data_template');
const protectedFiles = ['contacts.json', 'timeline.json', 'todos.json', 'wechat_ids.json'];

if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}
if (fs.existsSync(templateDir)) {
  // 先检查是否已有非空数据文件，有则跳过全部初始化
  let hasData = false;
  for (const f of protectedFiles) {
    const dest = path.join(dataDir, f);
    try {
      const stat = fs.statSync(dest);
      if (stat.size > 2) { hasData = true; break; } // >2字节 = 非空([]为2字节)
    } catch { /* 文件不存在，可安全创建 */ }
  }
  if (hasData) {
    console.log('✓ 检测到已有数据，跳过初始化');
  } else {
    const files = fs.readdirSync(templateDir);
    let copied = 0;
    for (const f of files) {
      const dest = path.join(dataDir, f);
      if (protectedFiles.includes(f)) {
        // 保护文件：仅当目标不存在或为空（<=2字节）才写入
        try {
          const stat = fs.statSync(dest);
          if (stat.size > 2) continue; // 非空，不动
        } catch { /* 不存在，创建 */ }
      } else {
        // 非保护文件：不存在才写入
        try { fs.statSync(dest); continue; } catch {}
      }
      fs.copyFileSync(path.join(templateDir, f), dest);
      copied++;
    }
    if (copied) console.log(`✓ 数据初始化完成（${copied}个文件）`);
  }
}

// 4. 验证
try {
  execSync(`${python} -c "from src.engine import *; print('✓ 引擎加载正常')"`, { cwd: ROOT });
} catch {
  console.warn('⚠ 引擎验证未通过，尝试: pip3 install -r requirements.txt');
}

console.log('\n✓ social-agent 安装完成！');
console.log(`  运行: npx social-agent dashboard\n`);
