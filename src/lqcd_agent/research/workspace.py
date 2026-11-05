"""Explicit operator actions on local research assets, without model execution."""
from hashlib import sha256
from pathlib import Path, PurePosixPath

from lqcd_agent.configuration import read_config
from lqcd_agent.control.coordinator import read_regular
from lqcd_agent.control.strict_json import loads, require
from lqcd_agent.settings import workspace_root
from .library import Library
from .projects import ProjectStore
from .methods import assess_method


COMMANDS = ("project-create", "project-list", "project-show", "project-contribute", "library-search", "library-save",
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


def execute_workspace(request):
    """Dispatch operator actions; method checks use the sandbox without model calls."""
    command = request["command"]
    require(command in COMMANDS, "Unsupported workspace command")
    workspace = workspace_root()
    if command.startswith("project-"):
        projects = ProjectStore(workspace)
        if command == "project-list":
            return projects.list()
        if command == "project-show":
            return {"project": projects.read(request["id"]), "runs": projects.runs(request["id"]),
                    "contributions": projects.contributions(request["id"])}
        if command == "project-contribute":
            return projects.contribute(request["id"], expected_digest=request["expected_digest"],
                key=request["key"], kind=request.get("kind", "scientific_comment"), body=request["body"],
                evidence_sha256=request.get("evidence", []))
        config = None
        if request.get("case_config") is not None:
            path, before = _input(Library(workspace), request["case_config"])
            config = read_config(path)
            require(read_regular(path) == before, "Case configuration changed while reading")
        if request.get("data_path") is not None:
            relative = request["data_path"]
            path = PurePosixPath(relative)
            require(path.parts and path.parts[0] == "raw_data" and len(path.parts) > 1 and
                    path.as_posix() == relative and not any(part.startswith(".") for part in path.parts) and
                    "\\" not in relative, "Data must be a workspace-relative file under raw_data/")
            config = {**(config or {}), "raw_data_path": relative}
        if request.get("python") is not None:
            require(Path(request["python"]).is_absolute(), "Select an absolute scientific interpreter")
            config = {**(config or {}), "generated_program": {
                **((config or {}).get("generated_program") or {}), "python": request["python"]}}
        if request.get("source_kind") is not None:
            source_kind = request["source_kind"]
            require(type(source_kind) is str and source_kind.strip() and len(source_kind) <= 200,
                    "Declare bounded data provenance")
            config = {**(config or {}), "source_kind": source_kind}
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
        return library.review(request["kind"], request["id"], status=request["status"], actor="operator",
            rationale=request["rationale"], evidence=evidence, expected_revision=request["expected_revision"])
    source = _project_reference(library, request["source"])
    assessment = assess_method(library._evidence(source), request["family"], request["python"])
    return library.register_method(request["id"], source=source, assessment=assessment, actor="operator",
        rationale=request["rationale"], expected_revision=request["expected_revision"])
