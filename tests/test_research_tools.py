"""Research tools use bounded public transport and scoped evidence, not broad file access."""
from contextlib import nullcontext
import asyncio
import json

import httpx
import pytest
from agents.tool_context import ToolContext

from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from lqcd_agent.research.tools import Literature, build_tools, page
from tests.test_async_resources import resource_host as resource_host


def test_c2_review_reads_only_the_witnessed_producer_in_larger_pages(tmp_path):
    from hashlib import sha256
    from lqcd_agent.research.c2_evidence import c2_review_reference
    host = tmp_path/'host'
    payload = json.dumps({'diagnostics':'x' * 51000})
    checksum = sha256(payload.encode()).hexdigest()
    refs = []
    for attempt in ('attempt_000002', 'attempt_000003'):
        relative = f'attempts/{attempt}/analysis_outputs/generated_result.json'
        member = host/'case'/'run'/relative
        member.parent.mkdir(parents=True)
        member.write_text(payload)
        refs.append({'artifact_id':attempt+':analysis', 'member':relative, 'sha256':checksum})
    context = {'identity':{'case_id':'case','run_id':'run'}, 'current_evidence':refs}
    witness = {'path':str(host/'domain/attempt_000003/case/run/analysis_outputs/generated_result.json'),
               'field':'sha256', 'value':checksum}
    sources = {'run_result':{'generated_execution':{'result_kind':'c2'}},
               'review_evidence':{'generated_diagnostics':{'evidence':[witness]}}}
    assert c2_review_reference(host,context,sources) == refs[1]
    tool = next(t for t in build_tools(tmp_path,context,host=host,output_dir=tmp_path/'review',sources=sources)
                if t.name=='read_context')
    async def read(ref, offset=0):
        args = json.dumps({'section':digest(ref),'offset':offset})
        return await tool.on_invoke_tool(ToolContext(context=None,tool_name=tool.name,tool_call_id='read',
                                                     tool_arguments=args), args)
    previous = asyncio.run(read(refs[0]))
    first = asyncio.run(read(refs[1]))
    last = asyncio.run(read(refs[1],first['next_offset']))
    assert previous['next_offset']==12000 and first['next_offset']>previous['next_offset']
    assert first['total_chars']==len(payload) and last['next_offset'] is None
    assert first['text']+last['text']==payload and first['sha256']==last['sha256']==checksum
    witness['value']='0'*64
    assert c2_review_reference(host,context,sources) is None


def test_c2_selection_requires_a_cited_supporting_criterion_and_distinguishes_no_preference():
    from copy import deepcopy
    from lqcd_agent.research.c2_evidence import bind_c2_interpretation
    criterion = '/domain_result/preparation/brief/success_criteria/1'
    facts = {'criteria': [{'pointer': criterion, 'assessment': None, 'fit_pointers': []}],
             'fits': [{'pointer': '/fits/0'}], 'selection': {'status': 'unassessed', 'fit_pointer': None}}
    assert bind_c2_interpretation(deepcopy(facts), None) == facts
    selected = {'criterion': criterion, 'assessment': 'supports', 'fit_pointers': ['/fits/0']}
    for rows in ([], [selected, selected], [{**selected, 'criterion': '/absent'}],
                 [{**selected, 'assessment': 'limits'}], [{**selected, 'fit_pointers': ['/fits/99']}]):
        with pytest.raises(ControlIntegrityError):
            bind_c2_interpretation(deepcopy(facts), {'assessments': rows,
                                   'selection': 'selected', 'preferred_fit': '/fits/0'})
    explicit = bind_c2_interpretation(deepcopy(facts), {'assessments': [], 'selection': 'no_preference',
                                                        'preferred_fit': None})
    assert explicit['selection'] == {'status': 'no_preference', 'fit_pointer': None}
    assert explicit['criteria'] == facts['criteria']


