// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LogLevelSelect, { describeServiceLogLevel, startOptionLabel } from './LogLevelSelect';

const AS_STARTED = {
  level: 'info', value: 20, source: 'start', changed_at: null,
  start: { level: 'info', value: 20, source: 'LOG_LEVEL' },
};
const SET_DEBUG = { ...AS_STARTED, level: 'debug', value: 10, source: 'hmi', changed_at: '2026-11-03T14:02:11Z' };

const renderSelect = (props = {}) => {
  const load = props.load || vi.fn(async () => AS_STARTED);
  const save = props.save || vi.fn(async () => SET_DEBUG);
  const view = render(
    <LogLevelSelect id="lvl" label="Log level" load={load} save={save} disabledText="Not connected." {...props} />
  );
  return { load, save, ...view };
};

const select = () => screen.getByLabelText('Log level');

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('describeServiceLogLevel and startOptionLabel', () => {
  it('says where the start level came from', () => {
    expect(startOptionLabel(AS_STARTED)).toBe('As started (info, from LOG_LEVEL)');
    expect(startOptionLabel({ ...AS_STARTED, start: { level: 'warning', source: '--log-level' } }))
      .toBe('As started (warning, from --log-level)');
    expect(startOptionLabel({ ...AS_STARTED, start: { level: 'info', source: 'default' } }))
      .toBe('As started (info, from the default)');
    expect(startOptionLabel(null)).toBe('As started');
  });

  it('says when the HMI changed it', () => {
    expect(describeServiceLogLevel(AS_STARTED)).toBe('info, as started (from LOG_LEVEL)');
    expect(describeServiceLogLevel(SET_DEBUG)).toMatch(/^debug, set from the HMI at \d{1,2}[:.]\d{2}/);
    expect(describeServiceLogLevel({ ...SET_DEBUG, changed_at: null })).toBe('debug, set from the HMI');
  });
});

describe('LogLevelSelect (specs 0010, 0011)', () => {
  it('reads the level and offers "As started" and the six names', async () => {
    renderSelect();
    await waitFor(() => expect(select()).toBeEnabled());
    expect([...select().options].map(o => o.textContent)).toEqual([
      'As started (info, from LOG_LEVEL)', 'critical', 'error', 'warning', 'info', 'debug', 'trace',
    ]);
    expect(select()).toHaveValue('');
    expect(document.getElementById('lvl-in-use').textContent).toBe('info, as started (from LOG_LEVEL)');
  });

  it('shows a level set from the HMI as chosen', async () => {
    renderSelect({ load: vi.fn(async () => SET_DEBUG) });
    await waitFor(() => expect(select()).toHaveValue('debug'));
  });

  it('sends a change straight away and shows the answer', async () => {
    const { save } = renderSelect();
    await waitFor(() => expect(select()).toBeEnabled());
    await userEvent.selectOptions(select(), 'debug');
    expect(save).toHaveBeenCalledWith('debug');
    await waitFor(() => expect(select()).toHaveValue('debug'));
    expect(document.getElementById('lvl-in-use').textContent).toMatch(/^debug, set from the HMI/);
  });

  it('sends null for "As started"', async () => {
    const save = vi.fn(async () => AS_STARTED);
    renderSelect({ load: vi.fn(async () => SET_DEBUG), save });
    await waitFor(() => expect(select()).toHaveValue('debug'));
    await userEvent.selectOptions(select(), '');
    expect(save).toHaveBeenCalledWith(null);
    await waitFor(() => expect(select()).toHaveValue(''));
  });

  it('goes back to the service\'s level and shows the reason when a change fails', async () => {
    const onError = vi.fn();
    const load = vi.fn(async () => AS_STARTED);
    const save = vi.fn(async () => { throw new Error('422 - unknown log level'); });
    renderSelect({ load, save, onError });
    await waitFor(() => expect(select()).toBeEnabled());
    await userEvent.selectOptions(select(), 'error');
    await waitFor(() => expect(document.getElementById('lvl-error')).toHaveTextContent('422 - unknown log level'));
    expect(onError).toHaveBeenCalledWith('422 - unknown log level');
    expect(load).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(select()).toHaveValue(''));
  });

  it('is disabled, and asks nothing, while there is no service', () => {
    const { load } = renderSelect({ disabled: true });
    expect(select()).toBeDisabled();
    expect(screen.getByText('Not connected.')).toBeInTheDocument();
    expect(load).not.toHaveBeenCalled();
  });

  it('is disabled when the level can\'t be read, and says why', async () => {
    renderSelect({ load: vi.fn(async () => { throw new Error('no answer from the BFF'); }) });
    await waitFor(() => expect(document.getElementById('lvl-error'))
      .toHaveTextContent("Can't read the log level: no answer from the BFF"));
    expect(select()).toBeDisabled();
  });

  it('reads again when the reload key changes, e.g. another instance', async () => {
    const load = vi.fn(async () => AS_STARTED);
    const { rerender, save } = renderSelect({ load, reloadKey: 'fsp01:5001' });
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
    const loadOther = vi.fn(async () => SET_DEBUG);
    rerender(<LogLevelSelect id="lvl" label="Log level" load={loadOther} save={save} reloadKey="fsp02:5002" />);
    await waitFor(() => expect(select()).toHaveValue('debug'));
    expect(loadOther).toHaveBeenCalledTimes(1);
  });

  it('keeps only the last read when two overlap', async () => {
    let resolveFirst;
    const first = vi.fn(() => new Promise((resolve) => { resolveFirst = resolve; }));
    const { rerender, save } = renderSelect({ load: first, reloadKey: 'a' });
    rerender(<LogLevelSelect id="lvl" label="Log level" load={vi.fn(async () => SET_DEBUG)} save={save} reloadKey="b" />);
    await waitFor(() => expect(select()).toHaveValue('debug'));
    resolveFirst(AS_STARTED);
    await new Promise((r) => setTimeout(r, 0));
    expect(select()).toHaveValue('debug');
  });

  it('keeps nothing in localStorage', async () => {
    renderSelect();
    await waitFor(() => expect(select()).toBeEnabled());
    await userEvent.selectOptions(select(), 'debug');
    await waitFor(() => expect(select()).toHaveValue('debug'));
    expect(localStorage.length).toBe(0);
  });
});
