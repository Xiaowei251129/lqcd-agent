"""Scientific assets remain empty until explicitly acquired and verified."""
from concurrent.futures import ThreadPoolExecutor
import hashlib

import pytest

from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes
from lqcd_agent.research.library import Library


def source():
    return [{"url": "https://arxiv.org/abs/2505.18430", "locator": "Appendix A; one tested ensemble"}]


def candidate(library, kind="wiki", asset_id="matrix-ratio", **overrides):
    arguments = {"title": "Correlated matrix-element ratio", "body": "Preserve shared jackknife correspondence.",
                 "scope": {"ensemble": "fixture", "observable": "matrix ratio"}, "sources": source()}
    arguments.update(overrides)
    return library.save(kind, asset_id, **arguments)


def project_file(library, filename, value):
    path = library.workspace / "projects" / "study" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else canonical_bytes(value))
    return library.reference(str(path.relative_to(library.workspace)))


def review(library, asset, *, status="reviewed", evidence=None, rationale="Supported only for the stated fixture."):
    evidence = evidence or []
    receipt = {"kind": asset["kind"], "id": asset["id"], "revision": asset["revision"],
               "status": status, "actor": "host-reviewer", "rationale": rationale, "evidence": evidence}
    reference = project_file(library, f"review-{asset['id']}-{asset['revision']}.json", receipt)
    return {"status": status, "actor": "host-reviewer", "rationale": rationale, "evidence": evidence,
            "review_record": reference, "expected_revision": asset["revision"]}


def test_new_library_is_empty_and_initialization_is_idempotent(tmp_path):
    library = Library(tmp_path)
    assert library.search("TMD") == []
    assert not library.root.exists()
    library.initialize()
    library.initialize()
    assert library.search() == []
    assert {p.name for p in library.root.iterdir()} == {"wiki", "skills", "methods", ".lock"}
    assert all(not list((library.root / name).iterdir()) for name in ("wiki", "skills", "methods"))


def test_candidate_review_edit_and_version_chain(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library)
    assert library.search("jackknife", scope="fixture")[0]["status"] == "candidate"
    assert library.search(status="reviewed") == []
    with pytest.raises(ControlIntegrityError, match="Stale"):
        candidate(library)
    reviewed = library.review("wiki", asset["id"], **review(library, asset))
    assert reviewed["status"] == "reviewed"
    edited = candidate(library, expected_revision=2, body="A narrower, provisional claim.")
    assert edited["status"] == "candidate" and edited["review"] is None
    assert library.read("wiki", asset["id"], 2)["sha256"] == reviewed["sha256"]
    version = library.root / "wiki" / asset["id"] / "versions" / "00000001.json"
    version.write_bytes(version.read_bytes().replace(b"jackknife", b"bootstrap"))
    with pytest.raises(ControlIntegrityError, match="chain changed"):
        library.read("wiki", asset["id"], 1)


def test_review_requires_exact_host_receipt_and_bound_evidence(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library)
    report = project_file(library, "evidence.json", {"sample_count": 20})
    arguments = review(library, asset, evidence=[report])
    with pytest.raises(ControlIntegrityError, match="receipt"):
        library.review("wiki", asset["id"], **{**arguments, "actor": "model-claims-approval"})
    (tmp_path / report["path"]).write_bytes(canonical_bytes({"sample_count": 2}))
    with pytest.raises(ControlIntegrityError, match="evidence changed"):
        library.review("wiki", asset["id"], **arguments)
    assert library.read("wiki", asset["id"])["status"] == "candidate"


def method_inputs(library, asset, *, passed=True, digest_override=None):
    code = b"def ratio(a, b):\n    return [x / y for x, y in zip(a, b, strict=True)]\n"
    code_ref = project_file(library, "analysis.py", code)
    report = project_file(library, "validation.json", {"source_sha256": digest_override or code_ref["sha256"],
                            "passed": passed, "checks": [{"name": "known correlated fixture", "passed": passed}]})
    arguments = review(library, asset, evidence=[code_ref, report])
    arguments.pop("status")
    arguments.pop("evidence")
    return {**arguments, "source": code_ref, "validation": [report]}


def test_method_registration_binds_validation_to_exact_source(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library, "method", "correlated-ratio")
    for overrides in ({"passed": False}, {"digest_override": "0" * 64}):
        with pytest.raises(ControlIntegrityError, match="validation does not pass"):
            library.register_method(asset["id"], **method_inputs(library, asset, **overrides))
    assert library.read("method", asset["id"])["status"] == "candidate"
    with pytest.raises(ControlIntegrityError, match="registered"):
        library.review("method", asset["id"], **review(library, asset))
    registered = library.register_method(asset["id"], **method_inputs(library, asset))
    record, code = library.method_snapshot(asset["id"])
    assert record == registered
    assert hashlib.sha256(code).hexdigest() == record["implementation"]["sha256"]
    implementation = library.workspace / record["implementation"]["path"]
    implementation.write_text("def ratio(a, b): return 0\n")
    with pytest.raises(ControlIntegrityError, match="evidence changed"):
        library.method_snapshot(asset["id"])


def test_dependency_changes_are_visible_without_rewriting_dependents(tmp_path):
    library = Library(tmp_path)
    knowledge = candidate(library)
    dependency = {key: knowledge[key] for key in ("kind", "id", "revision", "sha256")}
    skill = candidate(library, "skill", "check-ratio", dependencies=[dependency])
    assert skill["dependency_changes"] == []
    updated = library.review("wiki", knowledge["id"], **review(library, knowledge, status="contested"))
    dependent = library.dependents("wiki", knowledge["id"])[0]
    assert dependent["sha256"] == skill["sha256"]
    assert dependent["dependency_changes"][0]["current_status"] == updated["status"]
    with pytest.raises(ControlIntegrityError, match="dependencies need review"):
        library.review("skill", skill["id"], **review(library, skill))


@pytest.mark.parametrize("path", ["../private.json", "/etc/passwd", "projects/../.env", "projects//secret", "src/key.json"])
def test_evidence_paths_cannot_escape_scientific_assets(tmp_path, path):
    library = Library(tmp_path)
    with pytest.raises(ControlIntegrityError):
        library.reference(path)


def test_symlinks_and_duplicate_json_are_rejected(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library)
    foreign = tmp_path / "private.json"
    foreign.write_text("secret")
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "link.json").symlink_to(foreign)
    with pytest.raises(ControlIntegrityError, match="Redirected"):
        library.reference("projects/link.json")
    with pytest.raises(ControlIntegrityError):
        candidate(library, asset_id="../outside")
    head = library.root / "wiki" / asset["id"] / "current.json"
    head.write_bytes(b'{"revision":1,"revision":1,"sha256":"' + b"0" * 64 + b'"}')
    with pytest.raises(ControlIntegrityError, match="Duplicate"):
        library.read("wiki", asset["id"])


def test_concurrent_edits_cannot_silently_overwrite(tmp_path):
    library = Library(tmp_path)
    candidate(library)

    def update(body):
        try:
            return candidate(Library(tmp_path), expected_revision=1, body=body)
        except ControlIntegrityError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ("First change", "Second change")))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, ControlIntegrityError) for result in results) == 1
    assert library.read("wiki", "matrix-ratio")["revision"] == 2
