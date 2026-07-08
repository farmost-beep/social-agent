#!/usr/bin/env node
/**
 * social-agent / social — CLI 入口（npm 包装层 v3.0）
 *
 * 用法:
 *   npx @farmost/social-agent <args>     # 走 social 命令（v3 统一入口）
 *   social-agent <args>                   # 兼容 v2 入口
 *   social <args>                         # v3 统一入口
 *
 * v3.0 行为变化：
 * - 默认调 social_cli/cli.py（v3 统一入口）
 * - social-agent 子命令调 src/social.py（v2 兼容）
 * - 自动检测哪个 Python 模块可用
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { exit } = require('process');

const python = process.platform === 'win32' ? 'python' : 'python3';
const ROOT = path.join(__dirname, '..');
const args = process.argv.slice(2);

// 判断用哪个入口
// 1. 如果显式调用 `social-agent` bin（通过 npm bin link），走 v2
// 2. 如果调用 `social` bin 或 npx 软链，走 v3
const invokedAs = path.basename(process.argv[1] || '');
const isV2Entry = invokedAs === 'social-agent';

let scriptArgs;
if (isV2Entry) {
  // v2 兼容入口
  scriptArgs = [path.join(ROOT, 'src', 'social.py')];
} else {
  // v3 默认入口：用 `python -m social_cli` 触发包内相对导入
  scriptArgs = ['-m', 'social_cli'];
}

// Fallback：如果 v3 不存在（v2.5.x 旧版包），回退到 v2
if (!isV2Entry) {
  const v3Module = path.join(ROOT, 'social_cli', '__init__.py');
  if (!fs.existsSync(v3Module)) {
    const fallback = path.join(ROOT, 'src', 'social.py');
    if (fs.existsSync(fallback)) {
      scriptArgs = [fallback];
    } else {
      console.error('✗ 找不到 CLI 入口（既无 v3 social_cli/ 也无 v2 src/social.py）');
      console.error('  请重新安装: npm install @farmost/social-agent@latest');
      exit(1);
    }
  }
}

const child = spawn(python, [...scriptArgs, ...args], {
  stdio: 'inherit',
  cwd: ROOT,
  env: { ...process.env, PYTHONPATH: ROOT },
});
child.on('close', (code) => exit(code || 0));
child.on('error', (err) => {
  console.error(`✗ 无法启动 Python: ${err.message}`);
  console.error(`  请确认 Python 3.9+ 已安装: ${python} --version`);
  exit(1);
});