def test_public_literature_reader_paginates_and_retains_exact_source(tmp_path):
    requests = []
    def transport(request):
        requests.append(str(request.url))
        if request.url.host == 'inspirehep.net':
            return httpx.Response(200, json={'hits': {'hits': [{'id': '42', 'metadata': {
                'titles': [{'title': 'Fixture lattice analysis'}], 'arxiv_eprints': [{'value': '2501.12345'}]}}]}})
        return httpx.Response(200, text='<html><script>not scientific evidence</script><section><h1>Method</h1><p>'+('equation ' * 2200)+'</p></section></html>')
    reader = Literature(tmp_path, transport=httpx.MockTransport(transport))
    found = asyncio.run(reader.search('fixture', 2))
    assert found['hits'][0]['inspire_id'] == '42'
    first = asyncio.run(reader.read('2501.12345v2'))
    second = asyncio.run(reader.read('2501.12345v2', first['next_offset']))
    assert first['evidence_id'] == second['evidence_id']
    assert first['next_offset'] == 12000 and 'not scientific' not in first['text']
    assert len(list((tmp_path/'literature').glob('*.json'))) == 2
    with pytest.raises(ControlIntegrityError, match='identifier'):
        asyncio.run(reader.read('https://localhost/.env'))
    assert len(requests) == 3


def test_named_tools_refuse_unknown_files_and_save_only_candidates(tmp_path):
    host = tmp_path/'host'; host.mkdir()
    output = host/'domain'; output.mkdir()
    context = {'identity': {'case_id': 'case', 'run_id': 'run'}, 'current_evidence': []}
    tools = {tool.name: tool for tool in build_tools(tmp_path, context, host=host, output_dir=output,
                                                  sources={'definitions': {'unit': 'lattice'}}, write_scope=nullcontext)}
    async def call(name, arguments):
        result = await tools[name].on_invoke_tool(ToolContext(context=None, tool_name=name, tool_call_id='fixture', tool_arguments=json.dumps(arguments)), json.dumps(arguments))
        return json.loads(result) if isinstance(result, str) else result
    catalog = asyncio.run(call('read_context', {'section': 'catalog', 'offset': 0}))
    assert catalog['sections'] == ['definitions']
    unknown = asyncio.run(call('read_context', {'section': '.env', 'offset': 0}))
    assert unknown['status'] == 'not_registered' and set(unknown) == {'status', 'reason', 'next_action'}
    assert "read_context(section='catalog', offset=0)" in unknown['next_action']
    candidate = {'kind': 'method', 'asset_id': 'ratio', 'title': 'Ratio',
        'body': 'Keep covariance.', 'applicability': 'fixture only',
        'source_urls': ['context:'+'a'*64], 'expected_revision': 0}
    rejected = asyncio.run(call('save_candidate', candidate))
    assert rejected['status'] == 'invalid_input' and rejected['field'] == 'source_urls'
    assert rejected['invalid_indices'] == [0] and '[]' in rejected['next_action']
    assert not (tmp_path/'library').exists()
    from lqcd_agent.research.library import Library
    library = Library(tmp_path)
    with pytest.raises(ControlIntegrityError, match='Invalid literature URL'):
        library.save('method', 'ratio', title='Ratio', body='Keep covariance.', scope={'fixture': True},
                     sources=[{'url': candidate['source_urls'][0], 'locator': 'Unverified context identifier'}])
    assert not (tmp_path/'library/methods/ratio').exists()
    result = asyncio.run(call('save_candidate', {**candidate, 'source_urls': []}))
    assert result['status'] == 'candidate' and library.read('method', 'ratio')['sources'] == []
    description = tools['save_candidate'].params_json_schema['properties']['source_urls']['description']
    assert 'http://' in description and 'context:<sha>' in description and '[]' in description
    assert not {'execute', 'shell', 'approve', 'review', 'read_project_evidence'}.intersection(tools)
    assert len(tools) == 7
    with pytest.raises(ControlIntegrityError, match='reusable'):
        asyncio.run(call('read_method_source', {'asset_id': 'ratio', 'offset': 0}))


def test_page_has_explicit_remainder_and_content_identity():
    value = {'data': 'x' * 18000}
    first = page(value)
    second = page(value, first['next_offset'])
    assert first['sha256'] == digest(value) == second['sha256']
    assert second['next_offset'] is None


