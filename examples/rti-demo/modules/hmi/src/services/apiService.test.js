/*
 * SPDX-FileCopyrightText: 2026 Netbeheer Nederland
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  executeApiCall, getBffLogLevel, getInstanceLogLevel, setBffLogLevel, setInstanceLogLevel,
} from './apiService';

// What executeApiCall posts to the BFF's /api/execute.
let sent;
beforeEach(() => {
  sent = [];
  global.fetch = vi.fn(async (url, init) => {
    sent.push(JSON.parse(init.body));
    return { ok: true, status: 200, text: async () => '{"ok": true, "result": {}}' };
  });
});

describe('executeApiCall', () => {
  it('encodes a path parameter, slashes included', async () => {
    await executeApiCall('plugin-reload', 'fsp:5001', null, { pathParams: { name: 'a/b' } });
    expect(sent[0]).toMatchObject({ method: 'POST', path: '/api/plugins/a%2Fb/reload' });
  });

  it("keeps a plugin route's slashes, encoding each segment, with the caller's method and query", async () => {
    await executeApiCall('plugin-route', 'fsp:5001', { on: true }, {
      pathParams: { name: 'dr_panel', path: 'leds/red led' }, method: 'PUT', query: '?on=1&color=dark red',
    });
    expect(sent[0]).toEqual({
      target: 'fsp:5001', method: 'PUT', path: '/api/plugins/dr_panel/leds/red%20led?on=1&color=dark+red', body: { on: true },
    });
  });

  it("uses the definition's method and no query by default", async () => {
    await executeApiCall('plugin-route', 'fsp:5001', null, { pathParams: { name: 'dr_panel', path: 'leds' } });
    expect(sent[0]).toEqual({ target: 'fsp:5001', method: 'GET', path: '/api/plugins/dr_panel/leds' });
  });
});

describe('log level calls (specs 0010, 0011)', () => {
  const STATE = { level: 'debug', value: 10, source: 'hmi', changed_at: null, start: { level: 'info', value: 20, source: 'default' } };
  const answer = (status, body) => ({ ok: status < 400, status, text: async () => JSON.stringify(body), json: async () => body });

  it('reads and sets an instance\'s level through /api/execute', async () => {
    const calls = [];
    global.fetch = vi.fn(async (url, init) => {
      calls.push({ url, body: JSON.parse(init.body) });
      return answer(200, { ok: true, result: STATE });
    });
    await expect(getInstanceLogLevel('rti-fsp02:5002')).resolves.toEqual(STATE);
    await expect(setInstanceLogLevel('rti-fsp02:5002', 'debug')).resolves.toEqual(STATE);
    await setInstanceLogLevel('rti-fsp02:5002', null);
    expect(calls.map(c => c.url)).toEqual(Array(3).fill('http://localhost:3000/api/execute'));
    expect(calls.map(c => c.body)).toEqual([
      { target: 'rti-fsp02:5002', method: 'GET', path: '/api/log-level' },
      { target: 'rti-fsp02:5002', method: 'PUT', path: '/api/log-level', body: { level: 'debug' } },
      { target: 'rti-fsp02:5002', method: 'PUT', path: '/api/log-level', body: { level: null } },
    ]);
  });

  it("throws with the instance's reason", async () => {
    global.fetch = vi.fn(async () => answer(500, { detail: "422 Client Error - unknown log level 'loud'" }));
    await expect(setInstanceLogLevel('rti-so:5000', 'loud')).rejects.toThrow("unknown log level 'loud'");
    global.fetch = vi.fn(async () => { throw new TypeError('Failed to fetch'); });
    await expect(getInstanceLogLevel('rti-so:5000')).rejects.toThrow('Reading the log level: no answer from the BFF');
  });

  it("reads and sets the BFF's own level on the BFF itself", async () => {
    const calls = [];
    global.fetch = vi.fn(async (url, init = {}) => {
      calls.push({ url, method: init.method || 'GET', body: init.body });
      return answer(200, STATE);
    });
    await expect(getBffLogLevel('http://bff.local:3000')).resolves.toEqual(STATE);
    await expect(setBffLogLevel(null, 'http://bff.local:3000')).resolves.toEqual(STATE);
    expect(calls).toEqual([
      { url: 'http://bff.local:3000/api/log-level', method: 'GET', body: undefined },
      { url: 'http://bff.local:3000/api/log-level', method: 'PUT', body: '{"level":null}' },
    ]);
  });

  it("throws with the BFF's reason, a list included", async () => {
    global.fetch = vi.fn(async () => answer(422, { detail: [{ msg: 'Field required' }] }));
    await expect(setBffLogLevel('x', 'http://bff')).rejects.toThrow('Field required');
    global.fetch = vi.fn(async () => answer(422, { detail: 'unknown log level' }));
    await expect(setBffLogLevel('x', 'http://bff')).rejects.toThrow('unknown log level');
  });
});
