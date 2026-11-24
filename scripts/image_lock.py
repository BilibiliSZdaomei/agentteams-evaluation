"""Reference identities for the five pinned linux/amd64 images."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys

LOCK = Path(__file__).resolve().parents[1] / "images.lock"
ALPINE = "alpine:latest"
HELPER = "agentteams-evaluation/alpine:3ea06e4cb95e"


def require_local_engine():
    context = os.getenv("DOCKER_CONTEXT")
    endpoint = os.getenv("DOCKER_HOST")
    if context or not endpoint:
        cmd = ["docker", "context", "inspect"]
        if context:
            cmd.append(context)
        endpoint = subprocess.check_output(
            cmd + ["--format", "{{.Endpoints.docker.Host}}"], text=True).strip()
    if endpoint.startswith("unix://") or (os.name == "nt" and endpoint.startswith("npipe://")):
        return
    sys.exit("评测需连接本机 Docker socket。请检查 DOCKER_CONTEXT / DOCKER_HOST，避免操作远端引擎。")


@dataclass(frozen=True)
class Image:
    tag: str
    pinned: str
    config: str
    archive_manifest: str

    @property
    def destination(self):
        return HELPER if self.tag == ALPINE else self.tag

    def accepts(self, info):
        if info is None or info["platform"] != "linux/amd64":
            return False
        registry_digest = self.pinned.split("@")[1]
        accepted_ids = {self.config, self.archive_manifest, registry_digest}
        # Docker Hub can expand a short lock reference to docker.io/library/.
        published = any(ref.endswith("@" + registry_digest) for ref in info["repo_digests"])
        return info["id"] in accepted_ids or published


def images():
    return [Image(*line.split()) for line in LOCK.read_text().splitlines() if line.strip()]


def inspect_image(ref):
    template = '{{.Id}}|{{.Os}}/{{.Architecture}}|{{json .RepoDigests}}'
    result = subprocess.run(["docker", "image", "inspect", "--format", template, ref],
                            capture_output=True, text=True)
    if result.returncode:
        error = result.stderr.strip()
        if "no such" in error.lower() or "not found" in error.lower():
            return None
        raise RuntimeError(error or "Cannot inspect image " + ref)
    identifier, platform, digests = result.stdout.strip().split("|")
    return {"id": identifier, "platform": platform, "repo_digests": json.loads(digests) or []}
