"""Research tools use bounded public transport and scoped evidence, not broad file access."""
import asyncio
import json

import httpx
import pytest
from agents.tool_context import ToolContext

from lqcd_agent.control.strict_json import ControlIntegrityError, digest
from lqcd_agent.research.tools import Literature, build_tools, page


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
                                                  sources={'definitions': {'unit': 'lattice'}})}
    async def call(name, arguments):
        result = await tools[name].on_invoke_tool(ToolContext(context=None, tool_name=name, tool_call_id='fixture', tool_arguments=json.dumps(arguments)), json.dumps(arguments))
        return json.loads(result) if isinstance(result, str) else result
    catalog = asyncio.run(call('read_context', {'section': 'catalog', 'offset': 0}))
    assert catalog['sections'] == ['definitions']
    with pytest.raises(ControlIntegrityError, match='Unknown'):
        asyncio.run(call('read_context', {'section': '.env', 'offset': 0}))
    result = asyncio.run(call('save_candidate', {'kind': 'method', 'asset_id': 'ratio', 'title': 'Ratio',
        'body': 'Keep covariance.', 'applicability': 'fixture only', 'source_urls': [], 'expected_revision': 0}))
    assert result['status'] == 'candidate'
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
