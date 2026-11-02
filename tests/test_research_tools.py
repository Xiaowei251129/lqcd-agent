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
    assert not {'execute', 'shell', 'approve', 'review'}.intersection(tools)
    with pytest.raises(ControlIntegrityError, match='reusable'):
        asyncio.run(call('read_method_source', {'asset_id': 'ratio', 'offset': 0}))


def test_page_has_explicit_remainder_and_content_identity():
    value = {'data': 'x' * 18000}
    first = page(value)
    second = page(value, first['next_offset'])
    assert first['sha256'] == digest(value) == second['sha256']
    assert second['next_offset'] is None
