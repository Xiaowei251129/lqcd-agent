"""Persistent research projects and read-only copies of verified Run evidence.

Project metadata is scientific context, not a second execution authority. A Run
capture can retain preliminary results, but cannot resume execution or approve a
scientific result. Only registered artifact members and their bound scientific
sidecars are copied; raw datasets and arbitrary workspace trees are not backups.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import PurePosixPath

from lqcd_agent.archive import DOMAIN_ARTIFACTS, MAX_BYTES, MAX_MEMBERS
from lqcd_agent.control.coordinator import component, publish_exact, read_regular, sync_directory
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, closed, digest, digest_value, loads, number, require, text
from lqcd_agent.inspection import RunSnapshot, read_snapshot
from .files import WorkspaceFiles


_UNSET = object()
MAX_PROJECT_BYTES = 128 * 1024


def _relative(value):
    text(value)
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and "\\" not in value and "\0" not in value and
            all(part not in (".", "..") for part in path.parts), "Invalid captured evidence path")
    require(not any(part == ".env" or part.startswith(".env.") or part in (".git", ".aws", "auth.json", "credentials.json")
                    for part in path.parts), "Private configuration is not scientific evidence")
    return path


class UnregisteredEvidence(ControlIntegrityError):
    """The requested digest is absent from this project's verified registrations."""


