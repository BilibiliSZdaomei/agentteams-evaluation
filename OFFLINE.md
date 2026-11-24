# 离线安装所需的容器镜像

从[此版本的依赖下载页](https://github.com/BilibiliSZdaomei/agentteams-evaluation/releases/tag/runtime-linux-amd64-20261124)下载 `SHA256SUMS` 及五个镜像附件，放在同一个目录。另下载或克隆本仓源码。镜像适用于 Linux x86_64，也可在 Windows x64 的 Docker Desktop（Linux 容器）中使用。

在**仓库根目录**执行以下命令，把最后一个参数替换为附件目录。Linux 需要 Python 3 和能访问本机 Unix socket 的 Docker CLI。Windows 若从 PowerShell 操作，请确保 Windows 的 Python 3 和 Docker CLI 可用，或切换到已启用 Docker Integration 的 WSL 执行 Linux 命令。

**Linux / WSL**

```bash
python3 scripts/load_offline.py "$HOME/evaluations/agentteams/images"
```

**Windows PowerShell**

```powershell
py -3 scripts/load_offline.py "D:\Downloads\agentteams-images"
```

如只想检查全部文件与本地标签，可以在命令末尾加 `--check-only`。脚本先核对所有文件的 SHA-256、镜像标签及配置摘要，再导入缺少的镜像。四个服务使用项目版本标签，若有不同内容的同名标签，导入将中止。Alpine 工具镜像只导入为 `agentteams-evaluation/alpine:3ea06e4cb95e`，保留宿主机现有的 `alpine:latest`。后续启动沿用该独立标签。完成后按[仓库首页](README.md)启动。模型对话仍需部署机能够访问 DeepSeek 并使用自己的 Key。
