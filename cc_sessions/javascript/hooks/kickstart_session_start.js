#!/usr/bin/env node

// ===== IMPORTS ===== //

/// ===== STDLIB ===== ///
const fs = require('fs');
const path = require('path');
///-///

/// ===== 3RD-PARTY ===== ///
///-///

/// ===== LOCAL ===== ///
// Import from shared_state (same pattern as normal hooks). Runtime file lives in sessions/hooks
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const { loadState, editState, loadConfig } = require('./shared_state.js');
///-///

//-//

// ===== GLOBALS ===== //

/// ===== CI DETECTION ===== ///
function isCIEnvironment() {
    // Check if running in a CI environment (GitHub Actions)
    const ciIndicators = [
        'GITHUB_ACTIONS',         // GitHub Actions
        'GITHUB_WORKFLOW',        // GitHub Actions workflow
        'CI',                     // Generic CI indicator (set by GitHub Actions)
        'CONTINUOUS_INTEGRATION', // Generic CI (alternative)
    ];
    return ciIndicators.some(indicator => process.env[indicator]);
}

// Skip kickstart session start hook in CI environments
if (isCIEnvironment()) {
    process.exit(0);
}
///-///

/// ===== MODULE SEQUENCES ===== ///
const FULL_MODE_SEQUENCE = [
    '01-discussion.md',
    '02-implementation.md',
    '03-tasks-overview.md',
    '04-task-creation.md',
    '05-task-startup.md',
    '06-task-completion.md',
    '07-compaction.md',
    '08-agents.md',
    '09-api.md',
    '10-advanced.md',
    '11-graduation.md'
];

const SUBAGENTS_MODE_SEQUENCE = [
    '01-agents-only.md'
];
///-///

//-//

// ===== FUNCTIONS ===== //

function loadProtocolFile(relativePath) {
    /**
     * Load protocol markdown from protocols directory.
     */
    const protocolPath = path.join(PROJECT_ROOT, 'sessions', 'protocols', relativePath);
    if (!fs.existsSync(protocolPath)) {
        return `Error: Protocol file not found: ${relativePath}`;
    }
    return fs.readFileSync(protocolPath, 'utf8');
}

//-//

/*
Kickstart SessionStart Hook

Handles onboarding flow for users who chose kickstart in installer:
- Checks for kickstart metadata (should ALWAYS exist if this hook is running)
- Loads first module on first run, resumes from current_index on subsequent runs
- Sequences determined by mode (full or subagents)
*/

// ===== EXECUTION ===== //

//!> 1. Load state and check kickstart metadata
const STATE = loadState();
const CONFIG = loadConfig();

// Early exit if sessions are disabled
if (!CONFIG.features.sessions_enabled) {
    process.exit(0);
}

// Get kickstart metadata (should ALWAYS exist if this hook is running)
const kickstartMeta = STATE.metadata?.kickstart;
if (!kickstartMeta) {
    // This is a BUG - fail loudly
    console.log(JSON.stringify({
        hookSpecificOutput: {
            hookEventName: 'SessionStart',
            additionalContext: 'ERROR: kickstart_session_start hook fired but no kickstart metadata found. This is an installer bug.'
        }
    }));
    process.exit(1);
}

const mode = kickstartMeta.mode;  // 'full' or 'subagents'
if (!mode) {
    console.log(JSON.stringify({
        hookSpecificOutput: {
            hookEventName: 'SessionStart',
            additionalContext: 'ERROR: kickstart metadata exists but no mode specified. This is an installer bug.'
        }
    }));
    process.exit(1);
}
//!<

//!> 2. Output deterministic instructions for Claude to begin kickstart via API
// Detect OS for correct sessions command
const isWindows = process.platform === "win32";
const sessionsCmd = isWindows ? "sessions/bin/sessions.bat" : "sessions/bin/sessions";

const beginCmd = mode === 'subagents' ? `${sessionsCmd} kickstart subagents` : `${sessionsCmd} kickstart full`;
let instructions = `Kickstart onboarding is enabled. Begin immediately by running:\n\n  ${beginCmd}\n\nThen, for each module chunk returned, follow all instructions completely. When finished with a chunk, run:\n\n  ${sessionsCmd} kickstart next\n\nRepeat until kickstart is complete.`;
// Add a clearly delineated user section to guide manual starts
instructions += `\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nUSER INSTRUCTIONS:\nJust say 'kickstart' and press enter to begin\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;

console.log(JSON.stringify({
    hookSpecificOutput: {
        hookEventName: 'SessionStart',
        additionalContext: instructions
    }
}));
process.exit(0);
//!<
