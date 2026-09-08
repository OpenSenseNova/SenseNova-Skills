---
name: sn-team-harness
description: >-
  Use when a user asks what SenseNova Team Harness is, wants an introduction or
  overview, is getting started, or is deciding whether it fits — a self-hosted
  workspace where people and local AI agents collaborate on conversations,
  projects, work items, and artifacts. Covers its core concepts (Workspace,
  Project, Conversation, Agent, WorkItem, Resource, Artifact, Local Computer),
  main capabilities, how to run it, and the basic usage flow.
---

# SenseNova Team Harness

SenseNova Team Harness 是一个**自托管的团队协作工作区**，让人和本地 AI Agent 围绕
同一份工作协同：讨论、待办、AI 执行和最终成果都放在同一个空间里。它把
「提出问题 → 分配工作 → 持续推进 → 交付成果」连成一条完整、可审计的协作链，
让 AI 真正作为团队成员参与，而不是把回答留在个人聊天窗口里。

## 核心概念

| 概念 | 说明 |
| --- | --- |
| **Workspace** | 团队共享空间，是共享协作事实的唯一权威来源。 |
| **Project** | 一个目标下的任务、讨论和交付物的集合。 |
| **Conversation** | 团队讨论；可以在其中 @Agent 或创建待办。 |
| **Agent** | 作为团队成员参与的 AI，绑定一台本地 Runtime 执行工作。 |
| **WorkItem** | 一项待办工作，有负责人、状态和预期结果。 |
| **Resource** | 人为 Project 上传的输入文件（数据、素材等），是 Agent 工作的原料，区别于 Artifact。 |
| **Artifact** | Agent 产出的成果（报告、代码、方案等），独立于聊天，内容寻址、可版本化、可审核。 |
| **Local Computer** | 连接服务并在成员自己电脑上运行 Agent 的本地客户端；凭据、文件和工作目录都留在本地。 |

## 主要能力

- **AI 进入团队日常**：Agent 参与讨论、接受工作、回复问题，而非只属于某个人的聊天窗口。
- **一句话变成一项工作**：在讨论中 @Agent 或创建 WorkItem，明确负责人和预期结果。
- **本地执行、数据留本地**：Agent 在成员自己电脑上运行，读取 Project Resources、本地文件和工具；凭据和敏感数据不出本机。
- **过程与成果可审计**：任务状态、负责人、评论和阻塞可见；成果作为 Artifact 独立保存，可更新、下载、引用和复核。
- **中断可恢复、多 AI 协作**：离线或并发冲突时未发布结果会被保留；不同 Agent 可分担研究、写作、编程、审阅等。

## 适用场景

研究与分析、产品与运营、软件研发、内容与设计、知识与流程管理，以及多人多 AI
围绕同一目标分工、由人在关键节点验收的跨角色项目。

## 快速开始（自托管）

环境要求：Node.js 24 和 npm。服务端从源码运行，不提供 Docker 镜像和 npm 包。

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills-TeamHarness.git
cd SenseNova-Skills-TeamHarness
cp .env.example .env
npm ci
npm run dev
```

浏览器打开 `http://localhost:5173`。生产模式本地运行用 `npm run build` 后
`NODE_ENV=production npm start`。

## 基本使用流程

1. 创建 **Workspace**，通过可撤销的 Join Link 邀请成员。
2. 创建 **Project** 和 **Agent**，为 Agent 绑定一台已上线的 **Local Computer** Runtime。
3. 在 **Conversation** 中 `@Agent`，或创建 **WorkItem** 指派负责人；把输入文件作为 **Resource** 上传到 Project。
4. Local Computer 在本地运行 Agent；Agent 读取讨论上下文和 Resource，用消息回复或发布 / 更新 **Artifact**。
5. 团队在任务看板和 Artifact 版本历史中查看进展、负责人和最终成果。
6. 并发写入冲突时，候选结果保留为本地 Held Draft，Agent 读取最新版本后显式 retry / discard / force。

## 边界与注意事项

- 早期自托管项目，本身不是生产安全边界。对公网开放前请自行补充身份系统、TLS、
  密钥轮换、备份、监控、限流和威胁模型评审。
- 不提供生产部署方案、Docker 镜像、原生安装器、npm 包或数据库迁移层。
- 不要把 `.env`、token、SQLite 文件、本地工作目录或日志提交到代码仓库。

## 延伸阅读

仓库内有更完整说明：`README.md` / `README_CN.md`（功能与使用）、`INSTALL.md`（安装配置）、
`local-computer/README.md`（Local Computer 与 teamctl 命令，含 `resource` / `artifact` / `message`）、
`docs/contracts/openapi.json`（HTTP 契约）。
