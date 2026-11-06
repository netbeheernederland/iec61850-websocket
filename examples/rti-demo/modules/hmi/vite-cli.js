#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Netbeheer Nederland
//
// SPDX-License-Identifier: Apache-2.0

/**
 * Runs Vite for `npm run dev` / `build` / `preview`, with the HMI's
 * --log-level (spec 0008) taken off the command line: it wins over
 * LOG_LEVEL, so it becomes LOG_LEVEL, which vite.config.js bakes into the
 * bundle. Vite never sees --log-level, so its own --logLevel and its error
 * messages stay as they are. See vite.log-level.js.
 */

import { fileURLToPath } from 'node:url';
import { takeLogLevel } from './vite.log-level.js';

let taken;
try {
  taken = takeLogLevel(process.argv.slice(2));
} catch (e) {
  console.error(`vite-cli.js: ${e.message}`);
  process.exit(2);
}

if (taken.level !== undefined) process.env.LOG_LEVEL = taken.level;

// Vite's bin reads process.argv when it is imported.
const viteBin = new URL('bin/vite.js', import.meta.resolve('vite/package.json'));
process.argv = [process.argv[0], fileURLToPath(viteBin), ...taken.args];
await import(viteBin.href);
