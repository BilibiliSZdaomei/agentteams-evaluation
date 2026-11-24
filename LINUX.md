# 在 Ubuntu 服务器独立评测

适用于 Ubuntu 22.04 x86_64、Docker Engine 29.1.3 和本机 Docker Unix socket。AgentTeams 使用 Docker CLI，本流程不依赖 Compose。已有 Compose 2.40.3、容器化 Nginx 及其他业务栈可继续使用。评测入口默认仅监听回环，通过 SSH 本地端口转发打开，不需要改 Nginx、域名、防火墙或系统服务配置。

## 把程序和镜像上传到哪里

以下示例在有 SSH/SCP 和 Git 的 Bash（包括 Windows 的 WSL）中执行。示例在登录用户的 HOME 创建专属目录；若 HOME 空间有限，可改为管理员已分配给你的 **/data 下独立可写目录**。不要将上传文件放入 Docker 的 `/data/docker`。首次使用空的 app 目录，以免覆盖自己的已有文件。

在自己的电脑上进入本仓的 Git 工作副本，准备 [Release 镜像和 SHA256SUMS](OFFLINE.md)。`images` 变量填**下载目录**，不要填容器数据目录。

```bash
read -rp "堡垒机的 SSH 配置别名或 user@host: " jump
read -rp "目标服务器的 SSH 配置别名或 user@host: " target
read -rp "本地 Release 附件目录: " images
bundle="$(mktemp -d)"
git archive --format=tar.gz -o "$bundle/agentteams-src.tgz" HEAD
ssh -J "$jump" "$target" 'umask 077; mkdir -p "$HOME/evaluations/agentteams/app" "$HOME/evaluations/agentteams/images"'
scp -o "ProxyJump=$jump" "$bundle/agentteams-src.tgz" "${target}:evaluations/agentteams/"
scp -o "ProxyJump=$jump" "$images/SHA256SUMS" "$images"/agentteams--*.tar "$images/alpine-amd64.tar.gz" "${target}:evaluations/agentteams/images/"
ssh -J "$jump" "$target"
```

只有堡垒机支持标准 SSH ProxyJump 时才使用 `-J`。若公司通过门户或专用上传工具管理登录，使用已批准的方式上传到同样的 **app 的父目录** 和 **images**，再打开目标机终端。

## 在服务器上启动

用同一个普通 Linux 账号执行以下命令。该账号需已获本机 Docker Engine 的使用权限。Ubuntu 默认 rootful Docker 的 socket 通常为 `/var/run/docker.sock`；按公司实际授权使用。如果 `docker info` 提示 permission denied，联系管理员授权或代为测试。不要修改 socket 的属主或权限，也不要混用 sudo 运行，以免产生另一套用户目录与配置。

```bash
cd "$HOME/evaluations/agentteams"
tar --keep-old-files -xzf agentteams-src.tgz -C app
cd app
docker context show
docker info --format '{{.OSType}}/{{.Architecture}}  {{.ServerVersion}}  {{.DockerRootDir}}'
df -h . "$HOME"
ss -ltn '( sport = :18966 or sport = :18969 )'
python3 scripts/load_offline.py ../images --check-only
python3 scripts/load_offline.py ../images
bash start.sh
```

- `docker` 应连接**这台服务器**上的 Linux Docker Engine。远程 Docker context 会使容器发布地址与本地引导地址不一致。
- 初装默认固定使用 **127.0.0.1:18966**（网页网关）和 **127.0.0.1:18969**（Manager 控制台）。上游还为 Worker/Manager 自动分配回环端口。18967、18968、18970 在当前统一入口部署中没有固定对外映射。若固定端口已占用，首次启动前可用 `TEAM_EVAL_PORT=19566 bash start.sh`，此时固定端口为 19566、19569。
- 程序、镜像和实际 Docker 数据分开存放。配置和私有安装日志默认在 `$HOME/.local/share/agentteams-evaluation`，Docker 自行在已配置的 data-root 下存储卷和镜像。启动脚本不会重新设置 Docker data-root。若要改配置目录，在首次及后续启动都传同一 `TEAM_EVAL_STATE=/你已有权限的无空格目录`。
- 默认资源前缀为 `workeval-agentteams-`。新配置目录检测到同名前缀时会停止，避免接管其他人的容器或卷。加载镜像前会检查五个附件的摘要与标签，并为辅助 Alpine 保留独立标签。共用存储空间请按实际 Docker 剩余空间和公司配额评估。
- 启动完成会打印团队网址。首次输入的新密码供 `planning`、`logistics`、`admin` 使用。在线聊天需要从部署环境访问 DeepSeek，并有可用 Key。

## 在自己的电脑浏览器打开

在工作电脑再开一个终端，用同一堡垒机/目标机参数运行下列命令，保持 SSH 会话开启。在公司明确允许 SSH TCP 转发时使用；无法转发的账号需由管理员提供获准的访问路径。

```bash
read -rp "堡垒机的 SSH 配置别名或 user@host: " jump
read -rp "目标服务器的 SSH 配置别名或 user@host: " target
ssh -N -o ExitOnForwardFailure=yes -J "$jump" -L 127.0.0.1:18966:127.0.0.1:18966 "$target"
```

打开 [AgentTeams 团队工作台](http://localhost:18966/dashboard/#workbench/teams)。这个网址在工作电脑通过 SSH 到达服务器。若服务器改为 19566，请将转发命令的两个 18966 及浏览器端口都改为 19566。若电脑本地已有 18966 端口的其他评测站，先为本次独立部署选择两端都可用的端口。

停止此次部署时，在服务器仓库目录运行 `bash start.sh --stop`，只停止此前缀的五个容器，保留卷和记录。再次运行 `bash start.sh` 恢复。关闭工作电脑上的 SSH 隧道只会断开该电脑的访问。
