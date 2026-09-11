# SenseNova Team Harness

简体中文 | [English](sn-team-harness.md)

[`sn-team-harness`](../skills/sn-team-harness/SKILL.md) 介绍一个自托管协作工作区，让人和本地
Agent 共享上下文、项目、工作项、资源与版本化成果。它是团队协作框架，不只是聊天界面，
也不是 Agent runtime 的替代品。

## 核心概念

| 概念 | 说明 |
|---|---|
| Workspace | 团队协作的共享事实源。 |
| Project | 围绕一个目标组织的任务、讨论和交付物集合。 |
| Conversation | 成员可以在其中 @Agent 或创建工作项的讨论。 |
| Agent | 绑定本地 runtime、作为团队成员参与工作的 AI。 |
| WorkItem | 有负责人、状态和预期结果的一项待办。 |
| Resource | 上传到项目的输入材料。 |
| Artifact | Agent 产出的、可版本化和可审核的成果。 |
| Local Computer | 在成员电脑上运行 Agent、并在本地保留凭据和文件的客户端。 |

## 自托管快速开始

当前项目以源码方式运行，不提供 Docker 镜像、npm 包或生产部署层。环境要求为 Node.js 24
和 npm。

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills-TeamHarness.git
cd SenseNova-Skills-TeamHarness
cp .env.example .env
npm ci
npm run dev
```

浏览器打开 `http://localhost:5173`。本地生产模式运行：

```bash
npm run build
NODE_ENV=production npm start
```

## 基本流程

1. 创建 Workspace，并通过可撤销的 Join Link 邀请成员。
2. 创建 Project 和 Agent，将 Agent 绑定到已上线的 Local Computer runtime。
3. 在 Conversation 中 @Agent 或创建 WorkItem，把输入文件作为 Resource 上传。
4. 由 Local Computer 在本地运行 Agent，发布消息或 Artifact。
5. 在工作区查看进度、负责人、阻塞原因和 Artifact 版本历史。
6. 出现并发写入冲突时，通过 held-draft 的 retry、discard 或 force 流程处理。

## 安全边界

这是早期自托管项目，本身不是生产安全边界。对外开放前需要自行补充身份认证、TLS、密钥
轮换、备份、监控、限流和威胁模型评审。不要提交 `.env`、token、SQLite 文件、本地工作区
或日志。
