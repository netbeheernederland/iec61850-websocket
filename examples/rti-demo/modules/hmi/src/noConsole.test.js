// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

// Spec 0008: every console call goes through utils/log.js, so LOG_LEVEL
// decides what the browser shows.
const sources = import.meta.glob(['./**/*.{js,jsx}', '!./**/*.test.{js,jsx}', '!./utils/log.js', '!./setupTests.js'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

// `console` used in code, not only called: a member (console.error,
// console?.warn, console['log'], window.console.log - also as a value, as in
// .catch(console.error)), or console itself as a value (= console,
// (console), [console], { c: console }). "the browser console." in a text
// is not: no name right after the dot, nothing that takes a value before it.
const CONSOLE_USE = /\bconsole\s*(?:\?\.|\.(?=[\w$])|\[)|[=(,:[]\s*console\b/;

describe('the console pattern', () => {
  it.each([
    "console.error('x')",
    '.catch(console.error)',
    'promise.then(null, console.warn)',
    'const log = console.log;',
    'const { error } = console;',
    'const c = console;',
    'report(console)',
    'console?.debug(x)',
    "console['log'](x)",
    'window.console.info(x)',
    'globalThis.console.error(x)',
    '[console]',
    '{ out: console }',
  ])('finds %s', (line) => {
    expect(CONSOLE_USE.test(line)).toBe(true);
  });

  it.each([
    "alert('Failed to save connection. Check console for details.');",
    'What the HMI logs in the browser console. Applies straight away',
    'log.error(x)',
    'consoleOutput.push(x)',
    'myconsole.log(x)',
  ])('leaves %s', (line) => {
    expect(CONSOLE_USE.test(line)).toBe(false);
  });
});

describe('src/', () => {
  it('has sources to check', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20);
  });

  it('uses the console only in utils/log.js', () => {
    const uses = Object.entries(sources).flatMap(([path, text]) =>
      text.split('\n').flatMap((line, i) => (CONSOLE_USE.test(line) ? [`${path}:${i + 1}: ${line.trim()}`] : []))
    );
    expect(uses).toEqual([]);
  });
});
