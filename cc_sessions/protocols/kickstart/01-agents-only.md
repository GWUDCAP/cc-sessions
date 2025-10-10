# Kickstart: Agent Customization (Subagents-Only Mode)

## Agent Instructions

Introduce all subagents, explain which benefit from customization, and guide through code-review customization with threat profile discussion. This is a streamlined setup for users who want to customize their agents without going through the full tutorial.

---

SAY TO THE USER >>>

Welcome! You've chosen to customize your cc-sessions subagents.

CC-sessions includes five specialized subagents that handle different aspects of your workflow:
- **context-gathering** (literally the goat) - Researches external APIs, frameworks, and services
- **context-refinement** (the kid) - Updates task context with discoveries from your work
- **logging** (necessary) - Consolidates work logs during task completion
- **service-documentation** (he's alright) - Updates CLAUDE.md and module docs
- **code-review** (annoying prick also necessary) - Reviews code for bugs, security, and quality

You can customize all of these agents, but:
- **code-review** you should definitely customize based on the codebase you're in and styles/conventions/languages/threat profile/etc.
- **service-documentation** benefits from any specific documentation patterns you may have (but you can skip it if you dgaf)

**Would you like to customize code-review?**

<<<

## If user says yes:

SAY TO THE USER >>>

Cool. I'm going to call the context-gathering agent to analyze your codebase and give me recommendations for customizing the code-review agent.

<<<

Call the context-gathering agent with this prompt:
```
Analyze this codebase and provide code-review agent customization recommendations. Focus on:

1. Primary languages and frameworks
2. Code style conventions (formatting, naming, patterns)
3. Common vulnerability patterns relevant to this stack
4. Testing patterns and quality standards
5. Any architectural patterns or design principles evident in the code

**IMPORTANT: Do not write to any files. Return your findings directly in your response to me.**
```

After agent returns, continue with threat profile discussion.

---

SAY TO THE USER >>>

Alright, now I need to understand the threat profile for this codebase.

**Who uses this codebase and how do they use it?**

For example:
- Is this internal tooling just for your team?
- Is it a public-facing service with untrusted users?
- Is it a library that other developers will use?
- Is it a CLI tool that users run locally on their own machines?

<<<

Wait for user response. Based on their answer and the context-gathering recommendations, explain how you'll customize the code-review agent (language/framework focus, style conventions, threat model calibration, etc.).

Ask for confirmation that the approach sounds good.

Once confirmed, apply the customizations to `.claude/agents/code-review.md`.

---

SAY TO THE USER >>>

Code-review agent customized.

**Would you like to customize any of the other agents?**
- context-gathering
- context-refinement
- logging
- service-documentation

<<<

## If user wants to customize others:

Guide them through similar process for each agent they want to customize.

## When user is done with customization:

SAY TO THE USER >>>

Perfect! Your cc-sessions subagents are now customized for your codebase.

You're all set up and ready to start using cc-sessions. The kickstart metadata has been cleared, so you won't see this setup process again.

**Quick reminder of key commands:**
- `mek: <task-name>` - Create a new task
- `start^: @<task-name>` - Start working on a task
- `finito` - Complete current task
- `squish` - Compact context when needed
- `/sessions` - Manage state, config, and tasks

Happy coding! 🚀

<<<

Clear the kickstart metadata to mark setup as complete.

---
