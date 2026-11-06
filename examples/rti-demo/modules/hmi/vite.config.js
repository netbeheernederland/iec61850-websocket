/*
 * SPDX-FileCopyrightText: 2025-2026 Netbeheer Nederland
 * SPDX-License-Identifier: Apache-2.0
 *
 * Copyright 2025-2026 Netbeheer Nederland
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { buildLogLevel, hasLogLevel } from './vite.log-level.js'

// --log-level reaches here only when vite runs without vite-cli.js. Vite
// then takes it as its own --logLevel, which hides its errors - so stop,
// on stderr, as Vite's logger would print nothing.
if (hasLogLevel(process.argv)) {
  process.stderr.write(
    'vite.config.js: --log-level is the HMI\'s log level; use npm run dev / npm run build -- --log-level <level>, ' +
      'or LOG_LEVEL=<level> (spec 0008)\n'
  )
  process.exit(2)
}

// The HMI's log level (spec 0008): LOG_LEVEL (which vite-cli.js sets from
// --log-level) becomes VITE_LOG_LEVEL, which Vite reads from the
// environment after this file.
const hmiLogLevel = buildLogLevel(process.env)
if (hmiLogLevel !== undefined) {
  process.env.VITE_LOG_LEVEL = hmiLogLevel
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8080,
    open: true
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
    globals: true
  }
})
