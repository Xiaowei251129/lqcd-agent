"""Named research capabilities; no shell, arbitrary file read or model-owned approval."""
import asyncio
from hashlib import sha256
import threading
from html.parser import HTMLParser
from pathlib import Path
import re

from agents import function_tool
import httpx

from lqcd_agent.control.coordinator import publish_exact, read_regular
from lqcd_agent.control.strict_json import canonical_bytes, digest, digest_value, loads, require
from .library import Library, valid_literature_url


PAGE_CHARS = 12000
# A production C2 window scan includes fit and covariance diagnostics for both models.
C2_REVIEW_PAGE_CHARS = 48000
MAX_PAPER_BYTES = 4 * 1024 * 1024


def page(value, offset=0, *, size=PAGE_CHARS):
    require(type(offset) is int and offset >= 0, 'Invalid evidence offset')
    content = value if type(value) is str else canonical_bytes(value).decode()
    require(offset <= len(content), 'Evidence offset exceeds content')
    return {'text': content[offset:offset+size], 'offset': offset,
            'next_offset': offset+size if offset+size < len(content) else None,
            'total_chars': len(content), 'sha256': sha256(content.encode()).hexdigest()}


def c2_review_reference(host, context, sources):
    """Join the Host diagnostic's producer path and digest to this Run's registered Analysis copy."""
    if ((sources.get('run_result') or {}).get('generated_execution') or {}).get('result_kind') != 'c2':
        return None
    diagnostic = (sources.get('review_evidence') or {}).get('generated_diagnostics') or {}
    witnesses = {(row.get('path'), row.get('value')) for row in diagnostic.get('evidence', []) if row.get('field') == 'sha256'}
    identity = context['identity']
    for ref in context.get('current_evidence', []):
        attempt, _, slot = ref['artifact_id'].rpartition(':')
        member = Path('analysis_outputs/generated_result.json')
        if slot != 'analysis' or ref['member'] != str(Path('attempts') / attempt / member):
            continue
        producer = Path(host) / 'domain' / attempt / identity['case_id'] / identity['run_id'] / member
        if (str(producer), ref['sha256']) in witnesses:
            return ref
    return None


class PaperText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'section', 'h1', 'h2', 'h3', 'tr', 'li'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden-1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


class Literature:
    """Public INSPIRE metadata and arXiv HTML, without arbitrary URL fetching."""
    def __init__(self, output_dir, *, transport=None):
        self.output = Path(output_dir)/'literature'
        self.transport = transport

    async def _fetch(self, url, *, params=None):
        async with httpx.AsyncClient(timeout=30, follow_redirects=False, transport=self.transport,
                                     headers={'User-Agent': 'lqcd-agent research reader'}) as client:
            async with client.stream('GET', url, params=params) as response:
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    require(len(raw) <= MAX_PAPER_BYTES, 'Literature response exceeds reading limit')
                return bytes(raw), str(response.url)

    def _store(self, record):
        self.output.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(self.output == self.output.resolve(), 'Redirected literature evidence')
        identifier = digest(record)
        publish_exact(self.output/(identifier+'.json'), canonical_bytes(record))
        return identifier

    async def search(self, query, limit=5):
        require(type(query) is str and 0 < len(query) <= 1000, 'Invalid literature query')
        require(type(limit) is int and 1 <= limit <= 10, 'Literature result limit is 1 to 10')
        raw, url = await self._fetch('https://inspirehep.net/api/literature', params={'q': query, 'size': limit})
        value = loads(raw, canonical=False)
        hits = []
        for hit in value.get('hits', {}).get('hits', [])[:limit]:
            meta = hit.get('metadata', {})
            hits.append({'inspire_id': hit['id'], 'title': meta.get('titles', [{}])[0].get('title', ''),
                         'arxiv': meta.get('arxiv_eprints', []), 'doi': meta.get('dois', []),
                         'abstracts': meta.get('abstracts', []),
                         'source': 'https://inspirehep.net/literature/'+str(hit['id'])})
        identifier = self._store({'source': url, 'response_sha256': sha256(raw).hexdigest(), 'hits': hits})
        return {'evidence_id': identifier, 'hits': hits, 'scope': 'Metadata and abstracts, not full-paper review'}

    async def read(self, arxiv_id, offset=0):
        require(type(arxiv_id) is str and re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?', arxiv_id),
                'Use an arXiv identifier, not a URL or local file')
        # The HTML endpoint supplies equations and section structure. A missing HTML
        # version is reported, never silently replaced with an abstract-only review.
        raw, url = await self._fetch('https://arxiv.org/html/'+arxiv_id)
        parser = PaperText()
        parser.feed(raw.decode('utf-8'))
        content = ''.join(parser.parts).strip()
        require(content, 'No readable arXiv HTML text')
        identifier = self._store({'source': url, 'response_sha256': sha256(raw).hexdigest(), 'text': content})
        return {'evidence_id': identifier, 'source': url, 'scope': 'HTML text; embedded figures are not inspected', **page(content, offset)}


