"""Repo-local scientific assets; execution and review authority stay with the Host.

A fresh library contains no scientific claims or executable methods. Versions are
immutable evidence, while each asset has one current head. Reading a historical
version does not authorize running historical code. Review receipts and method
validation are produced by trusted application actions, never inferred from a
model's confidence or prose.
"""
from datetime import datetime, timezone
import hashlib
from pathlib import PurePosixPath
import re
from urllib.parse import urlparse

from lqcd_agent.control.coordinator import component, publish_exact, read_regular, sync_directory
from lqcd_agent.control.strict_json import canonical_bytes, closed, digest, digest_value, loads, number, require, text
from .files import WorkspaceFiles


KINDS = {"wiki": "wiki", "skill": "skills", "method": "methods"}
STATUSES = {"candidate", "reviewed", "contested", "superseded"}


def _list(value, label):
    require(type(value) is list, "Invalid " + label)
    return value


class Library(WorkspaceFiles):
    """Small filesystem catalog with scoped references and compare-and-set writes."""

    def __init__(self, workspace):
        super().__init__(workspace, "library")

    def initialize(self):
        """Create empty asset containers without importing any personal material."""
        for relative in ("library", *("library/" + folder for folder in KINDS.values())):
            path = self._path(relative)
            path.mkdir(mode=0o700, exist_ok=True)
            require(path.is_dir() and not path.is_symlink(), "Invalid library directory")
            sync_directory(path.parent)
        with self._locked(create=True):
            pass
        return self.root

    def _directory(self, kind, asset_id):
        require(kind in KINDS, "Unknown asset kind")
        component(asset_id)
        return self._path(f"library/{KINDS[kind]}/{asset_id}")

    def reference(self, relative):
        """Bind project/library evidence without exposing arbitrary workspace files."""
        path = self._path(relative)
        require(PurePosixPath(relative).parts[0] in ("projects", "library"),
                "Evidence must be inside projects or library")
        return {"path": relative, "sha256": hashlib.sha256(read_regular(path)).hexdigest()}

    def _evidence(self, reference):
        closed(reference, ("path", "sha256"))
        digest_value(reference["sha256"])
        path = self._path(reference["path"])
        require(PurePosixPath(reference["path"]).parts[0] in ("projects", "library"),
                "Evidence must be inside projects or library")
        raw = read_regular(path)
        require(hashlib.sha256(raw).hexdigest() == reference["sha256"], "Scientific asset evidence changed")
        return raw

    def _sources(self, sources):
        for source in _list(sources, "asset sources"):
            require(type(source) is dict, "Invalid asset source")
            if "url" in source:
                closed(source, ("url", "locator"))
                url = urlparse(text(source["url"]))
                require(url.scheme in ("https", "http") and bool(url.netloc) and not url.username,
                        "Invalid literature URL")
            else:
                closed(source, ("path", "sha256", "locator"))
                self._evidence({key: source[key] for key in ("path", "sha256")})
            text(source["locator"])

    def _dependency(self, dependency):
        closed(dependency, ("kind", "id", "revision", "sha256"))
        number(dependency["revision"], integer=True, minimum=1)
        digest_value(dependency["sha256"])
        record = self._read(dependency["kind"], dependency["id"], dependency["revision"])
        require(digest(record) == dependency["sha256"], "Asset dependency changed")

    def _read(self, kind, asset_id, revision=None):
        directory = self._directory(kind, asset_id)
        head = loads(read_regular(directory / "current.json"))
        closed(head, ("revision", "sha256"))
        number(head["revision"], integer=True, minimum=1)
        digest_value(head["sha256"])
        selected = head["revision"] if revision is None else revision
        number(selected, integer=True, minimum=1)
        require(selected <= head["revision"], "Asset version is not published")
        version = self._path(str((directory / "versions" / f"{selected:08d}.json").relative_to(self.workspace)))
        record = loads(read_regular(version))
        require(record.get("kind") == kind and record.get("id") == asset_id and record.get("revision") == selected,
                "Asset version identity changed")
        require(record.get("schema_version") == "1" and record.get("status") in STATUSES,
                "Invalid asset record")
        if selected == head["revision"]:
            require(digest(record) == head["sha256"], "Asset head digest changed")
        else:
            # Validate the selected historical version against its next immutable version.
            following = self._read(kind, asset_id, selected + 1)
            require(following["previous_sha256"] == digest(record), "Asset version chain changed")
        return record

    def _changes(self, record):
        changes = []
        for dependency in record["dependencies"]:
            current = self._read(dependency["kind"], dependency["id"])
            if digest(current) != dependency["sha256"] or current["status"] in ("contested", "superseded"):
                changes.append({"dependency": dependency, "current_revision": current["revision"],
                                "current_status": current["status"]})
        return changes

    def _view(self, record):
        return {**record, "sha256": digest(record), "dependency_changes": self._changes(record)}

    def read(self, kind, asset_id, revision=None):
        with self._locked():
            return self._view(self._read(kind, asset_id, revision))

    def _current(self, kind, asset_id, expected_revision):
        number(expected_revision, integer=True)
        directory = self._directory(kind, asset_id)
        try:
            current = self._read(kind, asset_id)
        except FileNotFoundError:
            require(not directory.exists(), "Incomplete scientific asset publication")
            current = None
        require((current["revision"] if current else 0) == expected_revision, "Stale scientific asset revision")
        return current

    def _publish(self, record):
        directory = self._directory(record["kind"], record["id"])
        directory.mkdir(mode=0o700, exist_ok=True)
        versions = directory / "versions"
        require(versions == versions.resolve(), "Redirected asset versions")
        versions.mkdir(mode=0o700, exist_ok=True)
        sync_directory(directory.parent)
        publish_exact(versions / f"{record['revision']:08d}.json", canonical_bytes(record))
        self._atomic(directory / "current.json", canonical_bytes({"revision": record["revision"], "sha256": digest(record)}))
        return self._view(record)

    def save(self, kind, asset_id, *, title, body, scope, sources, dependencies=(), expected_revision=0):
        """Store a candidate. Editing reviewed content always returns it to candidate."""
        self.initialize()
        with self._locked(write=True):
            current = self._current(kind, asset_id, expected_revision)
            text(title)
            text(body)
            require(type(scope) in (dict, list) and bool(scope), "Asset applicability is required")
            self._sources(sources)
            require(type(dependencies) in (list, tuple), "Invalid asset dependencies")
            for dependency in dependencies:
                self._dependency(dependency)
                require((dependency["kind"], dependency["id"]) != (kind, asset_id), "Self-dependent scientific asset")
            record = {"schema_version": "1", "kind": kind, "id": asset_id,
                      "revision": expected_revision + 1, "previous_sha256": digest(current) if current else None,
                      "title": title, "body": body, "scope": scope, "sources": sources,
                      "dependencies": list(dependencies), "status": "candidate", "review": None,
                      "implementation": current["implementation"] if current else None,
                      "updated_at": datetime.now(timezone.utc).isoformat()}
            return self._publish(record)

    def _review(self, current, *, status, rationale, evidence, actor, review_record):
        require(status in STATUSES - {"candidate"}, "Invalid scientific asset review state")
        text(actor)
        text(rationale)
        for reference in _list(evidence, "review evidence"):
            self._evidence(reference)
        receipt = loads(self._evidence(review_record))
        expected = {"kind": current["kind"], "id": current["id"], "revision": current["revision"],
                    "status": status, "actor": actor, "rationale": rationale, "evidence": evidence}
        require(receipt == expected, "Review receipt does not match the scientific asset decision")
        if status == "reviewed":
            require(bool(current["sources"] or evidence), "Reviewed knowledge needs supporting sources or evidence")
            require(not self._changes(current), "Asset dependencies need review")
            if current["kind"] == "method":
                require(current["implementation"] is not None, "Method must be registered with numerical validation")
        return {**current, "revision": current["revision"] + 1, "previous_sha256": digest(current),
                "status": status, "updated_at": datetime.now(timezone.utc).isoformat(),
                "review": {"actor": actor, "rationale": rationale, "evidence": evidence, "record": review_record}}

    def review(self, kind, asset_id, *, status, rationale, evidence, actor, review_record, expected_revision):
        """Apply a Host-owned review receipt; this storage API does not grant authority."""
        with self._locked(write=True):
            current = self._current(kind, asset_id, expected_revision)
            require(current is not None, "Unknown scientific asset")
            if status == "reviewed" and kind == "method" and current["implementation"] is not None:
                implementation = current["implementation"]
                self._evidence({key: implementation[key] for key in ("path", "sha256")})
                self._validation(implementation["validation"], implementation["sha256"])
            return self._publish(self._review(current, status=status, rationale=rationale, evidence=evidence,
                                              actor=actor, review_record=review_record))

    def _validation(self, references, source_digest):
        require(type(references) is list and references, "Method needs numerical validation evidence")
        for reference in references:
            report = loads(self._evidence(reference))
            require(type(report) is dict and report.get("source_sha256") == source_digest and
                    report.get("passed") is True and type(report.get("checks")) is list and report["checks"] and
                    all(type(check) is dict and bool(check.get("name")) and check.get("passed") is True
                        for check in report["checks"]), "Method validation does not pass for this exact source")

    def register_method(self, asset_id, *, source, validation, actor, review_record, rationale, expected_revision):
        """Publish one current implementation after a bound validation/review decision."""
        with self._locked(write=True):
            current = self._current("method", asset_id, expected_revision)
            require(current is not None, "Create the method candidate before registration")
            code = self._evidence(source)
            require(PurePosixPath(source["path"]).parts[0] == "projects" and source["path"].endswith(".py"),
                    "Method source must be project Python code")
            try:
                compile(code, source["path"], "exec")
            except SyntaxError as error:
                raise ValueError("Method source is not valid Python") from error
            self._validation(validation, source["sha256"])
            destination = self._directory("method", asset_id) / "implementation.py"
            implementation = {"path": str(destination.relative_to(self.workspace)), "sha256": source["sha256"],
                              "source": source, "validation": validation}
            checked = {**current, "implementation": implementation}
            record = self._review(checked, status="reviewed", rationale=rationale, evidence=[source, *validation],
                                  actor=actor, review_record=review_record)
            # The previous version is the original candidate, not the prepared implementation.
            record["previous_sha256"] = digest(current)
            self._atomic(destination, code)
            return self._publish(record)

    def method_snapshot(self, asset_id):
        """Read one reviewed record and its verified bytes under the same shared lock."""
        with self._locked():
            record = self._read("method", asset_id)
            require(record["status"] == "reviewed" and not self._changes(record), "Method is not currently reusable")
            implementation = record["implementation"]
            require(type(implementation) is dict, "Missing method implementation")
            raw = self._evidence({key: implementation[key] for key in ("path", "sha256")})
            self._validation(implementation["validation"], implementation["sha256"])
            return self._view(record), raw

    def _records(self):
        for kind, folder in KINDS.items():
            parent = self._path("library/" + folder)
            for directory in sorted(parent.iterdir()):
                if directory.name.startswith(".") or directory.name == "README.md":
                    continue
                require(directory.is_dir() and directory == directory.resolve(), "Invalid asset catalog member")
                yield self._read(kind, directory.name)

    def _empty(self):
        if not self.root.exists():
            self._path("library")
            return True
        for folder in KINDS.values():
            parent = self._path("library/" + folder)
            if parent.exists():
                require(parent.is_dir(), "Invalid library directory")
                if any(not item.name.startswith(".") and item.name != "README.md" for item in parent.iterdir()):
                    return False
        return True

    def search(self, query="", *, kind=None, status=None, scope=None, limit=20):
        """Search current metadata and text; candidate status remains visible in every hit."""
        require(kind is None or kind in KINDS, "Unknown asset search kind")
        require(status is None or status in STATUSES, "Unknown asset search status")
        require(type(query) is str and (scope is None or type(scope) is str), "Invalid asset query")
        number(limit, integer=True, minimum=1)
        require(limit <= 100, "Asset search limit exceeds 100")
        if self._empty():
            return []
        tokens = re.findall(r"\w+", query.casefold())
        hits = []
        with self._locked():
            for record in self._records():
                if kind is not None and record["kind"] != kind or status is not None and record["status"] != status:
                    continue
                scope_text = canonical_bytes(record["scope"]).decode().casefold()
                if scope is not None and scope.casefold() not in scope_text:
                    continue
                haystack = " ".join((record["title"], record["body"], scope_text)).casefold()
                if all(token in haystack for token in tokens):
                    hits.append((sum(haystack.count(token) for token in tokens), self._view(record)))
        hits.sort(key=lambda hit: (-hit[0], hit[1]["kind"], hit[1]["id"]))
        return [hit[1] for hit in hits[:limit]]

    def dependents(self, kind, asset_id):
        """List current assets that refer to a target; never rerun or rewrite them."""
        self._directory(kind, asset_id)
        if self._empty():
            return []
        with self._locked():
            return [self._view(record) for record in self._records()
                    if any((ref["kind"], ref["id"]) == (kind, asset_id) for ref in record["dependencies"])]
