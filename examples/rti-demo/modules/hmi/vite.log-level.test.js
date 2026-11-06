// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

import { spawnSync } from 'node:child_process';
import { describe, expect, it } from 'vitest';
import { buildLogLevel, hasLogLevel, takeLogLevel } from './vite.log-level.js';

// This file's directory (import.meta.url is not a file: URL under jsdom).
const here = import.meta.dirname;

describe('the build-time log level', () => {
  it('takes --log-level off the command line, in either form', () => {
    expect(takeLogLevel(['--log-level', 'debug'])).toEqual({ level: 'debug', args: [] });
    expect(takeLogLevel(['build', '--log-level=warning', '--logLevel', 'warn'])).toEqual({
      level: 'warning',
      args: ['build', '--logLevel', 'warn'],
    });
    expect(takeLogLevel(['build'])).toEqual({ level: undefined, args: ['build'] });
  });

  it('takes the last --log-level', () => {
    expect(takeLogLevel(['--log-level', 'debug', '--log-level=error']).level).toBe('error');
  });

  it('refuses --log-level without a value', () => {
    expect(() => takeLogLevel(['build', '--log-level'])).toThrow(/needs a value/);
  });

  it('finds --log-level left for Vite', () => {
    expect(hasLogLevel(['node', 'vite', '--log-level', 'debug'])).toBe(true);
    expect(hasLogLevel(['node', 'vite', '--log-level=debug'])).toBe(true);
    expect(hasLogLevel(['node', 'vite', '--logLevel', 'warn'])).toBe(false);
  });

  it('takes LOG_LEVEL, and nothing when it is unset or empty', () => {
    expect(buildLogLevel({ LOG_LEVEL: 'debug' })).toBe('debug');
    expect(buildLogLevel({ LOG_LEVEL: '' })).toBeUndefined();
    expect(buildLogLevel({})).toBeUndefined();
  });
});

describe('vite-cli.js', () => {
  const run = (...args) =>
    spawnSync(process.execPath, ['vite-cli.js', ...args], { cwd: here, encoding: 'utf8', timeout: 60000 });

  // Vite read --log-level as its own --logLevel, and with debug or warning
  // it printed none of its errors.
  it("keeps Vite's error messages with --log-level", () => {
    const result = run('build', '--log-level', 'debug', '--config', 'does-not-exist.js');
    expect(result.status).not.toBe(0);
    expect(result.stdout + result.stderr).toMatch(/failed to load config/);
  });

  it('refuses --log-level without a value', () => {
    const result = run('build', '--log-level');
    expect(result.status).toBe(2);
    expect(result.stderr).toMatch(/--log-level needs a value/);
  });
});
