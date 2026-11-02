"""Explicit operator actions on local research assets, without model execution."""
from hashlib import sha256
from pathlib import PurePosixPath

from lqcd_agent.configuration import read_config
from lqcd_agent.control.coordinator import publish_exact, read_regular, sync_directory
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads, require
from lqcd_agent.settings import workspace_root
from .library import Library
from .projects import ProjectStore


COMMANDS = ("project-create", "project-list", "project-show", "library-search", "library-save",
            "library-review", "library-register-method")
MAX_INPUT_BYTES = 1024 * 1024


def _input(library, relative):
    path = library._path(relative)
    require(not any(part.startswith(".") for part in PurePosixPath(relative).parts),
            "Hidden files are not research inputs")
    require(path.stat().st_size <= MAX_INPUT_BYTES, "Research input exceeds 1 MiB")
    raw = read_regular(path)
    require(len(raw) <= MAX_INPUT_BYTES, "Research input exceeds 1 MiB")
    return path, raw


def _project_reference(library, relative):
    require(type(relative) is str and PurePosixPath(relative).parts and
            PurePosixPath(relative).parts[0] == "projects", "Evidence must be a project file")
    _, raw = _input(library, relative)
    return {"path": relative, "sha256": sha256(raw).hexdigest()}


def _receipt(library, request, *, kind, status, evidence):
    """The explicit CLI action owns this decision; models cannot call this path."""
    current = library.read(kind, request["id"])
    require(current["revision"] == request["expected_revision"], "Stale scientific asset revision")
    value = {"kind": kind, "id": request["id"], "revision": current["revision"], "status": status,
             "actor": "operator", "rationale": request["rationale"], "evidence": evidence}
    relative = f"library/reviews/{digest(value)}.json"
    path = library._path(relative)
    with library._locked(write=True):
        path.parent.mkdir(mode=0o700, exist_ok=True)
        sync_directory(path.parent.parent)
        publish_exact(path, canonical_bytes(value))
    return library.reference(relative)


def execute_workspace(request):
    """Dispatch only operator commands; no credentials, Host or SDK is loaded."""
    command = request["command"]
    require(command in COMMANDS, "Unsupported workspace command")
    workspace = workspace_root()
    if command.startswith("project-"):
        projects = ProjectStore(workspace)
        if command == "project-list":
            return projects.list()
        if command == "project-show":
            return {"project": projects.read(request["id"]), "runs": projects.runs(request["id"])}
        config = None
        if request.get("case_config") is not None:
            path, before = _input(Library(workspace), request["case_config"])
            config = read_config(path)
            require(read_regular(path) == before, "Case configuration changed while reading")
        return projects.create(request["id"], request["title"], request["goal"], config)
    library = Library(workspace)
    if command == "library-search":
        return library.search(request.get("query", ""), kind=request.get("kind"),
                              status=request.get("status"), scope=request.get("scope"),
                              limit=request.get("limit", 20))
    if command == "library-save":
        _, body = _input(library, request["body_file"])
        return library.save(request["kind"], request["id"], title=request["title"], body=body.decode("utf-8"),
            scope=loads(request["scope"], canonical=False),
            sources=[{"url": url, "locator": "Document URL supplied by operator; passage not specified."}
                     for url in request.get("source_url", [])], expected_revision=request["expected_revision"])
    evidence = [_project_reference(library, path) for path in request.get("evidence", [])]
    if command == "library-review":
        receipt = _receipt(library, request, kind=request["kind"], status=request["status"], evidence=evidence)
        return library.review(request["kind"], request["id"], status=request["status"], actor="operator",
            rationale=request["rationale"], evidence=evidence, review_record=receipt,
            expected_revision=request["expected_revision"])
    source = _project_reference(library, request["source"])
    validation = [_project_reference(library, path) for path in request["validation"]]
    receipt = _receipt(library, request, kind="method", status="reviewed", evidence=[source, *validation])
    return library.register_method(request["id"], source=source, validation=validation, actor="operator",
        rationale=request["rationale"], review_record=receipt, expected_revision=request["expected_revision"])
