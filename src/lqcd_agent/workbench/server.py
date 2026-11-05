"""Loopback-only HTTP adapter; never a second control authority."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from lqcd_agent.control.strict_json import ControlIntegrityError, loads
from .service import RequestError, Workbench

STATIC = Path(__file__).parent/'static'


def create_app(workbench=None):
    service = workbench or Workbench()
    token = secrets.token_urlsafe(32)

    async def supervise():
        while True:
            try:
                await run_in_threadpool(service.ensure_worker)
            except (ValueError, OSError):
                pass
            await asyncio.sleep(2)

    @asynccontextmanager
    async def lifespan(app):
        supervisor = asyncio.create_task(supervise())
        try:
            yield
        finally:
            supervisor.cancel()
            try:
                await supervisor
            except asyncio.CancelledError:
                pass

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def local_session(request, call_next):
        port = request.scope['server'][1]
        authority = '127.0.0.1' if port == 80 else f'127.0.0.1:{port}'
        origin = 'http://'+authority
        if request.headers.get('host') != authority or request.headers.get('origin', origin) != origin:
            return JSONResponse({'error': 'untrusted_origin'}, status_code=403)
        if request.url.path.startswith('/api/') and request.url.path != '/api/session':
            if not secrets.compare_digest(request.headers.get('x-workbench-token', ''), token):
                return JSONResponse({'error': 'invalid_session'}, status_code=403)
        if request.method not in ('GET', 'HEAD') and request.headers.get('origin') != origin:
            return JSONResponse({'error': 'origin_required'}, status_code=403)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})
        return response

    @app.exception_handler(RequestError)
    async def request_error(request, error):
        return JSONResponse({'error': error.code}, status_code=error.status)

    @app.exception_handler(ControlIntegrityError)
    async def integrity_error(request, error):
        return JSONResponse({'error': 'control_rejected_request', 'detail': str(error)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({'error': 'invalid_request'}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, error):
        return JSONResponse({'error': 'evidence_or_run_missing'}, status_code=404)

    def text_evidence(item, raw):
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise RequestError('binary_evidence_has_no_text_preview', 415) from None
        return {'name': item['name'], 'sha256': item['sha256'], 'text': text}

    async def body(request):
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise RequestError('json_required', 415)
        value = bytearray()
        async for chunk in request.stream():
            value.extend(chunk)
            if len(value) > 65536:
                raise RequestError('request_too_large', 413)
        return loads(bytes(value), canonical=False)

    @app.get('/')
    def index():
        return FileResponse(STATIC/'index.html')

    @app.get('/static/{name}')
    def asset(name: str):
        if name not in ('app.js', 'style.css', 'task-desk.js', 'results.js', 'results.css', 'comparison.js', 'evidence.js', 'submissions.js'):
            raise RequestError('unknown_asset', 404)
        return FileResponse(STATIC/name)

    @app.get('/api/session')
    def session():
        return {'token': token, 'host': service.host}

    @app.get('/api/cases')
    def cases():
        return [{k: v for k, v in c.items() if k != 'path'} for c in service.catalog().values()]

    @app.get('/api/cases/{identifier}')
    def case(identifier: str):
        from lqcd_agent.configuration import read_config
        catalog = service.catalog()
        if identifier not in catalog:
            raise RequestError('unknown_case', 404)
        return read_config(catalog[identifier]['path'])

    @app.get('/api/projects')
    def projects():
        return service.projects.list()

    @app.post('/api/projects', status_code=201)
    async def create_project(request: Request):
        return await run_in_threadpool(service.create_project, await body(request))

    @app.get('/api/projects/{project_id}')
    def project(project_id: str, revision: int | None = None):
        return service.projects.read(project_id, revision)

    @app.post('/api/projects/{project_id}')
    async def edit_project(request: Request, project_id: str):
        return await run_in_threadpool(service.edit_project, project_id, await body(request))

    @app.get('/api/projects/{project_id}/contributions')
    def contributions(project_id: str):
        return service.projects.contributions(project_id)

    @app.post('/api/projects/{project_id}/contributions', status_code=201)
    async def contribute(request: Request, project_id: str):
        return await run_in_threadpool(service.contribute, project_id, await body(request))

    @app.get('/api/projects/{project_id}/runs')
    def project_runs(project_id: str):
        return service.project_runs(project_id)

    @app.post('/api/projects/{project_id}/runs', status_code=202)
    async def start_project(request: Request, project_id: str):
        return await run_in_threadpool(service.start_project, project_id, await body(request))

    @app.get('/api/projects/{project_id}/runs/{run_key}')
    def project_run(project_id: str, run_key: str, details: bool = True):
        return service.project_view(project_id, run_key, details=details)

    @app.get('/api/projects/{project_id}/evidence/{identifier}')
    def project_evidence(project_id: str, identifier: str):
        item, raw = service.project_member(project_id, identifier)
        return text_evidence(item, raw)

    @app.get('/api/library')
    def library(query: str = '', kind: str | None = None, status: str | None = None):
        return service.library.search(query, kind=kind, status=status)

    @app.get('/api/library/{kind}/{identifier}')
    def library_asset(kind: str, identifier: str, revision: int | None = None):
        return service.library.read(kind, identifier, revision)

    @app.get('/api/runs')
    def runs():
        return service.runs()

    @app.get('/api/operations/{key}')
    def operation(key: str):
        return service.operation(key)

    @app.post('/api/runs', status_code=202)
    async def start(request: Request):
        return await run_in_threadpool(service.start, await body(request))

    @app.get('/api/runs/{host}/{case}/{run}')
    def view(host: str, case: str, run: str, details: bool = True):
        return service.view(host, {'case_id': case, 'run_id': run}, details=details)

    @app.get('/api/runs/{host}/{case}/{run}/evidence/{identifier}')
    def evidence(host: str, case: str, run: str, identifier: str):
        item, raw = service.member(host, {'case_id': case, 'run_id': run}, identifier)
        return text_evidence(item, raw)

    @app.post('/api/runs/{host}/{case}/{run}/{action}', status_code=202)
    async def action(request: Request, host: str, case: str, run: str, action: str):
        return await run_in_threadpool(service.action, host, {'case_id': case, 'run_id': run}, action, await body(request))

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host='127.0.0.1', port=args.port, proxy_headers=False, access_log=False)


if __name__ == '__main__':
    main()
