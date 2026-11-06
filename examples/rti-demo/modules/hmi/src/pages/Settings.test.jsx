// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const SETTINGS = { bffHost: 'localhost', bffPort: 3000 };

// log.js reads ?log= when it is imported, so each case imports fresh copies.
const renderSettings = async () => {
  vi.resetModules();
  const { default: Settings } = await import('./Settings');
  const logModule = await import('../utils/log');
  render(<Settings settings={SETTINGS} setSettings={() => {}} />);
  return logModule;
};

const inUse = () => document.getElementById('log-level-in-use').textContent;

beforeEach(() => {
  global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }));
  vi.stubEnv('VITE_LOG_LEVEL', '');
  window.RTI_CONFIG = { logLevel: 'debug' };
});

afterEach(() => {
  delete window.RTI_CONFIG;
  localStorage.clear();
  window.history.replaceState(null, '', '/');
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe('Settings page: log level (spec 0008)', () => {
  it("offers the server's level and the six names", async () => {
    await renderSettings();
    const select = screen.getByLabelText('HMI log level (this browser)');
    expect([...select.options].map(o => o.textContent)).toEqual([
      'From the server (debug)', 'critical', 'error', 'warning', 'info', 'debug', 'trace',
    ]);
    expect(select).toHaveValue('');
    expect(inUse()).toBe('debug (from LOG_LEVEL)');
  });

  it('stores a choice and applies it without a reload', async () => {
    const user = userEvent.setup({ delay: null });
    const { log } = await renderSettings();
    const debug = vi.spyOn(console, 'debug').mockImplementation(() => {});

    await user.selectOptions(screen.getByLabelText('HMI log level (this browser)'), 'error');

    expect(localStorage.getItem('rti-hmi-log-level')).toBe('error');
    expect(inUse()).toBe('error (from the Settings page)');
    log.debug('hidden');
    expect(debug).not.toHaveBeenCalled();
  });

  it('clears the choice with "From the server"', async () => {
    localStorage.setItem('rti-hmi-log-level', 'error');
    const user = userEvent.setup({ delay: null });
    await renderSettings();
    expect(screen.getByLabelText('HMI log level (this browser)')).toHaveValue('error');

    await user.selectOptions(screen.getByLabelText('HMI log level (this browser)'), '');

    expect(localStorage.getItem('rti-hmi-log-level')).toBeNull();
    expect(inUse()).toBe('debug (from LOG_LEVEL)');
  });

  it('says when ?log= in the URL is in use', async () => {
    window.history.replaceState(null, '', '/settings?log=warning');
    await renderSettings();
    expect(inUse()).toBe('warning (from ?log=)');
    expect(screen.getByText(/\?log=warning in the URL wins over this choice/)).toBeInTheDocument();
  });
});

describe("Settings page: the BFF's log level (spec 0010)", () => {
  const STATE = {
    level: 'info', value: 20, source: 'start', changed_at: null,
    start: { level: 'info', value: 20, source: 'LOG_LEVEL' },
  };

  const bff = ({ health = true } = {}) => {
    const puts = [];
    global.fetch = vi.fn(async (url, init = {}) => {
      if (String(url).endsWith('/api/health')) {
        if (!health) throw new TypeError('Failed to fetch');
        return { ok: true, status: 200, json: async () => ({ ok: true }) };
      }
      if (String(url).endsWith('/api/log-level')) {
        if (init.method === 'PUT') {
          const { level } = JSON.parse(init.body);
          puts.push({ url, level });
          const next = level ? { ...STATE, level, value: 10, source: 'hmi', changed_at: '2026-11-03T14:02:00Z' } : STATE;
          return { ok: true, status: 200, json: async () => next };
        }
        return { ok: true, status: 200, json: async () => STATE };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });
    return puts;
  };

  it('reads the level after the connection check and sets it on the BFF that was checked', async () => {
    const puts = bff();
    await renderSettings();
    const select = screen.getByLabelText('BFF log level');
    await waitFor(() => expect(select).toBeEnabled(), { timeout: 2000 });
    expect(select.options[0].textContent).toBe('As started (info, from LOG_LEVEL)');
    expect(document.getElementById('bff-log-level-in-use').textContent).toBe('info, as started (from LOG_LEVEL)');

    await userEvent.selectOptions(select, 'debug');
    await waitFor(() => expect(select).toHaveValue('debug'));
    expect(puts).toEqual([{ url: 'http://localhost:3000/api/log-level', level: 'debug' }]);
    expect(localStorage.getItem('rti-hmi-log-level')).toBeNull();
  });

  it('is disabled while the BFF is not connected', async () => {
    bff({ health: false });
    await renderSettings();
    await screen.findByText('Connection failed', {}, { timeout: 2000 });
    expect(screen.getByLabelText('BFF log level')).toBeDisabled();
    expect(screen.getByText('Connect to the BFF to see its log level.')).toBeInTheDocument();
  });
});