def build_tools(workspace, context, *, host, output_dir, sources=None, write_scope=None):
    """Construct only capabilities authorized for this particular research attempt."""
    library = Library(workspace)
    literature = Literature(output_dir)
    host, output_dir = Path(host), Path(output_dir)
    root = host/context['identity']['case_id']/context['identity']['run_id']
    allowed = {digest(ref): ref for ref in context.get('current_evidence', [])}
    sections = dict(sources if sources is not None else context.get('research_sources', {}))
    c2_output = c2_review_reference(host, context, sections)
    project_id = context.get('root_goal', {}).get('project_id')
    identity = context['identity']
    actor = 'system:' + '/'.join(str(value) for value in
        (host.name, identity['case_id'], identity['run_id'], identity.get('attempt_id', 'unscoped')))
    observed = {}

    def observe(value):
        identifier = value.get('evidence_id') or value.get('sha256')
        if identifier is not None:
            observed[identifier] = value
        return value

    def registered(filename):
        references = [ref for ref in allowed.values() if Path(ref['member']).name == filename]
        require(len(references) == 1, 'Method review needs exact registered ' + filename)
        reference = references[0]
        target = root/reference['member']
        require(target == target.resolve() and target.is_relative_to(root), 'Method evidence escaped Run')
        raw = read_regular(target)
        require(sha256(raw).hexdigest() == reference['sha256'], 'Method evidence changed')
        return loads(raw)

    @function_tool(failure_error_function=None)
    async def search_library(query: str, kind: str | None = None) -> dict:
        """Search this installation's current wiki, skill or method candidates and reviews."""
        records = library.search(query, kind=kind, limit=12)
        return {'assets': [{key: record[key] for key in ('kind', 'id', 'revision', 'sha256', 'title', 'scope', 'status', 'dependency_changes')}
                           for record in records]}

    @function_tool(failure_error_function=None)
    async def read_asset(kind: str, asset_id: str, offset: int = 0) -> dict:
        """Read a version-bound local asset; candidate or contested claims remain provisional."""
        return page(library.read(kind, asset_id), offset)

    @function_tool(failure_error_function=None)
    async def read_method_source(asset_id: str, offset: int = 0) -> dict:
        """Read the verified current reviewed Python method for reuse in a coding proposal."""
        record, raw = library.method_snapshot(asset_id)
        return {'asset': record, 'source': page(raw.decode(), offset)}

    @function_tool(failure_error_function=None)
    async def save_candidate(kind: str, asset_id: str, title: str, body: str, applicability: str,
                             source_urls: list[str], expected_revision: int = 0) -> dict:
        """Save an explicitly provisional wiki/skill/method description, never approve or execute it.

        Args:
            source_urls: Only actual http:// or https:// literature URLs. Host context:<sha>
                identifiers are not URLs. Use [] when no external literature source applies.
        """
        require(len(body) <= 60000 and len(title) <= 300, 'Candidate is too large')
        require(write_scope is not None, 'Research asset mutation needs original Host write authority')
        invalid = [index for index, url in enumerate(source_urls) if not valid_literature_url(url)]
        if invalid:
            return {'status': 'invalid_input', 'field': 'source_urls', 'invalid_indices': invalid,
                    'reason': 'Only actual http:// or https:// literature URLs are accepted; context:<sha> '
                              'identifies Host context and is not a literature URL.',
                    'next_action': 'Supply literature URLs, or use [] when no external literature source applies.'}
        with write_scope():
            record = library.save(kind, asset_id, title=title, body=body,
                                  scope={'applicability': applicability},
                                  sources=[{'url': url, 'locator': 'Agent-proposed source; verify before review'} for url in source_urls],
                                  expected_revision=expected_revision, actor=actor)
        return {key: record[key] for key in ('kind', 'id', 'revision', 'sha256', 'status')}

    @function_tool(failure_error_function=None)
    async def search_literature(query: str, limit: int = 5) -> dict:
        """Search public INSPIRE literature metadata and abstracts; query must contain no private data."""
        try:
            return observe(await literature.search(query, limit))
        except httpx.HTTPError as error:
            return {'status': 'unavailable', 'reason': type(error).__name__, 'evidence': None}

    @function_tool(failure_error_function=None)
    async def read_paper(arxiv_id: str, offset: int = 0) -> dict:
        """Read a paginated public arXiv HTML paper; unavailable HTML is an explicit failure."""
        try:
            return observe(await literature.read(arxiv_id, offset))
        except httpx.HTTPError as error:
            return {'status': 'unavailable', 'reason': type(error).__name__, 'evidence': None}

    @function_tool(failure_error_function=None)
    async def read_context(section: str, offset: int = 0) -> dict:
        """Read Host-supplied sections and this Run's registered files.

        Use section='catalog' to list sections and registered_evidence. Pass a
        registered_evidence dictionary key as section to read that current Run file;
        these section IDs are not Project evidence SHA256 values. Unknown names or
        IDs return not_registered; copy exact catalog values without shortening them.
        """
        if section == 'catalog':
            return {'sections': sorted(sections), 'registered_evidence': allowed}
        if section in sections:
            return observe(page(sections[section], offset))
        if section not in allowed:
            return {'status': 'not_registered',
                    'reason': "This section name or ID is not in the current Run's read_context catalog.",
                    'next_action': "Call read_context(section='catalog', offset=0), then copy an exact named "
                                   'section or registered_evidence dictionary key as section.'}
        ref = allowed[section]
        target = root/ref['member']
        require(target == target.resolve() and target.is_relative_to(root), 'Research evidence escaped Run')
        raw = read_regular(target)
        require(sha256(raw).hexdigest() == ref['sha256'], 'Research evidence changed')
        size = C2_REVIEW_PAGE_CHARS if ref == c2_output else PAGE_CHARS
        return observe(page(raw.decode(), offset, size=size))

    @function_tool(failure_error_function=None)
    async def read_project_evidence(evidence_sha256: str | None = None, offset: int = 0) -> dict:
        """Read this Run's Project catalog, or its registered evidence.

        Use a member sha256 from this tool's Project catalog or project_history
        source.evidence_sha256. Current Run read_context catalog keys are section IDs
        for read_context(section=id), not Project member hashes. History is not authority.
        """
        from .projects import ProjectStore, UnregisteredEvidence
        projects = ProjectStore(workspace)
        if evidence_sha256 is None:
            return page({'project': projects.read(project_id), 'runs': projects.runs(project_id)}, offset)
        digest_value(evidence_sha256)
        try:
            raw = projects.evidence(project_id, evidence_sha256)
        except UnregisteredEvidence:
            if evidence_sha256 in allowed:
                return {'status': 'not_registered',
                        'reason': 'This is a current Run read_context section ID, not a registered Project evidence SHA256.',
                        'next_action': f'Call read_context(section={evidence_sha256!r}, offset={offset}) '
                                       'to read that current Run file through its original hash and path checks.'}
            return {'status': 'not_registered',
                    'reason': "This digest is not registered evidence in the Run's bound project.",
                    'next_action': 'Read the project catalog with read_project_evidence() and use a registered '
                                   'member sha256, or use project_history source.evidence_sha256. '
                                   'A content or section hash is not a project evidence identifier.'}
        return observe(page(raw.decode('utf-8'), offset))

    @function_tool(failure_error_function=None)
    async def review_asset(kind: str, asset_id: str, expected_revision: int,
                           rationale: str, evidence_ids: list[str]) -> dict:
        """Independently review a prior-attempt candidate using evidence actually read here.

        Methods additionally execute Host calibration of the exact current sealed program.
        Generic contracts stay candidates; passing finite tests is not universal physics validation.
        """
        require(write_scope is not None, 'Research asset mutation needs original Host write authority')
        asset = library.read(kind, asset_id)
        require(asset['revision'] == expected_revision, 'Stale scientific asset revision')
        if asset.get('proposed_by') is None:
            return {'asset': asset, 'reviewed': False,
                    'reason': 'Save a version with attributable proposer identity before automatic review.'}
        if asset['proposed_by'] == actor:
            return {'asset': asset, 'reviewed': False,
                    'reason': 'A candidate needs a different-attempt independent reviewer.'}
        if asset['status'] != 'candidate':
            return {'asset': asset, 'reviewed': False, 'reason': 'Only a current candidate needs automatic review.'}
        if not evidence_ids or any(identifier not in observed for identifier in evidence_ids):
            return {'asset': asset, 'reviewed': False,
                    'reason': 'Read the supporting context or literature before citing its returned evidence ID.'}
        def evidence_references():
            evidence = []
            library.initialize()
            for identifier in dict.fromkeys(evidence_ids):
                value = observed[identifier]
                relative = 'library/evidence/' + digest(value) + '.json'
                path = library._path(relative)
                path.parent.mkdir(mode=0o700, exist_ok=True)
                publish_exact(path, canonical_bytes(value))
                evidence.append(library.reference(relative))
            return evidence
        if kind != 'method':
            with write_scope():
                record = library.review(kind, asset_id, status='reviewed', rationale=rationale,
                    evidence=evidence_references(), actor=actor, expected_revision=expected_revision)
            return {'asset': record, 'reviewed': True,
                    'reason': 'Independent scoped system review; cited source claims remain attributable.'}
        config = context.get('root_goal', {}).get('case_config', {})
        program_config = config.get('generated_program') or {}
        family = program_config.get('result_kind')
        if project_id is None or family not in ('c2', 'normalization'):
            return {'asset': asset, 'reviewed': False,
                    'reason': 'Automatic method review needs a linked Project and a supported independent calibration contract.'}
        from .methods import assess_method, executed_assessment
        from .agent_runtime import _drain_tasks
        from lqcd_agent.code_agent.workspace import WorkspaceProvider
        result = registered('code_agent_result.json')
        require(result['status'] == 'success' and result['usable'] is True, 'Method review needs usable sealed Code')
        manifest, seal = registered('workspace_manifest.json'), registered('workspace_seal.json')
        provider = WorkspaceProvider(host/'code_workspaces')
        files = provider.verify_sealed(manifest, provider._public_witness(manifest), seal['final_tree_digest'])
        program = files['analysis.py']
        analysis = registered('run_result.json')['domain_result']
        require(analysis['run_success'] is True and
                analysis['run_result']['generated_execution']['execution']['program_sha256'] == sha256(program).hexdigest(),
                'Method must match the actually executed successful Analysis')
        cancelled = threading.Event()
        validation = asyncio.create_task(asyncio.to_thread(assess_method, program, family,
            program_config['python'], cancel_event=cancelled))
        try:
            assessment = await asyncio.shield(validation)
        except BaseException:
            cancelled.set()
            await _drain_tasks([validation])
            raise
        with write_scope():
            require(registered('code_agent_result.json') == result and
                    registered('workspace_manifest.json') == manifest and registered('workspace_seal.json') == seal and
                    registered('run_result.json')['domain_result'] == analysis,
                    'Run evidence changed during method calibration')
            current = provider.verify_sealed(manifest, provider._public_witness(manifest), seal['final_tree_digest'])
            require(current['analysis.py'] == program, 'Sealed method source changed during calibration')
            report = executed_assessment(assessment, sha256(program).hexdigest())
            identifier = sha256(assessment.record).hexdigest()
            section = 'method_validation:' + identifier
            destination = output_dir/'method_validations'/(identifier+'.json')
            require(destination == destination.resolve() and destination.is_relative_to(output_dir),
                    'Method calibration report escaped its producing attempt')
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            publish_exact(destination, assessment.record)
            sections[section] = report
            relative = f'projects/{project_id}/methods/{sha256(program).hexdigest()}.py'
            source_path = library._path(relative)
            source_path.parent.mkdir(mode=0o700, exist_ok=True)
            publish_exact(source_path, program)
            reviewed = library.register_method(asset_id, source=library.reference(relative), assessment=assessment,
                actor=actor, rationale=rationale, expected_revision=expected_revision, evidence=evidence_references())
            return {**reviewed, 'evidence_id': identifier, 'section': section,
                    'checks': [{'name': row['name'], 'passed': row['passed']} for row in report['checks']],
                    'limitations': report['limitations']}

    tools = [search_library, read_asset, read_method_source, save_candidate, search_literature, read_paper,
             read_context]
    if identity.get('attempt_kind') == 'scientific_reviewer':
        tools.append(review_asset)
    if project_id is not None:
        tools.append(read_project_evidence)
    return tools
