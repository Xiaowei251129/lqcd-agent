"""Named research capabilities; no shell, arbitrary file read or model-owned approval."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re

from agents import function_tool
import httpx

from lqcd_agent.control.coordinator import publish_exact, read_regular
from lqcd_agent.control.strict_json import canonical_bytes, digest, digest_value, loads, require
from .library import Library


PAGE_CHARS = 12000
MAX_PAPER_BYTES = 4 * 1024 * 1024


def page(value, offset=0):
    require(type(offset) is int and offset >= 0, 'Invalid evidence offset')
    content = value if type(value) is str else canonical_bytes(value).decode()
    require(offset <= len(content), 'Evidence offset exceeds content')
    return {'text': content[offset:offset+PAGE_CHARS], 'offset': offset,
            'next_offset': offset+PAGE_CHARS if offset+PAGE_CHARS < len(content) else None,
            'total_chars': len(content), 'sha256': sha256(content.encode()).hexdigest()}


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


def build_tools(workspace, context, *, host, output_dir, sources=None):
    """Construct only capabilities authorized for this particular research attempt."""
    library = Library(workspace)
    literature = Literature(output_dir)
    host, output_dir = Path(host), Path(output_dir)
    root = host/context['identity']['case_id']/context['identity']['run_id']
    allowed = {digest(ref): ref for ref in context.get('current_evidence', [])}
    sections = sources if sources is not None else context.get('research_sources', {})
    project_id = context.get('root_goal', {}).get('project_id')

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
        """Save an explicitly provisional wiki/skill/method description, never approve or execute it."""
        require(len(body) <= 60000 and len(title) <= 300, 'Candidate is too large')
        record = library.save(kind, asset_id, title=title, body=body,
                              scope={'applicability': applicability},
                              sources=[{'url': url, 'locator': 'Agent-proposed source; verify before review'} for url in source_urls],
                              expected_revision=expected_revision)
        return {key: record[key] for key in ('kind', 'id', 'revision', 'sha256', 'status')}

    @function_tool(failure_error_function=None)
    async def search_literature(query: str, limit: int = 5) -> dict:
        """Search public INSPIRE literature metadata and abstracts; query must contain no private data."""
        try:
            return await literature.search(query, limit)
        except httpx.HTTPError as error:
            return {'status': 'unavailable', 'reason': type(error).__name__, 'evidence': None}

    @function_tool(failure_error_function=None)
    async def read_paper(arxiv_id: str, offset: int = 0) -> dict:
        """Read a paginated public arXiv HTML paper; unavailable HTML is an explicit failure."""
        try:
            return await literature.read(arxiv_id, offset)
        except httpx.HTTPError as error:
            return {'status': 'unavailable', 'reason': type(error).__name__, 'evidence': None}

    @function_tool(failure_error_function=None)
    async def read_context(section: str, offset: int = 0) -> dict:
        """Read complete Host-supplied evidence sections. Use section='catalog' to list sections and registered files."""
        if section == 'catalog':
            return {'sections': sorted(sections), 'registered_evidence': allowed}
        if section in sections:
            return page(sections[section], offset)
        require(section in allowed, 'Unknown research evidence section')
        ref = allowed[section]
        target = root/ref['member']
        require(target == target.resolve() and target.is_relative_to(root), 'Research evidence escaped Run')
        raw = read_regular(target)
        require(sha256(raw).hexdigest() == ref['sha256'], 'Research evidence changed')
        return page(raw.decode(), offset)

    @function_tool(failure_error_function=None)
    async def read_project_evidence(evidence_sha256: str | None = None, offset: int = 0) -> dict:
        """Read this Run's bound project history or evidence digest; history is not execution authority."""
        from .projects import ProjectStore
        projects = ProjectStore(workspace)
        if evidence_sha256 is None:
            return page({'project': projects.read(project_id), 'runs': projects.runs(project_id)}, offset)
        digest_value(evidence_sha256)
        return page(projects.evidence(project_id, evidence_sha256).decode('utf-8'), offset)

    tools = [search_library, read_asset, read_method_source, save_candidate, search_literature, read_paper,
             read_context]
    if project_id is not None:
        tools.append(read_project_evidence)
    return tools
