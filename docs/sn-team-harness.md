# SenseNova Team Harness

English | [简体中文](sn-team-harness_cn.md)

[`sn-team-harness`](../skills/sn-team-harness/SKILL.md) introduces a self-hosted workspace
where people and local Agents share context, projects, work items, resources, and versioned
artifacts. It is a collaboration framework, not just a chat interface and not a replacement
for the Agent runtime itself.

## Core concepts

| Concept | Meaning |
|---|---|
| Workspace | The shared source of truth for collaboration. |
| Project | A collection of work, discussions, and deliverables around one goal. |
| Conversation | A discussion where members can mention Agents or create work items. |
| Agent | An AI team member bound to a local runtime. |
| WorkItem | A task with an owner, status, and expected result. |
| Resource | Input material uploaded to a project. |
| Artifact | A versioned, reviewable output produced by an Agent. |
| Local Computer | The local client that runs the Agent and keeps credentials and files on the member's computer. |

## Self-hosted quick start

The current project is source-based and does not provide a Docker image, npm package, or
production deployment layer. Requirements are Node.js 24 and npm.

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills-TeamHarness.git
cd SenseNova-Skills-TeamHarness
cp .env.example .env
npm ci
npm run dev
```

Open `http://localhost:5173`. For a local production run:

```bash
npm run build
NODE_ENV=production npm start
```

## Basic flow

1. Create a Workspace and invite members with a revocable Join Link.
2. Create a Project and Agent, then bind the Agent to an online Local Computer runtime.
3. Mention the Agent in a Conversation or create a WorkItem; upload inputs as Resources.
4. Let the Local Computer run the Agent and publish messages or Artifacts.
5. Review progress, ownership, blockers, and Artifact history in the workspace.
6. Resolve concurrent writes through the held-draft retry, discard, or force flow.

## Security boundaries

This is an early self-hosted project and is not a production security boundary by itself.
Before exposing it to a network, add authentication, TLS, secret rotation, backups,
monitoring, rate limiting, and a threat-model review. Do not commit `.env`, tokens, SQLite
files, local workspaces, or logs.
