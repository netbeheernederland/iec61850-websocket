// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { LOG_LEVEL_NAMES } from '../utils/log';

// A service's log level while it runs (specs 0010, 0011): the BFF on the
// Settings page, an SO or FSP in Monitoring. The level lives in the service,
// so nothing is kept in the browser.

const START_SOURCE_TEXT = { '--log-level': '--log-level', LOG_LEVEL: 'LOG_LEVEL', default: 'the default' };

const startSourceText = (source) => START_SOURCE_TEXT[source] || source || 'the default';

/** "As started (info, from LOG_LEVEL)", the select's first option. */
export const startOptionLabel = (state) => (state?.start
  ? `As started (${state.start.level}, from ${startSourceText(state.start.source)})`
  : 'As started');

/** "debug, set from the HMI at 14:02" or "info, as started (from LOG_LEVEL)". */
export function describeServiceLogLevel(state) {
  if (!state) return '';
  if (state.source === 'hmi') {
    const at = state.changed_at ? new Date(state.changed_at) : null;
    const time = at && !Number.isNaN(at.getTime())
      ? ` at ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
      : '';
    return `${state.level}, set from the HMI${time}`;
  }
  return `${state.level}, as started (from ${startSourceText(state.start?.source)})`;
}

/**
 * @param {object} props
 * @param {string} props.id - The select's id (its label points at it)
 * @param {string} props.label - The label
 * @param {() => Promise<object>} props.load - Reads the level; throws with the reason
 * @param {(level: string|null) => Promise<object>} props.save - Sets it (null: as started); throws with the reason
 * @param {boolean} [props.disabled] - No service to ask (not connected, none selected)
 * @param {string} [props.disabledText] - Shown instead while disabled
 * @param {string} [props.hint] - A line on what the level is for
 * @param {*} [props.reloadKey] - Read the level again when this changes
 * @param {(message: string) => void} [props.onError] - Also told when a change fails
 */
function LogLevelSelect({ id, label, load, save, disabled = false, disabledText, hint, reloadKey, onError }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // Only the last read counts: switching instances quickly mustn't show the
  // level of the one before.
  const readSeq = useRef(0);

  // keepError: after a failed change, whose reason stays on screen.
  const refresh = useCallback(async ({ keepError = false } = {}) => {
    const mine = ++readSeq.current;
    try {
      const next = await load();
      if (mine === readSeq.current) {
        setState(next);
        if (!keepError) setError('');
      }
    } catch (e) {
      if (mine === readSeq.current) {
        setState(null);
        setError(`Can't read the log level: ${e.message}`);
      }
    }
  }, [load]);

  useEffect(() => {
    if (disabled) {
      readSeq.current += 1;
      setState(null);
      setError('');
      return;
    }
    refresh();
  }, [disabled, refresh, reloadKey]);

  const handleChange = async (e) => {
    const level = e.target.value || null;
    setBusy(true);
    setError('');
    readSeq.current += 1;
    try {
      setState(await save(level));
    } catch (err) {
      setError(err.message);
      onError?.(err.message);
      // Back to what the service uses.
      refresh({ keepError: true });
    } finally {
      setBusy(false);
    }
  };

  const off = disabled || !state;
  const value = state?.source === 'hmi' ? state.level : '';

  return (
    <div className="setting-item log-level-select" style={{ display: 'block' }}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        onChange={handleChange}
        disabled={off || busy}
        style={{ width: '100%', maxWidth: '300px' }}
      >
        <option value="">{startOptionLabel(state)}</option>
        {LOG_LEVEL_NAMES.map(name => (
          <option key={name} value={name}>{name}</option>
        ))}
      </select>
      <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
        {disabled
          ? disabledText
          : state && <>In use: <span id={`${id}-in-use`}>{describeServiceLogLevel(state)}</span>. </>}
        {!disabled && hint}
      </p>
      {error && (
        <p id={`${id}-error`} style={{ color: 'var(--danger-color)', fontSize: '12px', marginTop: '4px' }}>
          {error}
        </p>
      )}
    </div>
  );
}

export default LogLevelSelect;
