"""Verify the AgentTeams release and import its images without moving shared tags."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

from image_lock import ALPINE, HELPER, images, inspect_image, require_local_engine


def file_hash(path):
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def release_files(folder):
    digests = {}
    for line in (folder / "SHA256SUMS").read_text(encoding="utf-8-sig").splitlines():
        sha, name = line.split()
        if name in digests:
            raise ValueError("Repeated file in SHA256SUMS: " + name)
        digests[name] = sha
    result = []
    for image in images():
        tag = image.tag
        name = ("alpine-amd64.tar.gz" if tag == ALPINE else
                "agentteams--" + tag.rsplit("/", 1)[1].replace(":", "-") + ".tar")
        p = folder / name
        if file_hash(p) != digests.pop(name):
            raise ValueError("SHA256 mismatch: " + name)
        with tarfile.open(p) as archive:
            entries = json.load(archive.extractfile("manifest.json"))
            if len(entries) != 1 or entries[0]["RepoTags"] != [tag]:
                raise ValueError("Unexpected image tag in " + name)
            image_config = archive.extractfile(entries[0]["Config"]).read()
            if "sha256:" + hashlib.sha256(image_config).hexdigest() != image.config:
                raise ValueError("Image config mismatch: " + name)
        result.append((p, image))
    if digests:
        raise ValueError("Unexpected files in SHA256SUMS")
    return result


def helper_archive(source):
    # The small utility is the only release archive with a global tag. Rewrite
    # both Docker and OCI naming metadata, preserving the original config/layers.
    data = io.BytesIO()
    repo, version = HELPER.split(":")
    with tarfile.open(source) as original, tarfile.open(fileobj=data, mode="w") as out:
        for member in original:
            file = original.extractfile(member) if member.isfile() else None
            if member.name in {"manifest.json", "index.json", "repositories"}:
                value = json.load(file)
                if member.name == "manifest.json":
                    value[0]["RepoTags"] = [HELPER]
                elif member.name == "index.json":
                    manifest, = value["manifests"]
                    manifest.setdefault("annotations", {}).update({
                        "io.containerd.image.name": "docker.io/" + HELPER,
                        "org.opencontainers.image.ref.name": version,
                    })
                else:
                    value = {repo: {version: value["alpine"]["latest"]}}
                file = io.BytesIO(json.dumps(value).encode("utf-8"))
                member = copy.copy(member)
                member.size = len(file.getbuffer())
            out.addfile(member, file)
    return data.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, help="Directory with SHA256SUMS and five archives")
    parser.add_argument("--check-only", action="store_true", help="Check files and existing Docker tags only")
    args = parser.parse_args()
    require_local_engine()
    subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, check=True)
    files = release_files(args.folder)
    missing = []
    for path, image in files:
        destination = image.destination
        current = inspect_image(destination)
        if current and not image.accepts(current):
            raise SystemExit("Local tag has a different image; no imports performed: " + destination)
        if not current:
            missing.append((path, image))
    print(f"Validated {len(files)} archives; {len(missing)} project tags require import.", flush=True)
    if args.check_only:
        return
    for path, image in missing:
        if image.tag == ALPINE:
            subprocess.run(["docker", "image", "load"], input=helper_archive(path), check=True)
        else:
            subprocess.run(["docker", "image", "load", "-i", str(path)], check=True)
        if not image.accepts(inspect_image(image.destination)):
            raise RuntimeError("Image import verification failed: " + image.destination)


if __name__ == "__main__":
    main()
