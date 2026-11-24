"""Install or resume one isolated, pinned AgentTeams evaluation."""
import argparse
import fcntl
import getpass
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_HASH = "06cbc319b9114784d5c61bdce7c81a3b4a2457445f246f56bebcfb915f7d6eee"
HELPER = "agentteams-evaluation/alpine:3ea06e4cb95e"

def run(cmd, **opts):
    return subprocess.run(cmd, check=True, **opts)

def inspect(kind, name, template):
    p = subprocess.run(["docker", kind, "inspect", "--format", template, name], capture_output=True, text=True)
    return p.stdout.strip() if not p.returncode else ""

def show_team(port, open_windows):
    url = f"http://localhost:{port}/dashboard/#workbench/teams"
    print("团队网址   " + url, flush=True)
    print("登录账号   planning / logistics / admin，使用首次设置的同一个密码。", flush=True)
    if open_windows:
        try:
            run(["rundll32.exe", "url.dll,FileProtocolHandler", url])
        except (OSError, subprocess.CalledProcessError):
            sys.exit("团队已启动。Windows 浏览器未自动打开，请使用上方网址。")

def prepare_images():
    for line in (ROOT / "images.lock").read_text().splitlines():
        tag, pinned, config = line.split()
        actual = inspect("image", tag, "{{.Id}}")
        if actual and actual != config and tag != "alpine:latest":
            sys.exit("Local image conflicts with the pinned release: " + tag)
        if actual != config and not inspect("image", config, "{{.Id}}"):
            run(["docker", "pull", "--platform", "linux/amd64", pinned])
        if inspect("image", config, "{{.Id}}") != config:
            sys.exit("Pinned image config mismatch for " + tag)
        alias = HELPER if tag == "alpine:latest" else tag
        if inspect("image", alias, "{{.Id}}") != config:
            run(["docker", "tag", config, alias])

def fresh_settings():
    password = os.environ.get("TEAM_EVAL_PASSWORD") or getpass.getpass("三个评测账号的新密码（至少 12 位英文、数字、点、下划线或短横线）：")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{12,100}", password):
        sys.exit("密码长度或字符不符合安装器要求。")
    shared = os.environ.get("TEAM_DEEPSEEK_KEY") or getpass.getpass("公共 DeepSeek API Key：").strip()
    if not shared:
        sys.exit("必须提供公司评测用的新 DeepSeek API Key。")
    keys = {"shared":shared}
    for role, label in (("planning","计划员"), ("logistics","物流员")):
        value = os.environ.get("TEAM_" + role.upper() + "_KEY")
        if value is None:
            value = getpass.getpass(label + " DeepSeek Key（回车沿用公共 Key）：").strip()
        keys[role] = value or shared
    return {"password":password, "keys":keys, "model":os.getenv("TEAM_MODEL", "deepseek-flash")}

