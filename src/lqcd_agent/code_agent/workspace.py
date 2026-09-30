"""Immutable text trees and fenced, disposable Host-managed workspaces."""
from hashlib import sha256
import difflib
import os
from pathlib import Path
import stat
import subprocess

from lqcd_agent.control.coordinator import exclusive_directory, publish_exact, read_regular
from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, digest_value, loads, number, require

from .schemas import protected_path, relative_path, validate_manifest, validate_task, within


def tree_digest(files):
    return digest({path: sha256(content).hexdigest() for path, content in sorted(files.items())})


def _text_file(path, content):
    relative_path(path)
    require(not protected_path(path), "Protected workspace content")
    require(type(content) is bytes and b"\x00" not in content, "Unsupported binary content")
    try:
        content.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("Workspace content must be UTF-8 text") from error


def immutable_git_tree(repository, revision):
    """Read committed blobs only; never checkout, import or run repository code."""
    repository = Path(repository)
    control = Path(__file__).resolve().parents[3]
    require(repository.is_absolute() and repository == repository.resolve() and repository.is_dir() and
            not repository.is_relative_to(control) and not control.is_relative_to(repository), "Invalid immutable base repository")
    git_dir = repository / ".git"
    require(git_dir.is_dir() and not git_dir.is_symlink() and git_dir.resolve() == git_dir and
            not (git_dir / "objects/info/alternates").exists() and not (git_dir / "commondir").exists(),
            "Base repository has external object authority")
    require(type(revision) is str and len(revision) in (40, 64) and all(c in "0123456789abcdef" for c in revision),
            "Base requires a full immutable commit")

    def git(*args):
        result = subprocess.run(["/usr/bin/git", "--no-replace-objects", "-c", "core.fsmonitor=false", "-c",
            "core.hooksPath=/dev/null", "-C", str(repository), *args], check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                                         "GIT_CONFIG_GLOBAL": os.devnull}, timeout=10, shell=False)
        return result.stdout

    require(git("rev-parse", "--verify", revision + "^{commit}").decode().strip() == revision, "Base is not the exact commit")
    files = {}
    for row in git("ls-tree", "-rz", "--full-tree", revision).split(b"\x00"):
        if not row:
            continue
        header, raw_path = row.split(b"\t", 1)
        mode, kind, blob = header.split(b" ")
        require(mode == b"100644" and kind == b"blob", "Unsupported base file type or mode")
        path = raw_path.decode("utf-8")
        content = git("cat-file", "blob", blob.decode())
        _text_file(path, content)
        require(path.casefold() not in {key.casefold() for key in files}, "Base path normalization collision")
        files[path] = content
    require(files, "Empty immutable Code base")
    return files


def scan_tree(root, *, expected_paths=()):
    """Inspect all filesystem entries, including untracked and hidden content."""
    root = Path(root)
    require(root.is_dir() and root == root.resolve() and not root.is_symlink(), "Missing or replaced workspace")
    device = root.stat().st_dev
    files, aliases, directory_paths = {}, set(), []
    for directory, directories, filenames in os.walk(root, followlinks=False):
        for name in sorted([*directories, *filenames]):
            entry = Path(directory) / name
            info = entry.lstat()
            path = entry.relative_to(root).as_posix()
            relative_path(path)
            require(not protected_path(path) and entry.resolve() == entry and info.st_dev == device,
                    "Workspace namespace or mount escape")
            require(path.casefold() not in aliases, "Workspace path normalization collision")
            aliases.add(path.casefold())
            if stat.S_ISDIR(info.st_mode):
                require(not stat.S_ISLNK(info.st_mode), "Workspace symlink directory")
                directory_paths.append(path)
                continue
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o111,
                    "Unsupported workspace file type, link or executable mode")
            content = read_regular(entry)
            _text_file(path, content)
            files[path] = content
    require(all(any(path.startswith(directory + "/") for path in (*files, *expected_paths)) for directory in directory_paths),
            "Unaccounted empty workspace directory")
    return files


