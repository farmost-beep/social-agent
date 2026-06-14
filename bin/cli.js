#!/usr/bin/env node
/**
 * social-agent — CLI 入口（npm 包装层）
 * 用法: npx social-agent <args>
 *       social-agent <args>   (全局安装后)
 */
const { spawn } = require('child_process');
const path = require('path');
const { exit } = require('process');

const python = process.platform === 'win32' ? 'python' : 'python3';
const script = path.join(__dirname, '..', 'src', 'social.py');
const args = process.argv.slice(2);

const child = spawn(python, [script, ...args], { stdio: 'inherit' });

child.on('close', (code) => exit(code));