class ProjectStore(WorkspaceFiles):
    def __init__(self, workspace):
        super().__init__(workspace, "projects")

    def _initialize(self):
        root = self._path("projects")
        root.mkdir(mode=0o700, exist_ok=True)
        require(root.is_dir(), "Invalid project root")
        sync_directory(root.parent)
        with self._locked(create=True):
            pass

    def _directory(self, project_id):
        component(project_id)
        require(len(project_id) <= 128, "Project identifier is too long")
        return self._path("projects/" + project_id)

    def _validate(self, record):
        closed(record, ("schema_version", "id", "revision", "previous_sha256", "title", "goal", "case_config", "updated_at"))
        require(record["schema_version"] == "1", "Unsupported project metadata version")
        self._directory(record["id"])
        number(record["revision"], integer=True, minimum=1)
        digest_value(record["previous_sha256"], nullable=True)
        text(record["title"])
        text(record["goal"])
        text(record["updated_at"])
        require(len(record["title"]) <= 500 and len(record["goal"]) <= 32000, "Project text exceeds its limit")
        require(record["case_config"] is None or type(record["case_config"]) is dict, "Project case configuration must be an object")
        require(len(canonical_bytes(record)) <= MAX_PROJECT_BYTES, "Project metadata exceeds 128 KiB")
        return record

    def _read(self, project_id, revision=None):
        directory = self._directory(project_id)
        head = loads(read_regular(directory / "project.json"))
        closed(head, ("revision", "sha256"))
        number(head["revision"], integer=True, minimum=1)
        digest_value(head["sha256"])
        selected = head["revision"] if revision is None else revision
        number(selected, integer=True, minimum=1)
        require(selected <= head["revision"], "Project version is not published")
        path = self._path(f"projects/{project_id}/versions/{selected:08d}.json")
        require(path.stat().st_size <= MAX_PROJECT_BYTES, "Project metadata exceeds 128 KiB")
        record = self._validate(loads(read_regular(path)))
        require(record["id"] == project_id and record["revision"] == selected, "Project version identity changed")
        if selected == head["revision"]:
            require(digest(record) == head["sha256"], "Project metadata digest changed")
        else:
            following = self._read(project_id, selected + 1)
            require(following["previous_sha256"] == digest(record), "Project version chain changed")
        return record

    def _publish(self, record):
        self._validate(record)
        directory = self._directory(record["id"])
        directory.mkdir(mode=0o700, exist_ok=True)
        versions = self._path(f"projects/{record['id']}/versions")
        versions.mkdir(mode=0o700, exist_ok=True)
        sync_directory(directory.parent)
        publish_exact(versions / f"{record['revision']:08d}.json", canonical_bytes(record))
        self._atomic(directory / "project.json", canonical_bytes({"revision": record["revision"], "sha256": digest(record)}))
        return {**record, "sha256": digest(record)}

    def create(self, project_id, title, goal, case_config=None):
        self._initialize()
        with self._locked(write=True):
            require(not self._directory(project_id).exists(), "Project already exists")
            return self._publish({"schema_version": "1", "id": project_id, "revision": 1, "previous_sha256": None,
                                  "title": title, "goal": goal, "case_config": case_config,
                                  "updated_at": datetime.now(timezone.utc).isoformat()})

    def read(self, project_id, revision=None):
        with self._locked():
            record = self._read(project_id, revision)
            return {**record, "sha256": digest(record)}

    def list(self):
        if not self.root.exists():
            self._path("projects")
            return []
        # The source distribution may contain only a README and empty placeholders.
        entries = [path for path in self._path("projects").iterdir()
                   if not path.name.startswith(".") and path.name != "README.md"]
        if not entries:
            return []
        with self._locked():
            return [{**record, "sha256": digest(record)} for record in
                    (self._read(path.name) for path in sorted(entries))]

    def revise(self, project_id, *, expected_digest, title=None, goal=None, case_config=_UNSET):
        digest_value(expected_digest)
        with self._locked(write=True):
            current = self._read(project_id)
            require(digest(current) == expected_digest, "Stale project revision")
            record = {**current, "revision": current["revision"] + 1, "previous_sha256": digest(current),
                      "title": current["title"] if title is None else title,
                      "goal": current["goal"] if goal is None else goal,
                      "case_config": current["case_config"] if case_config is _UNSET else case_config,
                      "updated_at": datetime.now(timezone.utc).isoformat()}
            return self._publish(record)

    def _contributions(self, project_id):
        directory = self._path(f"projects/{project_id}/contributions")
        if not directory.exists():
            return []
        head = closed(loads(read_regular(directory / "current.json")), ("revision", "sha256"))
        number(head["revision"], integer=True, minimum=1)
        digest_value(head["sha256"])
        records, identifier = [], head["sha256"]
        for revision in range(head["revision"], 0, -1):
            raw = read_regular(self._path(f"projects/{project_id}/contributions/{identifier}.json"))
            require(len(raw) <= 65536 and sha256(raw).hexdigest() == identifier,
                    "Scientific contribution digest changed")
            record = closed(loads(raw), ("schema_version", "project_id", "project_revision", "project_sha256",
                "revision", "previous_sha256", "key", "author", "kind", "body", "evidence_sha256", "run", "created_at"))
            require(record["schema_version"] == "1" and record["project_id"] == project_id and
                    record["revision"] == revision and record["author"] == "operator",
                    "Scientific contribution chain changed")
            project = self._read(project_id, record["project_revision"])
            require(digest(project) == record["project_sha256"], "Scientific contribution Project changed")
            records.append({**record, "sha256": identifier})
            identifier = record["previous_sha256"]
            digest_value(identifier, nullable=True)
        require(identifier is None, "Scientific contribution chain changed")
        return list(reversed(records))

    def contribute(self, project_id, *, expected_digest, key, kind, body, evidence_sha256=(), run=None):
        """Record operator scientific input; this never grants execution authority."""
        digest_value(expected_digest)
        component(key)
        require(len(key) <= 128 and kind in ("scientific_comment", "question", "evidence"),
                "Invalid scientific contribution")
        text(body)
        require(body.strip() and len(body) <= 16000, "Scientific contribution needs bounded text")
        require(type(evidence_sha256) in (list, tuple) and len(evidence_sha256) <= 16 and
                all(type(value) is str for value in evidence_sha256), "Invalid contribution evidence")
        require(len(set(evidence_sha256)) == len(evidence_sha256), "Duplicate contribution evidence")
        references = sorted(evidence_sha256)
        require(kind != "evidence" or bool(references), "Evidence input needs registered references")
        for identifier in references:
            # Registered project evidence is immutable; no arbitrary path or URL is read.
            self.evidence(project_id, identifier)
        if run is not None:
            closed(run, ("host", "case_id", "run_id", "execution_head"))
            for name in ("host", "case_id", "run_id"):
                component(run[name])
            digest_value(run["execution_head"])
        intent = {"project_sha256": expected_digest, "key": key, "kind": kind, "body": body,
                  "evidence_sha256": references, "run": run}
        with self._locked(write=True):
            current = self._read(project_id)
            records = self._contributions(project_id)
            original = next((row for row in records if row["key"] == key), None)
            if original is not None:
                require(all(original[name] == value for name, value in intent.items()),
                        "Contribution key conflicts with the original input")
                return original
            require(digest(current) == expected_digest, "Stale project revision")
            if run is not None:
                run_key = digest({name: run[name] for name in ("host", "case_id", "run_id")})
                self._run_manifest(project_id, run_key)
            record = {"schema_version": "1", "project_id": project_id,
                "project_revision": current["revision"], **intent, "revision": len(records) + 1,
                "previous_sha256": records[-1]["sha256"] if records else None,
                "author": "operator", "created_at": datetime.now(timezone.utc).isoformat()}
            require(len(canonical_bytes(record)) <= 65536, "Scientific contribution is too large")
            directory = self._path(f"projects/{project_id}/contributions")
            directory.mkdir(mode=0o700, exist_ok=True)
            identifier = digest(record)
            publish_exact(directory / (identifier + ".json"), canonical_bytes(record))
            self._atomic(directory / "current.json", canonical_bytes({"revision": record["revision"], "sha256": identifier}))
            sync_directory(directory.parent)
            return {**record, "sha256": identifier}

    def contributions(self, project_id, *, run=None):
        """Read attributed input for the next attempt, leaving existing Run artifacts unchanged."""
        if run is not None:
            closed(run, ("host", "case_id", "run_id"))
        with self._locked():
            self._read(project_id)
            records = self._contributions(project_id)
            return [row for row in records if run is None or row["run"] is None or
                    all(row["run"][name] == value for name, value in run.items())]

    @staticmethod
    def _source(path, scope, expected, remaining):
        digest_value(expected)
        require(path == path.resolve() and scope == scope.resolve() and path.is_relative_to(scope),
                "Evidence escaped its registered producer scope")
        require(path.stat().st_size <= remaining, "Project evidence capture exceeds 256 MiB")
        raw = read_regular(path)
        require(len(raw) <= remaining and sha256(raw).hexdigest() == expected, "Registered project evidence changed")
        return raw

    def _capture(self, supplied):
        require(isinstance(supplied, RunSnapshot), "Capture requires a verified Run snapshot")
        snapshot = read_snapshot(supplied.host, supplied.locator)
        require(snapshot.control == supplied.control and snapshot.closure == supplied.closure and
                snapshot.state["execution_head"] == supplied.state["execution_head"],
                "Run changed before project capture; inspect again")
        created = snapshot.records.values[0]
        goal_raw = self._source(snapshot.root / "root_goal.json", snapshot.root,
                                created["root_goal_reference"]["sha256"], MAX_BYTES)
        goal = loads(goal_raw)
        require(goal.get("workspace") == str(self.workspace), "Run belongs to another project workspace")
        project_id = goal.get("project_id")
        self._directory(project_id)
        project = self._read(project_id, goal.get("project_revision"))
        require(type(goal.get("project_revision")) is int and digest(project) == goal.get("project_sha256"),
                "Run project revision binding changed")
        frozen = goal.get("project_snapshot")
        require(frozen == project or frozen == {**project, "sha256": digest(project)},
                "Frozen project snapshot does not match its original version")
        blobs, entries, sources = {}, [], {}
        size = 0

        def collect(path, scope, expected, *, source, name, artifact_id=None, slot=None, attempt_id=None, current=False):
            nonlocal size
            _relative(name)
            require(len(entries) < MAX_MEMBERS, "Too many project evidence members")
            raw = self._source(path, scope, expected, MAX_BYTES - size)
            if expected not in blobs:
                size += len(raw)
                blobs[expected] = raw
            sources[path] = (scope, expected)
            entries.append({"source": source, "name": name, "artifact_id": artifact_id, "slot": slot,
                            "attempt_id": attempt_id, "current": current, "sha256": expected, "size_bytes": len(raw)})
            return raw

        for label, reference in (("root_goal", created["root_goal_reference"]),
                                 ("input_snapshot", created["input_snapshot_reference"])):
            require(reference["reference"] == label + ".json", "Unexpected registered Run input")
            collect(snapshot.root / reference["reference"], snapshot.root, reference["sha256"],
                    source="input", name=reference["reference"])
        index = loads(read_regular(snapshot.root / "artifact_index.json"))
        pointers = [record["pointer"] for line in read_regular(snapshot.root / "artifact_history.jsonl").splitlines()
                    if (record := loads(line))["event"] == "registered"]
        for pointer in pointers:
            component(pointer["attempt_id"])
            attempt = snapshot.root / "attempts" / pointer["attempt_id"]
            current = index["current"][pointer["slot"]]
            is_current = current is not None and current["artifact_id"] == pointer["artifact_id"]
            for member in pointer["members"]:
                relative = _relative(member["canonical_path"])
                raw = collect(snapshot.root / relative, attempt, member["sha256"], source="artifact",
                              name=member["canonical_path"], artifact_id=pointer["artifact_id"], slot=pointer["slot"],
                              attempt_id=pointer["attempt_id"], current=is_current)
                if member["logical_name"] not in DOMAIN_ARTIFACTS:
                    continue
                domain = loads(raw).get("domain_result", {})
                require(type(domain) is dict, "Invalid scientific artifact envelope")
                scope = snapshot.host / "domain" / pointer["attempt_id"] / snapshot.locator["case_id"] / snapshot.locator["run_id"]
                for relative, expected in sorted(domain.get("member_digests", {}).items()):
                    relative = _relative(relative)
                    collect(snapshot.host / relative, scope, expected, source="scientific", name=str(relative),
                            artifact_id=pointer["artifact_id"], slot=pointer["slot"],
                            attempt_id=pointer["attempt_id"], current=is_current)
        after = read_snapshot(snapshot.host, snapshot.locator)
        require(after.control == snapshot.control and after.closure == snapshot.closure,
                "Run changed during project capture; inspect again")
        for path, (scope, expected) in sources.items():
            self._source(path, scope, expected, MAX_BYTES)
        outcome, origin = None, None
        terminal = index['current']['terminal']
        if terminal is not None:
            member = next(item for item in terminal['members'] if item['logical_name'] == 'memory_update.json')
            raw = read_regular(snapshot.root / member['canonical_path'])
            require(sha256(raw).hexdigest() == member['sha256'], 'Terminal research outcome changed')
            classification = loads(raw)
            outcome, origin = classification['scientific_outcome'], classification['decision_origin']
            require(outcome in ('supported', 'qualified', 'inconclusive') and origin in ('system', 'human'),
                    'Invalid research conclusion provenance')
        closed_run = snapshot.state['run_status'] in ('completed', 'failed', 'halted') and snapshot.closure is not None
        if terminal is None and closed_run:
            outcome, origin = 'inconclusive', 'system'
        manifest = {"schema_version": "1", "kind": "project_run_snapshot", "project_id": project_id,
                    "project_revision": project["revision"], "project_sha256": digest(project),
                    "host": snapshot.host.name.removeprefix("lqcd-agent-host-"), "run_locator": snapshot.locator,
                    "run_status": snapshot.state["run_status"], "execution_head": snapshot.state["execution_head"],
                    "execution_event_index": snapshot.records.values[-1]["event_index"],
                    "scientific_outcome": outcome, "decision_origin": origin, "preliminary": not closed_run,
                    "outcome_source": "scientific_terminal" if terminal is not None else "control_closure" if closed_run else None,
                    "research_task": goal.get("research_task"),
                    "resumable": False, "state": snapshot.state, "evidence": entries,
                    "limitations": ["Read-only evidence copy; no execution authority or recovery database.",
                                    "Raw numerical datasets are not automatically backed up."]}
        manifest['workflow'] = goal['workflow']
        if goal['workflow'] == 'intake':
            from lqcd_agent.inspection import read_preparation
            selected = read_preparation(snapshot.root)
            manifest['preparation'] = selected[0] if selected else None
        return manifest, blobs

    def capture_run(self, snapshot):
        """Retain a verified, possibly preliminary Run snapshot in its bound project."""
        with self._locked(write=True):
            manifest, blobs = self._capture(snapshot)
            project_id = manifest["project_id"]
            directory = self._directory(project_id)
            evidence = self._path(f"projects/{project_id}/evidence")
            evidence.mkdir(mode=0o700, exist_ok=True)
            run_key = digest({"host": manifest["host"], **manifest["run_locator"]})
            run = self._path(f"projects/{project_id}/runs/{run_key}")
            run.parent.mkdir(mode=0o700, exist_ok=True)
            require(run.parent == run.parent.resolve(), "Redirected project Run directory")
            run.mkdir(mode=0o700, exist_ok=True)
            versions = self._path(f"projects/{project_id}/runs/{run_key}/snapshots")
            versions.mkdir(mode=0o700, exist_ok=True)
            current = run / "current.json"
            if current.exists():
                old = self._run_manifest(project_id, run_key)
                require(old["execution_event_index"] <= manifest["execution_event_index"], "Project Run snapshot cannot roll back")
                if old["execution_event_index"] == manifest["execution_event_index"]:
                    require(old["execution_head"] == manifest["execution_head"], "Project Run history diverged")
            for identifier, raw in sorted(blobs.items()):
                publish_exact(evidence / identifier, raw)
            identifier = digest(manifest)
            publish_exact(versions / (identifier + ".json"), canonical_bytes(manifest))
            self._atomic(current, canonical_bytes({"sha256": identifier, "execution_head": manifest["execution_head"]}))
            sync_directory(directory)
            return {**manifest, "sha256": identifier}

    def _manifest(self, project_id, run_key, identifier):
        digest_value(run_key)
        digest_value(identifier)
        path = self._path(f"projects/{project_id}/runs/{run_key}/snapshots/{identifier}.json")
        require(path.stat().st_size <= MAX_BYTES, "Project Run snapshot is too large")
        raw = read_regular(path)
        require(len(raw) <= MAX_BYTES and sha256(raw).hexdigest() == identifier, "Project Run snapshot digest changed")
        manifest = loads(raw)
        require(manifest.get("schema_version") == "1" and manifest.get("kind") == "project_run_snapshot" and
                manifest.get("project_id") == project_id and manifest.get("resumable") is False and
                digest({"host": manifest["host"], **manifest["run_locator"]}) == run_key,
                "Project Run snapshot identity changed")
        original = self._read(project_id, manifest["project_revision"])
        require(digest(original) == manifest["project_sha256"], "Project Run metadata binding changed")
        return manifest

    def _run_manifest(self, project_id, run_key):
        path = self._path(f"projects/{project_id}/runs/{run_key}/current.json")
        head = loads(read_regular(path))
        closed(head, ("sha256", "execution_head"))
        manifest = self._manifest(project_id, run_key, head["sha256"])
        require(manifest["execution_head"] == head["execution_head"], "Project Run snapshot head changed")
        return {**manifest, "sha256": head["sha256"]}

    def runs(self, project_id):
        with self._locked():
            self._read(project_id)
            root = self._path(f"projects/{project_id}/runs")
            if not root.exists():
                return []
            return [self._run_manifest(project_id, path.name) for path in sorted(root.iterdir())]

    def evidence(self, project_id, identifier):
        """Read only content referenced by a published snapshot of this project."""
        digest_value(identifier)
        with self._locked():
            self._read(project_id)
            runs = self._path(f"projects/{project_id}/runs")
            found = False
            if runs.exists():
                for run in sorted(runs.iterdir()):
                    root = self._path(f"projects/{project_id}/runs/{run.name}/snapshots")
                    for path in sorted(root.iterdir()):
                        require(path.suffix == ".json", "Unknown project Run snapshot member")
                        manifest = self._manifest(project_id, run.name, path.stem)
                        if any(member["sha256"] == identifier for member in manifest["evidence"]):
                            found = True
                            break
                    if found:
                        break
            if not found:
                raise UnregisteredEvidence("Evidence is not registered to this project")
            path = self._path(f"projects/{project_id}/evidence/{identifier}")
            require(path.stat().st_size <= MAX_BYTES, "Project evidence is too large")
            raw = read_regular(path)
            require(sha256(raw).hexdigest() == identifier, "Project evidence digest changed")
            return raw
