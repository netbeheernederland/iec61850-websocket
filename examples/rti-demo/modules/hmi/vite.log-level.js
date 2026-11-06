// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

/**
 * The HMI's build-time log level (spec 0008).
 *
 * `npm run dev -- --log-level debug` wins over LOG_LEVEL in the environment,
 * as in the FSP, SO and BFF. vite-cli.js (behind `npm run dev` / `build` /
 * `preview`) takes --log-level off the command line before Vite sees it -
 * Vite would read it as its own --logLevel, which has no debug or warning
 * and then hides its errors - and puts it in LOG_LEVEL. vite.config.js puts
 * LOG_LEVEL in VITE_LOG_LEVEL for the bundle (src/utils/log.js); without it,
 * VITE_LOG_LEVEL is as Vite finds it (the environment or an .env file).
 */

const OPTION = '--log-level';

/**
 * Takes --log-level (`--log-level X` or `--log-level=X`, the last one wins)
 * out of the arguments: { level, args }, level undefined when not given.
 * Throws when --log-level has no value.
 */
export function takeLogLevel(args) {
  let level;
  const rest = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === OPTION) {
      if (i + 1 >= args.length) throw new Error(`${OPTION} needs a value, such as ${OPTION} debug`);
      level = args[i + 1];
      i += 1;
    } else if (args[i].startsWith(`${OPTION}=`)) {
      level = args[i].slice(OPTION.length + 1);
    } else {
      rest.push(args[i]);
    }
  }
  return { level, args: rest };
}

/** Whether --log-level is in the arguments (vite run without vite-cli.js). */
export const hasLogLevel = (args) => args.some((arg) => arg === OPTION || arg.startsWith(`${OPTION}=`));

/** The build's level: LOG_LEVEL, undefined when unset or empty. */
export const buildLogLevel = (env) => (env.LOG_LEVEL ? env.LOG_LEVEL : undefined);