def validate_changes(task, base, final):
    """Derive changes from complete trees; a Backend manifest is never authority."""
    require(tree_digest(base) == task["base_tree_digest"], "Immutable base tree drift")
    changes = []
    for path in sorted(base.keys() | final.keys()):
        before, after = base.get(path), final.get(path)
        if before == after:
            continue
        relative_path(path)
        require(within(path, task["write_paths"]) and not within(path, task["forbidden_paths"]) and
                not protected_path(path) and not within(path, task["filesystem_policy"]["ephemeral_paths"]),
                "Out-of-scope persistent change")
        if after is not None:
            _text_file(path, after)
        changes.append({"path": path, "kind": "added" if before is None else "deleted" if after is None else "modified",
            "before_sha256": sha256(before).hexdigest() if before is not None else None,
            "after_sha256": sha256(after).hexdigest() if after is not None else None, "mode": "100644",
            "blob_digest": sha256(after).hexdigest() if after is not None else None})
    return changes


def canonical_patch(base, final, changes):
    """Derive patch bytes from the complete Host-observed before/after trees."""
    output = []
    for change in changes:
        path = change["path"]
        before = base.get(path, b"").decode("utf-8").splitlines(keepends=True)
        after = final.get(path, b"").decode("utf-8").splitlines(keepends=True)
        old_name = "/dev/null" if change["kind"] == "added" else "a/" + path
        new_name = "/dev/null" if change["kind"] == "deleted" else "b/" + path
        output.extend(difflib.unified_diff(before, after, fromfile=old_name, tofile=new_name, lineterm="\n"))
    return "".join(output).encode("utf-8")


class WorkspaceProvider:
    """A filesystem port; the caller supplies a live coordinator fence each time."""

    def __init__(self, managed_root):
        self.root = Path(managed_root)
        control = Path(__file__).resolve().parents[3]
        require(self.root.is_absolute() and self.root == self.root.resolve() and
                not self.root.is_relative_to(control) and not control.is_relative_to(self.root), "Invalid managed workspace root")

    def path(self, workspace_id):
        relative_path(workspace_id)
        require("/" not in workspace_id and workspace_id[0].isalnum(), "Workspace identity is not a path")
        return self.root / workspace_id

    def materialize(self, manifest, files, fence, *, witness=None):
        """Only an unpublished, precomputed directory may have missing members."""
        require(tree_digest(files) == manifest["base_tree_digest"], "Workspace base does not match manifest")
        require(len({path.casefold() for path in files}) == len(files), "Workspace path normalization collision")
        for path, content in files.items():
            _text_file(path, content)
        destination = self.path(manifest["workspace_id"])
        fence()
        if witness is not None:
            self.verify_identity(manifest, witness)
            require(scan_tree(destination) == files, "Materialized workspace changed")
            return witness
        exclusive_directory(self.root)
        owners = self.root / ".workspace_owners"
        exclusive_directory(owners)
        ownership = owners / (manifest["workspace_id"] + ".json")
        if ownership.exists():
            self.verify_identity(manifest, self._public_witness(manifest))
        else:
            require(not destination.exists() and not destination.is_symlink(), "Workspace has no trusted creation witness")
            exclusive_directory(destination)
            info = destination.stat()
            publish_exact(ownership, canonical_bytes({**self._public_witness(manifest), "device": info.st_dev, "inode": info.st_ino}))
        existing = scan_tree(destination, expected_paths=files)
        require(all(path in files and files[path] == content for path, content in existing.items()),
                "Conflicting workspace materialization")
        for path, content in sorted(files.items()):
            fence()
            target = destination / path
            parent = destination
            for part in target.parent.relative_to(destination).parts:
                parent = parent / part
                exclusive_directory(parent)
            publish_exact(target, content)
        fence()
        require(scan_tree(destination) == files, "Workspace materialization incomplete")
        return self._public_witness(manifest)

    @staticmethod
    def _public_witness(manifest):
        return {key: manifest[key] for key in ("workspace_id", "manifest_digest", "managed_root_identity", "base_tree_digest")}

    def verify_identity(self, manifest, witness):
        path = self.path(manifest["workspace_id"])
        require(path.is_dir() and path.resolve() == path and not path.is_symlink(), "Workspace disappeared or escaped")
        info = path.stat()
        expected = self._public_witness(manifest)
        ownership = self.root / ".workspace_owners" / (manifest["workspace_id"] + ".json")
        require(ownership.resolve() == ownership and witness == expected and
                loads(read_regular(ownership)) == {**expected, "device": info.st_dev, "inode": info.st_ino},
                "Workspace identity was replaced")
        return path

    def verify_sealed(self, manifest, witness, expected_tree):
        path = self.verify_identity(manifest, witness)
        files = scan_tree(path)
        require(tree_digest(files) == expected_tree, "Post-seal workspace mutation")
        return files