def test_project_evidence_tool_is_bound_to_the_run_project(tmp_path):
    from lqcd_agent.research.projects import ProjectStore, UnregisteredEvidence
    from tests.test_research_projects import scientific_run

    store = ProjectStore(tmp_path)
    bound = store.create('bound', 'Current project', 'Inspect the current scientific question.')
    other = store.create('other', 'Other project', 'An unrelated scientific question.')
    snapshot = scientific_run(tmp_path, store, other)
    captured = store.capture_run(snapshot)
    identifier = captured['evidence'][0]['sha256']

    def tool_for(project):
        context = {'identity': snapshot.locator, 'root_goal': {'project_id': project['id']}}
        tools = build_tools(tmp_path, context, host=snapshot.host, output_dir=tmp_path/'output')
        return next(tool for tool in tools if tool.name == 'read_project_evidence')

    async def read(tool, identifier=None, offset=0):
        arguments = json.dumps({'evidence_sha256': identifier, 'offset': offset})
        result = await tool.on_invoke_tool(ToolContext(context=None, tool_name=tool.name,
            tool_call_id='fixture', tool_arguments=arguments), arguments)
        return json.loads(result) if isinstance(result, str) else result

    tool = tool_for(bound)
    assert set(tool.params_json_schema['properties']) == {'evidence_sha256', 'offset'}
    history = json.loads(asyncio.run(read(tool))['text'])
    assert history == {'project': bound, 'runs': []}
    with pytest.raises(UnregisteredEvidence, match='not registered to this project'):
        store.evidence(bound['id'], identifier)
    missing = asyncio.run(read(tool, identifier))
    assert missing == asyncio.run(read(tool, '0' * 64))
    assert missing['status'] == 'not_registered'
    assert set(missing) == {'status', 'reason', 'next_action'}
    assert 'source.evidence_sha256' in missing['next_action']
    assert identifier not in json.dumps(missing) and other['goal'] not in json.dumps(missing)

    registered = tool_for(other)
    assert asyncio.run(read(registered, identifier))['text'] == store.evidence(other['id'], identifier).decode()
    with pytest.raises(ControlIntegrityError, match='offset exceeds'):
        asyncio.run(read(registered, identifier, offset=10**9))
    path = tmp_path/'projects'/other['id']/'evidence'/identifier
    path.write_bytes(b'changed')
    with pytest.raises(ControlIntegrityError, match='digest changed'):
        asyncio.run(read(registered, identifier))
    path.unlink()
    with pytest.raises(FileNotFoundError):
        asyncio.run(read(registered, identifier))
    foreign = tmp_path/'unregistered.json'
    foreign.write_text('Private material outside the registered evidence store.')
    path.symlink_to(foreign)
    with pytest.raises(ControlIntegrityError, match='Redirected research path'):
        asyncio.run(read(registered, identifier))


def test_mutation_tools_without_original_host_authority_cannot_publish(tmp_path):
    host=tmp_path/'host';host.mkdir()
    tools={t.name:t for t in build_tools(tmp_path,{'identity':{'case_id':'case','run_id':'run'}},
        host=host,output_dir=host/'domain')}
    value={'kind':'wiki','asset_id':'unscoped','title':'Unscoped claim','body':'Candidate only.',
           'applicability':'fixture','source_urls':['context:'+'a'*64],'expected_revision':0}
    raw=json.dumps(value)
    async def check():
        with pytest.raises(ControlIntegrityError,match='original Host write authority'):
            await tools['save_candidate'].on_invoke_tool(ToolContext(context=None,tool_name='save_candidate',
                tool_call_id='unscoped',tool_arguments=raw),raw)
    asyncio.run(check())
    assert not (tmp_path/'library').exists()


