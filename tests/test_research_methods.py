"""Reusable code is reviewed and frozen before entering the sole Code backend."""
from contextlib import nullcontext
from hashlib import sha256

import pytest

from lqcd_agent.control.strict_json import ControlIntegrityError
from lqcd_agent.research.library import Library
from lqcd_agent.research.methods import method_files, snapshot_methods
from tests.test_research_library import candidate, method_inputs


def test_reviewed_sources_are_frozen_and_stale_dependencies_are_refused(tmp_path):
    library = Library(tmp_path)
    asset = candidate(library, 'method')
    arguments = method_inputs(library, asset)
    code = (tmp_path/arguments['source']['path']).read_bytes()
    reviewed = library.register_method(asset['id'], **arguments)['asset']
    config = {'method_dependencies': [{key: reviewed[key] for key in ('id', 'revision', 'sha256')}]}
    snapshot = snapshot_methods(config, tmp_path)
    assert method_files(snapshot) == {'reused/'+asset['id']+'.py': code}
    assert snapshot[0]['source_sha256'] == sha256(code).hexdigest()
    candidate(library, 'method', expected_revision=reviewed['revision'], body='Changed method; needs fresh review.')
    with pytest.raises(ControlIntegrityError, match='reusable|current review'):
        snapshot_methods(config, tmp_path)
    assert method_files(snapshot)['reused/'+asset['id']+'.py'] == code
    snapshot[0]['source'] += '\n# changed'
    with pytest.raises(ControlIntegrityError, match='changed'):
        method_files(snapshot)


def method_review_tools(tmp_path, *, write_scope=nullcontext):
    import json, sys
    from lqcd_agent.control.strict_json import canonical_bytes, digest
    from lqcd_agent.code_agent.execution import execute_candidate
    from lqcd_agent.code_agent.workspace import WorkspaceProvider, tree_digest
    from lqcd_agent.research.tools import build_tools
    from lqcd_agent.research.projects import ProjectStore
    from lqcd_agent.research_evaluation import calibration
    from tests.test_research_library import method_program

    ProjectStore(tmp_path).create('study', 'Normalization study', 'Check the finite normalization contract.')
    library=Library(tmp_path)
    asset=candidate(library,'method','run-method',actor='system:host/case/run/code')
    host=tmp_path/'host';host.mkdir()
    run=host/'case/run';run.mkdir(parents=True)
    program=method_program()
    manifest={'workspace_id':'source','manifest_digest':'1'*64,'managed_root_identity':'2'*64,
              'base_tree_digest':tree_digest({'analysis.py':program})}
    provider=WorkspaceProvider(host/'code_workspaces')
    provider.materialize(manifest,{'analysis.py':program},lambda:None)
    _,execution=execute_candidate(program,calibration('normalization'),sys.executable,timeout=10)
    files={'code_agent_result.json':{'status':'success','usable':True},
           'workspace_manifest.json':manifest,
           'workspace_seal.json':{'final_tree_digest':manifest['base_tree_digest']},
           'run_result.json':{'domain_result':{'run_success':True,'run_result':{'generated_execution':{'execution':execution}}}}}
    references=[]
    for name,value in files.items():
        path=run/name;path.write_bytes(canonical_bytes(value))
        references.append({'artifact_id':'code' if name!='run_result.json' else 'analysis',
                           'member':name,'sha256':sha256(path.read_bytes()).hexdigest()})
    supporting={'scope':'Normalization contract with explicitly paired replicas.'}
    context={'identity':{'case_id':'case','run_id':'run','attempt_id':'review','attempt_kind':'scientific_reviewer'},
             'current_evidence':references,'root_goal':{'project_id':'study','case_config':{
                'generated_program':{'result_kind':'normalization','python':sys.executable}}}}
    tools={t.name:t for t in build_tools(tmp_path,context,host=host,output_dir=host/'domain',sources={'supporting':supporting}, write_scope=write_scope)}
    async def invoke(name,value):
        from agents.tool_context import ToolContext
        raw=json.dumps(value)
        result=await tools[name].on_invoke_tool(ToolContext(context=None,tool_name=name,tool_call_id='test',tool_arguments=raw),raw)
        return json.loads(result) if isinstance(result,str) else result
    arguments={'kind':'method','asset_id':asset['id'],'expected_revision':1,
               'rationale':'The exact successful sealed program passed finite independent calibration.',
               'evidence_ids':[digest(supporting)]}
    return library,provider.path(manifest['workspace_id']),context,invoke,arguments


