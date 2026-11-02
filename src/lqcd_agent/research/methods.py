"""Freeze reviewed reuse inputs for one Run; they never become a second executor."""
from hashlib import sha256
from lqcd_agent.control.strict_json import closed, require
from .library import Library


def snapshot_methods(config, workspace):
    dependencies = config.get('method_dependencies', [])
    require(type(dependencies) is list and len(dependencies) <= 8, 'Use at most eight explicit method dependencies')
    result = []
    library = Library(workspace)
    for dependency in dependencies:
        closed(dependency, ('id', 'revision', 'sha256'))
        record, raw = library.method_snapshot(dependency['id'])
        require(all(record[key] == dependency[key] for key in dependency), 'Method dependency needs current review')
        require(len(raw) <= 128*1024, 'Reusable method source exceeds 128 KiB')
        result.append({'id': record['id'], 'revision': record['revision'], 'asset_sha256': record['sha256'],
                       'source_sha256': sha256(raw).hexdigest(), 'source': raw.decode('utf-8'),
                       'scope': record['scope'], 'validation': record['implementation']['validation']})
    require(len({r['id'] for r in result}) == len(result), 'Duplicate method dependency')
    return result


def method_files(snapshots):
    files = {}
    for snapshot in snapshots:
        from lqcd_agent.control.coordinator import component
        component(snapshot['id'])
        raw = snapshot['source'].encode('utf-8')
        require(sha256(raw).hexdigest() == snapshot['source_sha256'], 'Frozen reusable source changed')
        files['reused/'+snapshot['id']+'.py'] = raw
    return files
