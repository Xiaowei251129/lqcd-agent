"""Scientific assets remain empty until explicitly acquired and verified."""
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sys

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
    return {"status": status, "actor": "operator", "rationale": rationale, "evidence": evidence or [],
            "expected_revision": asset["revision"]}


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


def test_review_receipt_records_origin_and_bound_evidence(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library)
    report = project_file(library, "evidence.json", {"sample_count": 20})
    arguments = review(library, asset, evidence=[report])
    with pytest.raises(ControlIntegrityError, match="reviewer identity"):
        library.review("wiki", asset["id"], **{**arguments, "actor": "model-claims-approval"})
    (tmp_path / report["path"]).write_bytes(canonical_bytes({"sample_count": 2}))
    with pytest.raises(ControlIntegrityError, match="evidence changed"):
        library.review("wiki", asset["id"], **arguments)
    assert library.read("wiki", asset["id"])["status"] == "candidate"


def method_program():
    return b'''import json,sys,math
p=json.load(open(sys.argv[1]));P=p['target_pz'];B=p['target_bT']
records={(r['pz'],r['bT'],r['bz'],r['sample_id']):r for r in p['records']}
required={(0,B,0),(P,0,0),(0,0,0)}
if p['omit_reference'] or not required<={(a,b,c) for a,b,c,_ in records}:
 print(json.dumps(dict(status='needs_more_info',results=[])));sys.exit()
rows=[]
for r in p['records']:
 if (r['pz'],r['bT'])!=(P,B) or r['bz'] not in p['bz_values']:continue
 sid=r['sample_id'];bz=r['bz']
 for mode in ('mode2','mode3'):
  keys=[(P,B,bz,sid),(0,B,0,sid)]
  if mode=='mode3':keys += [(P,0,0,sid),(0,0,0,sid)]
  values=[records.get(k) for k in keys]
  valid=all(v and v['success'] and v['real'] is not None and v['imag'] is not None for v in values)
  z=[complex(v['real'],v['imag']) for v in values] if valid else []
  valid=valid and z[1]!=0 and (mode=='mode2' or z[2]!=0)
  v=(z[0]/z[1] if mode=='mode2' else (z[0]/z[2])*(z[3]/z[1])) if valid else None
  rows.append(dict(mode=mode,bz=bz,sample_id=sid,success=valid,real=v.real if valid else None,imag=v.imag if valid else None))
summaries=[]
for mode in ('mode2','mode3'):
 for bz in p['bz_values']:
  for component in ('real','imag'):
   values=sorted(r[component] for r in rows if (r['mode'],r['bz'])==(mode,bz) and r['success'])
   def q(f):
    i=(len(values)-1)*f;a=math.floor(i);b=math.ceil(i);return values[a]+(values[b]-values[a])*(i-a)
   lo,hi=(q(.16),q(.84)) if values else (None,None)
   summaries.append(dict(mode=mode,bz=bz,component=component,mean=(lo+hi)/2 if values else None,error=(hi-lo)/2 if values else None,n_valid=len(values)))
print(json.dumps(dict(status='ok',results=rows,summaries=summaries)))
'''


def method_inputs(library, asset, *, program=None):
    from lqcd_agent.research.methods import assess_method
    code = method_program() if program is None else program
    code_ref = project_file(library, "analysis.py", code)
    return {"source": code_ref, "assessment": assess_method(code, 'normalization', sys.executable),
            "actor": "operator", "rationale": "Independent finite normalization calibration.",
            "expected_revision": asset['revision']}


def test_method_registration_requires_executed_exact_source_validation(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library, "method", "correlated-ratio")
    arguments = method_inputs(library, asset)
    forged = {"source_sha256": arguments['source']['sha256'], "passed": True,
              "checks": [{"name": "claimed", "passed": True}]}
    with pytest.raises(ControlIntegrityError, match='not an uploaded report'):
        library.register_method(asset['id'], **{**arguments, 'assessment': forged})
    with pytest.raises(ControlIntegrityError, match="registered"):
        library.review("method", asset["id"], **review(library, asset))
    changed = project_file(library, "changed.py", method_program()+b'\n# changed\n')
    with pytest.raises(ControlIntegrityError, match='source changed'):
        library.register_method(asset['id'], **{**arguments, 'source': changed})
    registered = library.register_method(asset["id"], **arguments)
    assert registered['registered'] and registered['asset']['review']['origin']=='human'
    record, code = library.method_snapshot(asset["id"])
    assert record == registered['asset']
    assert hashlib.sha256(code).hexdigest() == record["implementation"]["sha256"]
    implementation = library.workspace / record["implementation"]["path"]
    implementation.write_text("def ratio(a, b): return 0\n")
    with pytest.raises(ControlIntegrityError, match="evidence changed"):
        library.method_snapshot(asset["id"])