def test_candidate_save_preserves_real_host_fencing_and_library_cas(tmp_path, resource_host):
    from lqcd_agent.research.library import Library
    from lqcd_agent.research.meter import ResearchMeter
    port, clock, root = resource_host
    context = {'identity': {'case_id': root.parent.name, 'run_id': root.name}}
    meter = ResearchMeter(port, node='method_planner', context=context, output_dir=tmp_path/'output',
                          request_timeout_seconds=1, model='offline-fixture', max_output_tokens=1)
    tool = next(tool for tool in build_tools(tmp_path, context, host=port.leases.coordinator.root,
        output_dir=tmp_path/'output', write_scope=meter.write_scope) if tool.name == 'save_candidate')
    value = {'kind': 'wiki', 'asset_id': 'fenced', 'title': 'Scoped candidate', 'body': 'Retain limitations.',
             'applicability': 'fixture only', 'source_urls': [], 'expected_revision': 0}
    async def call(value):
        raw = json.dumps(value)
        result = await tool.on_invoke_tool(ToolContext(context=None, tool_name=tool.name,
            tool_call_id='fenced-save', tool_arguments=raw), raw)
        return json.loads(result) if isinstance(result, str) else result
    assert asyncio.run(call(value))['revision'] == 1
    with pytest.raises(ControlIntegrityError, match='Stale scientific asset revision'):
        asyncio.run(call(value))
    library = Library(tmp_path)
    original = library.read('wiki', 'fenced')
    _, capability = port.leases.get(port.capability_id)
    clock.advance(capability['expires_at'] - clock.now().monotonic_seconds)
    with pytest.raises(ControlIntegrityError, match='Stale or expired invocation lease'):
        asyncio.run(call({**value, 'expected_revision': 1}))
    assert library.read('wiki', 'fenced') == original
    assert len(list((tmp_path/'library/wiki/fenced/versions').iterdir())) == 1


def test_current_run_section_misrouting_is_correctable_without_bypassing_evidence_checks(tmp_path):
    from hashlib import sha256
    from lqcd_agent.research.projects import ProjectStore
    ProjectStore(tmp_path).create('bound', 'Bound Project', 'Inspect current scientific evidence.')
    host = tmp_path/'host'
    root = host/'case'/'run'
    root.mkdir(parents=True)
    target = root/'result.json'
    raw = b'{"summary":"Current Run scientific evidence"}'
    target.write_bytes(raw)
    reference = {'artifact_id': 'analysis', 'member': 'result.json', 'sha256': sha256(raw).hexdigest()}
    section = digest(reference)
    context = {'identity': {'case_id': 'case', 'run_id': 'run'},
               'root_goal': {'project_id': 'bound'}, 'current_evidence': [reference]}
    tools = {tool.name: tool for tool in build_tools(tmp_path, context, host=host, output_dir=host/'domain')}
    async def call(name, arguments):
        value = json.dumps(arguments)
        result = await tools[name].on_invoke_tool(ToolContext(context=None, tool_name=name,
            tool_call_id='current-evidence', tool_arguments=value), value)
        return json.loads(result) if isinstance(result, str) else result
    truncated = asyncio.run(call('read_context', {'section': section[:-1], 'offset': 0}))
    assert truncated['status'] == 'not_registered' and set(truncated) == {'status', 'reason', 'next_action'}
    assert "read_context(section='catalog', offset=0)" in truncated['next_action']
    assert section not in json.dumps(truncated) and reference['sha256'] not in json.dumps(truncated)
    catalog = asyncio.run(call('read_context', {'section': 'catalog', 'offset': 0}))
    assert catalog['registered_evidence'][section] == reference
    correction = asyncio.run(call('read_project_evidence', {'evidence_sha256': section, 'offset': 7}))
    assert correction['status'] == 'not_registered' and 'text' not in correction
    assert f"read_context(section={section!r}, offset=7)" in correction['next_action']
    result = asyncio.run(call('read_context', {'section': section, 'offset': 7}))
    assert result['text'] == raw.decode()[7:] and result['sha256'] == reference['sha256']
    assert asyncio.run(call('read_context', {'section': 'a'*64, 'offset': 0})) == truncated
    with pytest.raises(ControlIntegrityError, match='offset exceeds'):
        asyncio.run(call('read_context', {'section': section, 'offset': 10**9}))
    with pytest.raises(ControlIntegrityError, match='Invalid evidence offset'):
        asyncio.run(call('read_context', {'section': section, 'offset': -1}))
    target.write_bytes(b'changed')
    with pytest.raises(ControlIntegrityError, match='Research evidence changed'):
        asyncio.run(call('read_context', {'section': section, 'offset': 0}))
    target.unlink()
    with pytest.raises(FileNotFoundError):
        asyncio.run(call('read_context', {'section': section, 'offset': 0}))
    outside = tmp_path/'outside.json'
    outside.write_bytes(raw)
    target.symlink_to(outside)
    with pytest.raises(ControlIntegrityError, match='Research evidence escaped Run'):
        asyncio.run(call('read_context', {'section': section, 'offset': 0}))
