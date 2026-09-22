#!/usr/bin/env node
import {
  createCipheriv,
  createDecipheriv,
  createHash,
  pbkdf2Sync,
  randomBytes,
} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {basename} from 'node:path';

const FORMAT = 'cn.guanxiang.liuyao.rules-package';
const AAD = Buffer.from('liuyao-rules-package-v1', 'utf8');
const ITERATIONS = 310_000;
const MAX_WORKBOOK_BYTES = 5_000_000;

function fail(message) {
  process.stderr.write(message + '\n');
  process.exit(1);
}

function password() {
  const value = process.env.LIUYAO_RULE_PASSWORD_FILE
    ? readFileSync(process.env.LIUYAO_RULE_PASSWORD_FILE, 'utf8').trim()
    : (process.env.LIUYAO_RULE_PASSWORD || '');
  if (value.length < 12 || value.length > 256) {
    fail('请通过 LIUYAO_RULE_PASSWORD_FILE 或 LIUYAO_RULE_PASSWORD 提供 12–256 位规则包口令。');
  }
  return value;
}

function workbook(path) {
  const raw = readFileSync(path);
  if (raw.length < 4 || raw.length > MAX_WORKBOOK_BYTES ||
      raw[0] !== 0x50 || raw[1] !== 0x4b || raw[2] !== 0x03 || raw[3] !== 0x04) {
    fail('输入必须是小于 5 MB 的有效 XLSX 文件。');
  }
  return raw;
}

function decode(value, label) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) {
    fail(label + '格式无效。');
  }
  return Buffer.from(value, 'base64');
}

function encrypt(input, output) {
  const plain = workbook(input);
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = pbkdf2Sync(password(), salt, ITERATIONS, 32, 'sha256');
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(AAD);
  const encrypted = Buffer.concat([cipher.update(plain), cipher.final(), cipher.getAuthTag()]);
  const pack = {
    format: FORMAT,
    version: 1,
    kdf: {name: 'PBKDF2-HMAC-SHA-256', iterations: ITERATIONS, salt: salt.toString('base64')},
    cipher: {name: 'AES-256-GCM', iv: iv.toString('base64'), tag_length: 128},
    payload: {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      name: basename(input),
      bytes: plain.length,
      sha256: createHash('sha256').update(plain).digest('hex'),
    },
    ciphertext: encrypted.toString('base64'),
  };
  writeFileSync(output, JSON.stringify(pack, null, 2) + '\n', {flag: 'wx', mode: 0o600});
  process.stdout.write(JSON.stringify({output, payload_bytes: plain.length, sha256: pack.payload.sha256}) + '\n');
}

function decrypt(input, output) {
  let pack;
  try { pack = JSON.parse(readFileSync(input, 'utf8')); }
  catch (_) { fail('无法读取 .lyrules 文件。'); }
  if (pack?.format !== FORMAT || pack.version !== 1 ||
      pack.kdf?.name !== 'PBKDF2-HMAC-SHA-256' ||
      !Number.isInteger(pack.kdf.iterations) || pack.kdf.iterations < 100_000 || pack.kdf.iterations > 2_000_000 ||
      pack.cipher?.name !== 'AES-256-GCM' || pack.cipher.tag_length !== 128) {
    fail('规则包格式或版本不受支持。');
  }
  const salt = decode(pack.kdf.salt, '盐值');
  const iv = decode(pack.cipher.iv, '随机向量');
  const sealed = decode(pack.ciphertext, '密文');
  if (salt.length < 16 || salt.length > 64 || iv.length !== 12 || sealed.length < 17) fail('规则包长度无效。');
  const key = pbkdf2Sync(password(), salt, pack.kdf.iterations, 32, 'sha256');
  const tag = sealed.subarray(sealed.length - 16);
  const cipherText = sealed.subarray(0, sealed.length - 16);
  let plain;
  try {
    const decipher = createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAAD(AAD);
    decipher.setAuthTag(tag);
    plain = Buffer.concat([decipher.update(cipherText), decipher.final()]);
  } catch (_) { fail('规则包口令不正确，或文件已经损坏。'); }
  const digest = createHash('sha256').update(plain).digest('hex');
  if (plain.length > MAX_WORKBOOK_BYTES || digest !== pack.payload?.sha256) fail('规则包摘要不匹配。');
  writeFileSync(output, plain, {flag: 'wx', mode: 0o600});
  process.stdout.write(JSON.stringify({output, payload_bytes: plain.length, sha256: digest}) + '\n');
}

function generatePassword(output) {
  const value = randomBytes(24).toString('base64url');
  writeFileSync(output, value + '\n', {flag: 'wx', mode: 0o600});
  process.stdout.write(JSON.stringify({output, characters: value.length}) + '\n');
}

const [operation, input, output] = process.argv.slice(2);
if (operation === 'password' && input && !output) generatePassword(input);
else if (operation === 'encrypt' && input && output) encrypt(input, output);
else if (operation === 'decrypt' && input && output) decrypt(input, output);
else fail('用法：node tools/rule-package.mjs password 口令文件；或通过 LIUYAO_RULE_PASSWORD_FILE / LIUYAO_RULE_PASSWORD 执行 encrypt|decrypt 输入文件 输出文件');