def test_failed_host_calibration_is_retained_without_method_promotion(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library, 'method', 'bad-method')
    result = library.register_method(asset['id'], **method_inputs(library, asset, program=b'print("{}")\n'))
    assert not result['registered'] and result['asset']['status']=='candidate'
    from lqcd_agent.control.strict_json import loads
    report = loads(library._evidence(result['validation']))
    assert report['passed'] is False and all(not r['passed'] for r in report['checks'])
    assert all('execution' in r for r in report['checks'])
    with pytest.raises(ControlIntegrityError, match='reusable'):
        library.method_snapshot(asset['id'])


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


def test_sdk_reviewer_can_publish_a_scoped_system_review_without_human_response(tmp_path):
    import asyncio
    from openai.types.responses import ResponseFunctionToolCall
    from lqcd_agent.control.strict_json import digest
    from lqcd_agent.research.agent_runtime import ResearchAgentRuntime
    from lqcd_agent.research.tools import build_tools
    from tests.test_research_agent_runtime import ScriptedModel, arguments, message

    library = Library(tmp_path)
    asset = candidate(library, actor='system:host/case/run/attempt_000001')
    supporting = {'unit': 'lattice units', 'limitation': 'The original paired indices remain unavailable.'}
    context = {'identity': {'case_id': 'case', 'run_id': 'run', 'attempt_id': 'attempt_000004',
                           'attempt_kind': 'scientific_reviewer'}, 'current_evidence': []}
    host = tmp_path/'host'; host.mkdir()
    output = host/'domain'; output.mkdir()
    tools = build_tools(tmp_path, context, host=host, output_dir=output, sources={'supporting': supporting}, write_scope=nullcontext)
    calls = [[ResponseFunctionToolCall(type='function_call', name='read_context', call_id='read',
                  arguments='{"section":"supporting","offset":0}')],
             [ResponseFunctionToolCall(type='function_call', name='review_asset', call_id='review',
                  arguments=json.dumps({'kind': 'wiki', 'asset_id': asset['id'],
                      'expected_revision': 1, 'rationale': 'Scoped review preserves the explicit provenance limitation.',
                      'evidence_ids': [digest(supporting)]}))],
             [message('The scoped asset was reviewed; the provenance limitation remains.')]]
    events = []
    result = asyncio.run(ResearchAgentRuntime(ScriptedModel(calls), max_output_tokens=512).run(
        **arguments(events.append, tools)))
    assert result.output['conclusion'].startswith('The scoped asset')
    reviewed = library.read('wiki', asset['id'])
    assert reviewed['status']=='reviewed' and reviewed['review']['origin']=='system'
    assert reviewed['review']['actor'].endswith('/attempt_000004')
    assert len(reviewed['review']['evidence'])==1
    assert [e['tool_name'] for e in events if e['event']=='tool_end']==['read_context','review_asset']
    assert library.read('wiki', asset['id'], 1)['status']=='candidate'


def test_automatic_reviewer_cannot_self_review_or_cite_unread_evidence(tmp_path):
    import asyncio,json
    from agents.tool_context import ToolContext
    from lqcd_agent.research.tools import build_tools
    context = {'identity': {'case_id': 'case', 'run_id': 'run', 'attempt_id': 'review',
                           'attempt_kind': 'scientific_reviewer'}, 'current_evidence': []}
    host=tmp_path/'host';host.mkdir()
    tools={t.name:t for t in build_tools(tmp_path, context, host=host, output_dir=host/'domain', write_scope=nullcontext)}
    async def call(name,value):
        raw=json.dumps(value)
        result=await tools[name].on_invoke_tool(ToolContext(context=None,tool_name=name,
            tool_call_id='test',tool_arguments=raw),raw)
        return json.loads(result) if isinstance(result,str) else result
    own=asyncio.run(call('save_candidate', {'kind':'wiki','asset_id':'own','title':'Own claim',
        'body':'Scoped provisional claim.','applicability':'fixture','source_urls':[],'expected_revision':0}))
    result=asyncio.run(call('review_asset',{'kind':'wiki','asset_id':own['id'],'expected_revision':1,
        'rationale':'Self review is insufficient.','evidence_ids':['0'*64]}))
    assert not result['reviewed'] and 'different-attempt' in result['reason']
    other=candidate(Library(tmp_path),asset_id='other')
    result=asyncio.run(call('review_asset',{'kind':'wiki','asset_id':other['id'],'expected_revision':1,
        'rationale':'No actual read.','evidence_ids':['0'*64]}))
    assert not result['reviewed'] and 'Read the supporting' in result['reason']
    assert Library(tmp_path).search(status='reviewed')==[]
