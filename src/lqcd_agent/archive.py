"""Bounded portable evidence bundles; never database backups or executable Runs."""
from hashlib import sha256
import io
import os
from pathlib import Path, PurePosixPath
import stat
import zipfile
from .control.coordinator import read_regular, sync_directory
from .control.strict_json import canonical_bytes, closed, digest_value, loads, number, require
from .inspection import read_snapshot

MAX_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 10000
DOMAIN_ARTIFACTS = {'method_plan.json', 'run_result.json', 'scientific_review_report.json'}


def _member_name(name):
    path = PurePosixPath(name)
    require(type(name) is str and name and not path.is_absolute() and '\\' not in name and
            path.as_posix() == name and not any(part in ('.', '..') for part in path.parts), 'Unsafe archive member')
    return name


def archive_run(host, locator):
    snapshot = read_snapshot(host, locator)
    require(snapshot.closure is not None and snapshot.closure['terminal_closure'] == 'committed',
            'Only a terminated Run with committed closure can be archived')
    members = {'control_snapshot.json': canonical_bytes({'control':snapshot.control,'closure':snapshot.closure})}
    sources = {}
    domain_members = {}
    size = len(members['control_snapshot.json'])

    def collect(name, path, expected=None):
        nonlocal size
        _member_name(name)
        require(path == path.resolve() and path.is_file(), 'Archive source was redirected')
        require(path.stat().st_size <= MAX_BYTES-size, 'Archive exceeds the 256 MiB evidence limit')
        raw = read_regular(path)
        require(expected is None or sha256(raw).hexdigest() == expected, 'Scientific archive source changed')
        if name in members:
            require(members[name] == raw, 'Conflicting archive member')
            return
        size += len(raw)
        require(size <= MAX_BYTES and len(members) < MAX_MEMBERS, 'Archive evidence limit exceeded')
        members[name], sources[path] = raw, sha256(raw).hexdigest()

    for path in sorted(snapshot.root.rglob('*')):
        relative = path.relative_to(snapshot.root)
        require(not path.is_symlink(), 'Archive source contains a symlink')
        # Checkpoint SQLite remains in its authority domain; never copy its live files.
        if 'checkpoints' in relative.parts or path.is_dir():
            continue
        name = 'run/'+relative.as_posix()
        collect(name, path)
        if path.name in DOMAIN_ARTIFACTS and relative.parts[0] == 'attempts':
            value = loads(members[name], canonical=False)
            result = value.get('domain_result', {})
            for member, expected in result.get('member_digests', {}).items():
                _member_name(member)
                require(member.startswith('domain/'), 'Scientific archive member escaped domain')
                require(member not in domain_members or domain_members[member] == expected, 'Conflicting scientific archive source')
                domain_members[member] = expected
    for member, expected in sorted(domain_members.items()):
        collect(member, snapshot.host/member, expected)
    manifest = {'schema_version':'0.1', 'kind':'lqcd_evidence_archive', 'run_locator':locator,
        'execution_head':snapshot.state['execution_head'], 'run_status':snapshot.state['run_status'],
        'members':{name:{'sha256':sha256(raw).hexdigest(),'size_bytes':len(raw)} for name,raw in sorted(members.items())}}
    members['archive_manifest.json'] = canonical_bytes(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as bundle:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.create_system, info.external_attr = 3, (stat.S_IFREG | 0o600) << 16
            bundle.writestr(info, raw)
    payload = buffer.getvalue()
    require(len(payload) <= MAX_BYTES, 'Archive exceeds the 256 MiB evidence limit')
    current = read_snapshot(host, locator)
    require(current.control == snapshot.control and current.closure == snapshot.closure and
            all(sha256(read_regular(path)).hexdigest() == expected for path,expected in sources.items()),
            'Run changed during archive creation')
    folder = snapshot.host/'archives'
    folder.mkdir(mode=0o700, exist_ok=True)
    require(folder == folder.resolve() and folder.is_dir(), 'Archive directory was redirected')
    target = folder/(sha256(payload).hexdigest()+'.zip')
    existing = target.exists() or target.is_symlink()
    if existing:
        require(read_regular(target) == payload, 'Conflicting archive publication')
    flags = os.O_RDONLY if existing else os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags | os.O_NOFOLLOW, 0o600)
    try:
        if not existing:
            with os.fdopen(descriptor, 'wb', closefd=False) as stream:
                stream.write(payload)
                stream.flush()
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    sync_directory(folder)
    sync_directory(snapshot.host)
    return {'archive':str(target),'sha256':sha256(payload).hexdigest(),'run_locator':locator,'execution_head':manifest['execution_head']}


def verify_archive(path):
    path = Path(path)
    require(path == path.resolve() and path.is_file() and path.stat().st_uid == os.getuid(), 'Invalid archive file')
    require(path.stat().st_size <= MAX_BYTES, 'Archive exceeds the 256 MiB evidence limit')
    payload = read_regular(path)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
            infos = bundle.infolist()
            names = [item.filename for item in infos]
            require(len(names) <= MAX_MEMBERS+1 and len(names) == len(set(names)), 'Duplicate or excessive archive members')
            for item in infos:
                _member_name(item.filename)
                require(item.compress_type == zipfile.ZIP_STORED and item.create_system == 3 and
                        stat.S_ISREG(item.external_attr >> 16) and not item.flag_bits & 1 and
                        item.file_size <= MAX_BYTES, 'Unsupported archive member type')
            require(sum(item.file_size for item in infos) <= MAX_BYTES, 'Archive content limit exceeded')
            require('archive_manifest.json' in names, 'Missing archive manifest')
            manifest = loads(bundle.read('archive_manifest.json'))
            closed(manifest, ('schema_version','kind','run_locator','execution_head','run_status','members'))
            require(manifest['schema_version'] == '0.1' and manifest['kind'] == 'lqcd_evidence_archive' and
                    manifest['run_status'] in ('completed','failed','halted'), 'Invalid archive manifest')
            digest_value(manifest['execution_head'])
            require(set(names) == set(manifest['members']) | {'archive_manifest.json'}, 'Archive inventory mismatch')
            for name, expected in manifest['members'].items():
                closed(expected, ('sha256','size_bytes'))
                digest_value(expected['sha256'])
                number(expected['size_bytes'], integer=True)
                raw = bundle.read(name)
                require(len(raw) == expected['size_bytes'] and sha256(raw).hexdigest() == expected['sha256'], 'Archive member digest mismatch')
            control = loads(bundle.read('control_snapshot.json'))
            require(control['control']['projection']['execution_head'] == manifest['execution_head'] and
                    control['control']['locator'] == manifest['run_locator'] and
                    control['closure']['terminal_closure'] == 'committed' and
                    control['closure']['run_status'] == manifest['run_status'], 'Archive control snapshot mismatch')
    except (zipfile.BadZipFile, KeyError, TypeError) as error:
        raise ValueError('Invalid evidence archive') from error
    return {'valid':True,'sha256':sha256(payload).hexdigest(),'run_locator':manifest['run_locator'],
            'execution_head':manifest['execution_head'],'run_status':manifest['run_status'],'members':len(manifest['members'])}