def main():
    from bootstrap import provision
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--open-windows", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if shutil.which("docker") is None:
        sys.exit("当前 WSL/Linux 内没有可用的 Docker CLI，请检查 Docker Desktop 的 WSL Integration。")
    run(["docker", "info"], stdout=subprocess.DEVNULL)
    architecture = subprocess.check_output(["docker","info","--format","{{.OSType}}/{{.Architecture}}"],text=True).strip()
    if architecture not in ("linux/x86_64","linux/amd64"):
        sys.exit("需要 Linux x86_64 容器引擎，当前为 " + architecture)
    home = Path(os.getenv("TEAM_EVAL_STATE", str(Path.home()/".local/share/agentteams-evaluation"))).resolve()
    if any(c.isspace() for c in str(home)):
        sys.exit("请把 TEAM_EVAL_STATE 指向无空格的 Linux 数据目录。")
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (home / "deploy.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    settings = home / "settings.json"
    prefix = os.getenv("TEAM_EVAL_PREFIX", "workeval-agentteams-")
    if not re.fullmatch("[a-z][a-z0-9-]{2,35}-", prefix):
        sys.exit("TEAM_EVAL_PREFIX 需为以短横线结尾的小写名称。")
    port = int(os.getenv("TEAM_EVAL_PORT","18966"))
    if not 1024 <= port <= 65531:
        sys.exit("无效端口。")
    if settings.exists():
        cfg = json.loads(settings.read_text())
        changed_prefix = "TEAM_EVAL_PREFIX" in os.environ and prefix != cfg["prefix"]
        changed_port = "TEAM_EVAL_PORT" in os.environ and port != cfg["port"]
        if changed_prefix or changed_port:
            sys.exit("该数据目录已绑定其他前缀或端口。")
        prefix, port = cfg["prefix"], cfg["port"]
    else:
        if args.stop:
            sys.exit("当前数据目录尚无安装。")
        conflicts = subprocess.check_output(["docker","ps","-a","--format","{{.Names}}"],text=True).splitlines()
        vols = subprocess.check_output(["docker","volume","ls","-q"],text=True).splitlines()
        nets = subprocess.check_output(["docker","network","ls","--format","{{.Name}}"],text=True).splitlines()
        if any(x.startswith(prefix) for x in conflicts + vols + nets):
            sys.exit("此前缀已有 Docker 资源，请还原原数据目录或选新前缀。")
        for n in range(port,port+5):
            with socket.socket() as probe:
                try: probe.bind(("127.0.0.1",n))
                except OSError: sys.exit("端口已占用：" + str(n))
        cfg = fresh_settings()
        cfg.update(port=port, prefix=prefix)
        with settings.open("x") as file:
            json.dump(cfg,file)
    core = [prefix + name for name in ("controller","dashboard","manager")]
    worker_names = [prefix + "worker-" + name + "-agent" for name in ("planning","logistics")]
    if args.stop:
        for name in worker_names + list(reversed(core)):
            if inspect("container",name,"{{.State.Running}}") == "true":
                run(["docker","stop",name],stdout=subprocess.DEVNULL)
        print("AgentTeams 已停止，数据已保留。")
        return

    source = (ROOT / "vendor/install.sh").read_bytes()
    if hashlib.sha256(source).hexdigest()!=INSTALL_HASH:
        sys.exit("上游安装器校验失败。")
    if not all(inspect("container",name,"{{.Id}}") for name in core):
        prepare_images()
        for name in ("workspace","shared"):
            (home/name).mkdir(mode=0o700, exist_ok=True)
        env = dict(os.environ)
        env.update(AGENTTEAMS_VERSION="v1.2.8", AGENTTEAMS_LANGUAGE="zh", AGENTTEAMS_RESOURCE_PREFIX=prefix,
            AGENTTEAMS_NON_INTERACTIVE="1", AGENTTEAMS_LOCAL_ONLY="1",AGENTTEAMS_UNIFIED_ENTRY="1",
            AGENTTEAMS_REGISTRY="higress-registry.cn-hangzhou.cr.aliyuncs.com", AGENTTEAMS_DASHBOARD="1",
            AGENTTEAMS_DASHBOARD_VERSION="v1.4.3", AGENTTEAMS_MANAGER_RUNTIME="qwenpaw",
            AGENTTEAMS_DEFAULT_WORKER_RUNTIME="deepseek-harness",AGENTTEAMS_LLM_PROVIDER="eval-shared",
            AGENTTEAMS_ADMIN_USER="admin", AGENTTEAMS_ADMIN_PASSWORD=cfg["password"],
            AGENTTEAMS_DEFAULT_MODEL=cfg["model"], AGENTTEAMS_OPENAI_BASE_URL="https://api.deepseek.com/v1",
            AGENTTEAMS_LLM_API_KEY="", AGENTTEAMS_LOG_FILE=str(home/"installer.log"),
            AGENTTEAMS_INSTALL_EMBEDDED_IMAGE="higress-registry.cn-hangzhou.cr.aliyuncs.com/agentteams/agentteams-embedded:v1.2.8",
            AGENTTEAMS_ENV_FILE=str(home/"manager.env"), AGENTTEAMS_HOST_SHARE_DIR=str(home/"shared"),
            AGENTTEAMS_WORKSPACE_DIR=str(home/"workspace"), AGENTTEAMS_DATA_DIR=prefix+"data",
            AGENTTEAMS_ENTRY_EXTERNAL_URL=f"http://localhost:{port}")
        for offset,key in enumerate(("GATEWAY","ELEMENT_WEB","DASHBOARD","MANAGER_CONSOLE","CONSOLE")):
            env["AGENTTEAMS_PORT_"+key]=str(port+offset)
        script = home/"pinned-install.sh"
        script.write_bytes(source.replace(b'alpine:latest',HELPER.encode("ascii")))
        print("正在启动原版 AgentTeams，首次启动可能需要数分钟。",flush=True)
        # Upstream prints generated secrets; only the private installer log receives them.
        with (home/"install-output.log").open("ab") as log:
            run(["bash",str(script)],env=env,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
    for name in core:
        if inspect("container",name,"{{.State.Running}}")!="true":
            run(["docker","start",name],stdout=subprocess.DEVNULL)
    provision(cfg, home, worker_names)
    show_team(port, args.open_windows)

if __name__ == "__main__":
    main()