def validate_tool_audit(content, task, manifest):
    """Keep every observed invocation; backend claims never satisfy verification."""
    require(type(content) is bytes and (not content or content.endswith(b"\n")), "Incomplete tool audit")
    events = [loads(line) for line in content.splitlines()]
    require(all(line == canonical_bytes(event) for line, event in zip(content.splitlines(), events)),
            "Noncanonical tool audit event")
    tool_ids = {spec["spec_id"] for spec in task["tool_policy"]}
    for index, event in enumerate(events, 1):
        closed(event, ("tool_event_index", "task_id", "workspace_id", "tool_id", "argv_digest", "cwd",
                       "start_at", "end_at", "status", "affected_paths", "output_digest", "resource_usage"))
        require(event["tool_event_index"] == index and event["task_id"] == task["task_id"] and
                event["workspace_id"] == manifest["workspace_id"] and event["tool_id"] in tool_ids,
                "Tool audit sequence or authority changed")
        digest_value(event["argv_digest"])
        digest_value(event["output_digest"])
        relative_path(event["cwd"], root=True)
        number(event["start_at"])
        number(event["end_at"])
        require(event["end_at"] >= event["start_at"] and
                event["status"] in ("completed", "failed", "timeout", "blocked"), "Invalid tool observation")
        paths = event["affected_paths"]
        require(type(paths) is list and paths == sorted(set(paths)), "Invalid tool path audit")
        for path in paths:
            relative_path(path)
            require(within(path, task["write_paths"]) and not protected_path(path), "Tool escaped task scope")
        usage = closed(event["resource_usage"], ("llm_calls", "tool_calls", "active_seconds"))
        for name, value in usage.items():
            number(value, integer=name != "active_seconds", minimum=0)
        require(usage["tool_calls"] == 1, "One audit event must represent one tool invocation")
    return events


def seal_workspace(provider, task, manifest, witness, base, *, backend_status, stop_proof, tool_audit,
                   sealed_at, fence):
    """Freeze complete Host-observed content only after a proved stop."""
    task = validate_task(task).value
    manifest = validate_manifest(manifest, task).value
    require(backend_status in ("completed", "failed"), "Backend has no terminal result")
    require(type(stop_proof) is dict and set(stop_proof) == {
        "termination_or_not_dispatched", "write_lease_revocation", "verify_empty", "bounded_drain",
        "post_stop_stability"} and stop_proof["termination_or_not_dispatched"] == "confirmed" and
        all(stop_proof[name] is True for name in stop_proof if name != "termination_or_not_dispatched"),
        "Workspace lacks complete safe stop proof")
    number(sealed_at)
    fence()
    final = scan_tree(provider.verify_identity(manifest, witness))
    changes = validate_changes(task, base, final)
    validate_tool_audit(tool_audit, task, manifest)
    provider.verify_sealed(manifest, witness, tree_digest(final))
    change_manifest = {"schema_version": "0.1", "task_id": task["task_id"],
                       "workspace_id": manifest["workspace_id"], "base_tree_digest": task["base_tree_digest"],
                       "final_tree_digest": tree_digest(final), "changes": changes}
    change_manifest["change_manifest_digest"] = digest(change_manifest)
    seal = {"schema_version": "0.1", "workspace_id": manifest["workspace_id"],
            "workspace_manifest_digest": manifest["manifest_digest"], "producer_operation_id": task["producer_operation_id"],
            "coding_backend_kind": task["coding_backend_kind"], "backend_version": task["backend_version"],
            "terminal_backend_status": backend_status, "final_tree_digest": change_manifest["final_tree_digest"],
            "change_manifest_digest": change_manifest["change_manifest_digest"],
            "tool_audit_digest": sha256(tool_audit).hexdigest(), "stop_proof_digest": digest(stop_proof),
            "sealed_at": sealed_at, "write_lease_revoked": True}
    seal["seal_digest"] = digest(seal)
    fence()
    provider.verify_sealed(manifest, witness, seal["final_tree_digest"])
    return change_manifest, seal
