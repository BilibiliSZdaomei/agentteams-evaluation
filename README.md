# AgentTeams 计划与物流协作评测

在新电脑上安装 AgentTeams 原版，准备一支「计划与物流协作」团队。计划员、物流员和管理员使用你首次设置的同一个评测密码。登录工作台后选 **我的团队 → 计划与物流协作**，即可在群内 @ 两名 Agent。

**[打开本机评测团队](http://localhost:18966/dashboard/#workbench/teams)**

在不能直接拉取镜像的公司电脑上，先按 [离线依赖](OFFLINE.md) 导入五个镜像，再运行启动脚本。

在已有业务的 Ubuntu 服务器上试用，请按 [Linux 服务器部署与堡垒机访问](LINUX.md) 上传、启动并打开工作台。

## 第一次启动

1. 使用 x86_64 的 Windows 10/11（WSL2 Ubuntu + Docker Desktop 的 Linux 容器）或 Linux。Windows 请让 Ubuntu 成为默认 WSL 发行版，在 Docker Desktop 的 **Settings → Resources → WSL Integration** 启用该 Ubuntu；确认 Ubuntu 里能运行 `docker info`、`python3 --version`、`openssl version`、`curl --version` 和 `bash --version`。Linux 需要相同的命令及可通过本地 Unix socket 使用的 Docker Engine。Python 3.8 或更高版本。
2. 下载并解压本仓。在 Windows 双击 **Start.cmd**，在 Linux 或 WSL 进入仓库后运行 **`bash start.sh`**。初次启动需要输入新密码及公司允许使用的 DeepSeek Key；终端隐藏输入字符。准备一把 Key 即可，计划员和物流员也能分别使用独立的 Key。
3. 等终端显示“已验证团队 Active”。Windows 将打开上述网址。浏览器用户名直接填 `planning`、`logistics` 或 `admin`，输入首次设置的密码。对照两个账号时，可以同时使用 Chrome 普通窗口和无痕窗口，分别登录后进入同一团队。

默认仅发布在本机回环地址，网页和 Manager 控制台分别使用 TCP 18966、18969。请确保 Docker 能拉取杭州 Higress 公共镜像仓库和 Docker Hub 的镜像；如已导入 Release 中的离线镜像，启动器会复用本地匹配版本。Agent 发出模型请求需要能访问 `https://api.deepseek.com`。登录、建团队和基础检查本身不发送模型提示词。

| 账号 | 角色及可试内容 |
| --- | --- |
| `planning` | 团队管理员，在群里 @planning-agent 发送「订单需要 36 箱，已备 17 箱，还差多少？」 |
| `logistics` | 团队成员，在同一群里 @logistics-agent 发送「19 箱，每车最多装 8 箱，需要几辆？」 |
| `admin` | 全局管理员，同时也是团队成员，可进入同一群及管理控制台 |

发消息时在编辑框输入 `@`，再从候选人列表选中 Agent。两次人工交接可分别检查答案 19 箱、3 辆，以及两位组员能否看到彼此的提问和回复。

## 模型与版本

默认采用 DeepSeek 接口模型 ID `deepseek-flash`。初始部署创建 `eval-planning`、`eval-logistics`、`eval-shared` 三个 DeepSeek 提供方，个人 Worker 分别绑定前两条，Manager 使用公共线路。两名 Worker 使用 **deepseek-harness**，Manager 的软件运行时为 **qwenpaw**，模型请求交给配置的 DeepSeek 提供方。账号开通的模型 ID 有差异时，可在首次启动前设置 `TEAM_MODEL`。

| 组件 | 使用版本 |
| --- | --- |
| AgentTeams Embedded、QwenPaw、DeepSeek Harness | v1.2.8 |
| AgentTeams Dashboard | v1.4.3-unified |
| 官方网站 Bash 安装器 | v1.2.8，SHA-256 `06cbc319b9114784d5c61bdce7c81a3b4a2457445f246f56bebcfb915f7d6eee` |
| 卷初始化用 Alpine | amd64 固定镜像，启动器为它创建独立的本地标签 |

运行的是上游发布的镜像。本仓保存配置、部署检查和上游安装器，不打包开发者的数据库、模型 Key 或账号。上游清单摘要、amd64 配置摘要和离线归档在 Docker 29 容器镜像存储中的清单摘要见 [images.lock](images.lock)。本仓校验原安装器后，只在本机私有执行副本里把两处 Alpine 辅助容器改为已锁定的本地标签，避免更改其他项目的 `alpine:latest`。镜像已按原标签导入 Docker 时无需重新下载。

[AgentTeams 上游项目](https://github.com/agentscope-ai/AgentTeams) · [上游安装器来源](https://github.com/agentteams-group/agentteams-group.github.io/blob/main/public/install.sh) · [安装器原许可证](vendor/LICENSE)

## 重启、停止和迁移

- 重启电脑后，再次双击 **Start.cmd** 或运行 `bash start.sh`。脚本复用原数据卷，检查控制器、网关、Matrix 房间、Worker 进程和其控制器连接。若 Worker 曾提前退出，会等依赖启动后走原生重启接口。
- 停止这套实例并保留数据，运行 `bash start.sh --stop`。再次运行启动命令恢复。
- 全新独立部署请使用新电脑、VM 或新的前缀、数据目录和端口。首次启动前可设置 `TEAM_EVAL_PREFIX`（如 `trial-two-`）、`TEAM_EVAL_STATE`（无空格的 Linux 路径）、`TEAM_EVAL_PORT`（网页端口，Manager 同时使用该端口加 3）。后续恢复继续使用同一个数据目录。Windows 的 Start.cmd 也会把这三个 Windows 环境变量传给 WSL，按本次部署的实际端口打开浏览器。若公司禁用 WSL 调用 Windows 程序，请打开终端打印的网址。
- 默认应用状态在当前 Linux 用户的 `~/.local/share/agentteams-evaluation/`，包括权限受限的设置、上游私有日志、工作空间及专门的共享目录。不要将该目录提交到 Git 或分发。账号与聊天记录存于以 `workeval-agentteams-` 为前缀的 Docker 资源。要保留历史搬迁，先按上面的命令停止本实例，使用你们的 Docker/VM 备份工具保存该数据目录及所有此前缀的数据卷（含平台数据、Dashboard 数据及各运行时认证卷）。在新的隔离 VM 上先恢复同名卷与原数据目录，再装相同版本并启动。本仓提供全新初始化；历史数据迁移须在目标机验证。
- 官方自托管控制器需要挂载本机 Docker socket 来创建和维护 Worker；请选用公司允许用于评测的独立 Docker 环境。默认只把本项目的 **shared** 子目录作为 Manager 的主机共享目录。

## 验证边界

2026-11-24 在独立前缀、全新 Docker 数据卷和端口 19566 上进行了空白安装。官方服务完成初始化，三个新建的登录身份都通过了团队 API 和 Matrix 群成员检查，两名新建 Worker 均运行并能使用自己的身份访问 Matrix 运行状态。该轮使用无模型额度的测试占位值，未验证公司 Key。相同镜像的既有评测实例曾在团队群实测两名 Agent 分别回复 19 和 3。

启动器只在三个角色都能访问同一真实团队、两个 Worker 的 Matrix 进程和服务身份均正常后报告成功。要确认公司自己的模型额度、出网和响应质量，请用上面两条团队消息实际验证。Windows 本机回环地址仅供当前电脑的浏览器使用。