@pytest.mark.parametrize('fault',[None,'sealed_source','analysis_source','during_sealed','during_analysis','expired'])
def test_automatic_method_review_executes_exact_sealed_successful_program(tmp_path,monkeypatch,fault):
    import asyncio
    from tests.test_research_library import method_program
    from contextlib import contextmanager
    from lqcd_agent.research import methods
    @contextmanager
    def expired():
        raise ControlIntegrityError('Original Host fence expired')
        yield
    library,workspace,context,invoke,arguments=method_review_tools(tmp_path,
        write_scope=expired if fault=='expired' else nullcontext)
    if fault in ('during_sealed','during_analysis'):
        assess=methods.assess_method
        def mutate(*args,**kwargs):
            assessment=assess(*args,**kwargs)
            if fault=='during_sealed':
                (workspace/'analysis.py').write_text('print("{}")\n')
            else:
                (tmp_path/'host/case/run/run_result.json').write_bytes(b'{}')
            return assessment
        monkeypatch.setattr(methods,'assess_method',mutate)
    if fault=='sealed_source':
        (workspace/'analysis.py').write_text('print("{}")\n')
    if fault=='analysis_source':
        from lqcd_agent.control.strict_json import canonical_bytes,loads
        ref=next(r for r in context['current_evidence'] if r['member']=='run_result.json')
        path=tmp_path/'host/case/run/run_result.json'
        value=loads(path.read_bytes())
        value['domain_result']['run_result']['generated_execution']['execution']['program_sha256']='0'*64
        path.write_bytes(canonical_bytes(value));ref['sha256']=sha256(path.read_bytes()).hexdigest()
    async def check():
        await invoke('read_context',{'section':'supporting','offset':0})
        if fault:
            with pytest.raises(ControlIntegrityError,match='mutation|actually executed|evidence changed|fence expired'):
                await invoke('review_asset',arguments)
            assert library.read('method','run-method')['status']=='candidate'
            assert not (tmp_path/'projects/study/methods').exists()
            assert not (tmp_path/'library/reviews').exists()
        else:
            result=await invoke('review_asset',arguments)
            assert result['registered'] and result['asset']['review']['origin']=='system'
            assert result['evidence_id']==result['validation']['sha256']
            assert [r['name'] for r in result['checks']]==['paired_complex','failed_replica','missing_reference']
            assert all(set(r)=={'name','passed'} and r['passed'] for r in result['checks'])
            report=(tmp_path/'host/domain/method_validations'/(result['evidence_id']+'.json')).read_bytes()
            assert sha256(report).hexdigest()==result['evidence_id']
            page=await invoke('read_context',{'section':result['section'],'offset':0})
            assert page['sha256']==result['evidence_id'] and page['total_chars']==len(report.decode())
            record,program=library.method_snapshot('run-method')
            assert program==method_program()
            assert record['implementation']['family']=='normalization' and record['implementation']['limitations']
            assert len(record['review']['evidence'])==3
    asyncio.run(check())


def test_cancelled_method_review_drains_calibration_before_return_without_promotion(tmp_path,monkeypatch):
    import asyncio,threading
    from lqcd_agent.research import methods
    library,_,_,invoke,arguments=method_review_tools(tmp_path)
    entered,released,ended=threading.Event(),threading.Event(),threading.Event()
    cancellations=[]
    def calibrate(*args,cancel_event,**kwargs):
        entered.set()
        try:
            assert released.wait(5)
            cancellations.append(cancel_event.is_set())
            raise InterruptedError('Fixture numerical calibration cancelled')
        finally:
            ended.set()
    monkeypatch.setattr(methods,'assess_method',calibrate)
    async def check():
        await invoke('read_context',{'section':'supporting','offset':0})
        task=asyncio.create_task(invoke('review_asset',arguments))
        for _ in range(100):
            if entered.is_set():break
            await asyncio.sleep(.01)
        assert entered.is_set()
        task.cancel()
        await asyncio.sleep(.02)
        assert not task.done() and not ended.is_set()
        released.set()
        with pytest.raises(asyncio.CancelledError):await task
        assert ended.is_set()
    asyncio.run(check())
    assert cancellations==[True] and library.read('method','run-method')['status']=='candidate'
    assert not (tmp_path/'projects/study/methods').exists()


def test_hidden_c2_calibration_rejects_a_constant_fixture_ground_state():
    import sys
    from lqcd_agent.research.methods import assess_method, executed_assessment
    from tests.test_scientific_codegen import C2
    report=executed_assessment(assess_method(C2,'c2',sys.executable),sha256(C2).hexdigest())
    assert not report['passed']
    low,high,fixed=report['checks']
    assert low['expected_ground'] < .23 and high['expected_ground'] > .32
    assert not low['passed'] and not high['passed'] and fixed['passed']
    assert all(r['execution']['program_sha256']==sha256(C2).hexdigest() for r in report['checks'])
