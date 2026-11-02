"""Reusable code is reviewed and frozen before entering the sole Code backend."""
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
    reviewed = library.register_method(asset['id'], **arguments)
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
