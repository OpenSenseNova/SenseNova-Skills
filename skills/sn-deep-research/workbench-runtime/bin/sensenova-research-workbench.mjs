#!/usr/bin/env node
process.env.WORKBENCH_PRODUCT = process.env.WORKBENCH_PRODUCT || 'research'
await import('./sensenova-ppt-workbench.mjs')
