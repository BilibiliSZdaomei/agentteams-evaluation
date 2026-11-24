"""Provision real Team/Human/Worker resources through AgentTeams' APIs."""
import json
import os
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import build_opener, ProxyHandler, Request

class API:
    def __init__(self, port):
        self.origin = "http://localhost:" + str(port)
        self.opener = build_opener(ProxyHandler({}))
        self.token = None

    def request(self, path, data=None, method=None):
        headers = {"Content-Type":"application/json", "Origin":self.origin}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = Request(self.origin+path, data=None if data is None else json.dumps(data).encode(),
                      headers=headers, method=method)
        try:
            with self.opener.open(req,timeout=12) as result:
                content = result.read()
                return result.status, json.loads(content) if content else {}
        except HTTPError as error:
            return error.code, {}
        except (URLError, TimeoutError, ValueError, ConnectionError):
            return 0, {}

    def ok(self,path,data=None,method=None):
        status,result = self.request(path,data,method)
        if not 200 <= status < 300:
            raise RuntimeError(f"{method or ('GET' if data is None else 'POST')} {path} returned HTTP {status}")
        return result

    def login(self,role,password):
        status,result=self.request("/_matrix/client/v3/login",{"type":"m.login.password",
            "identifier":{"type":"m.id.user","user":role},"password":password,
            "device_id":"WORK_EVAL_SETUP_"+role.upper(),"initial_device_display_name":"团队部署检查"})
        if status==200:
            self.token=result["access_token"]
        return status==200

def wait(check, what, seconds=230):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        found=check()
        if found:
            return found
        time.sleep(3)
    raise RuntimeError("等待超时：" + what)

def ensure(a,resource,name,payload):
    path="/api/v1/"+resource
    status,_=a.request(path+"/"+name)
    if status==404:
        a.ok(path,dict(name=name,**payload))
    elif status!=200:
        raise RuntimeError(f"{resource}/{name} HTTP {status}")

def provision(cfg, home, containers):
    admin=API(cfg["port"])
    wait(lambda:admin.login("admin",cfg["password"]),"管理员登录")
    resource="/api/v1/gateway/assets/models"
    wait(lambda:admin.request(resource,{"action":"list"})[0]==200, "DeepSeek 网关")
    team="/api/v1/teams/planning-logistics"
    roles={"planning":"计划员","logistics":"物流员"}
    marker=home/"team-initialized"
    if not marker.exists():
        for role in ("shared", "planning", "logistics"):
            provider="eval-"+role
            model="ds-flash-"+role
            status,_=admin.request(resource,{"action":"get","name":provider})
            if status not in (200,404):
                # Gateway versions can reply 400 for unknown providers; verify against list.
                known=admin.ok(resource,{"action":"list"})
                status=200 if any(r["name"]==provider for r in known) else 404
            mapping={model:cfg["model"]}
            if role=="shared":mapping[cfg["model"]]=cfg["model"]
            admin.ok(resource,{"action":"save","update":status==200,"input":{"name":provider,
                "type":"deepseek","protocol":"openai/v1","tokens":[cfg["keys"][role]],"rawConfigs":{"modelMapping":mapping}}})
        wait(lambda:admin.request("/api/v1/managers/default")[0]==200,"Manager")
        admin.ok("/api/v1/managers/default",{"model":"ds-flash-shared","modelProvider":"eval-shared"},"PUT")
        for role,label in roles.items():
            name=role+"-agent"
            ensure(admin,"workers",name,{"runtime":"deepseek-harness","model":"ds-flash-"+role,
                   "modelProvider":"eval-"+role,"identity":label+"的个人助手，请用中文回答。"})
            admin.ok(resource,{"action":"bind","provider":"eval-"+role,"model":"ds-flash-"+role,"worker":name})
            ensure(admin,"humans",role,{"displayName":label,"permissionLevel":2,"note":"公司本机评测账号"})
            wait(lambda:admin.ok("/api/v1/humans/"+role).get("matrixUserID"),role+" Matrix 账号")
            person=API(cfg["port"])
            if not person.login(role,cfg["password"]):
                admin.ok("/api/v1/humans/"+role+"/reset-password",{"newPassword":cfg["password"]})
            admin.ok("/api/v1/humans/"+role,{"accessibleWorkers":[name]},"PUT")
        ensure(admin,"teams","planning-logistics",{"teamName":"计划与物流协作","admin":{"name":"planning"},
             "description":"核对备件库存缺口、运输数量和交接。",
             "humanMembers":[{"name":"logistics","role":"member"},{"name":"admin","role":"member"}],
             "workerMembers":[{"name":"planning-agent","role":"team_leader"},{"name":"logistics-agent","role":"worker"}],
             "peerMentions":True})
    active=wait(lambda:(lambda t:t if t.get("phase")=="Active" and t.get("teamRoomID") else None)(admin.ok(team)),
                "计划与物流协作团队 Active")
    for role in ("admin", *roles):
        user=admin if role=="admin" else API(cfg["port"])
        if role!="admin":
            wait(lambda:user.login(role,cfg["password"]),role+" 的统一密码登录")
        assert user.ok(team)["name"]=="planning-logistics"
        room=active["teamRoomID"]
        wait(lambda:user.request("/_matrix/client/v3/join/"+quote(room,safe=""),{})[0]==200,role+" 进入团队群")
        if room not in user.ok("/_matrix/client/v3/joined_rooms")["joined_rooms"]:
            raise RuntimeError(role+" 未进群")
    for role,container in zip(roles,containers):
        last=0
        def ready():
            nonlocal last
            check=subprocess.run(["docker","inspect","--format","{{.State.Running}}",container],capture_output=True,text=True)
            if check.returncode==0 and check.stdout.strip()=="true":
                return subprocess.run(["docker","exec",container,"python3","-c",PROBE],capture_output=True,timeout=12).returncode==0
            if time.monotonic()-last>20:
                admin.request("/api/v1/workers/"+role+"-agent/restart",{})
                last=time.monotonic()
            return False
        wait(ready, role+" Agent 的 Matrix 连接")
    marker.touch(mode=0o600)
    print("已验证团队 Active，三个账号均可打开同一团队，两名 Agent 已接入。",flush=True)

PROBE = r"""from pathlib import Path
import os
from urllib.request import Request, urlopen
args = b'/opt/agentteams/scripts/matrix_bridge.py'
for proc in Path('/proc').glob('[0-9]*'):
    try:
        if args in (proc/'cmdline').read_bytes().split(b'\0'):
            break
    except OSError:
        continue
else:
    raise SystemExit(1)
token = Path(os.environ['AGENTTEAMS_AUTH_TOKEN_FILE']).read_text().strip()
req = Request(os.environ['AGENTTEAMS_CONTROLLER_URL'].rstrip('/')+'/api/v1/runtime/matrix',
              headers={'Authorization':'Bearer '+token})
with urlopen(req, timeout=4) as reply:
    if reply.status != 200:
        raise SystemExit(1)"""
