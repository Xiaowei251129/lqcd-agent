import os
from pathlib import Path
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator, exclusive_directory
from lqcd_agent.control.strict_json import ControlIntegrityError

def reservation_client(pipe, root, overlay, payload):
    coordinator = Coordinator(root, clock=FakeClock(100, 0))
    try:
        pipe.send('ready')
        assert pipe.recv() == 'go'
        try:
            result = coordinator.reserve('start_run', 'not_applicable', 'scope', 'key', payload, 'worker', lambda *_: overlay, lease_seconds=10)
            pipe.send(('reserved', result))
        except ControlIntegrityError as error:
            pipe.send(('rejected', str(error)))
    finally:
        coordinator.close()
        pipe.close()

def publication_client(pipe, root, overlay, crash):

    def observer(name, side, value):
        if crash and (name, side) == ('bootstrap.policy.file_sync', 'after'):
            os._exit(83)
    coordinator = Coordinator(root, clock=FakeClock(110, 10) if not crash else FakeClock(100, 0), observer=observer)
    try:
        if crash:
            operation = coordinator.reserve('start_run', 'not_applicable', 'scope', 'key', {}, 'worker', lambda *_: overlay, lease_seconds=10)
        else:
            operation = coordinator.lookup_key('scope', 'key')
            operation = coordinator.acquire(operation['operation_id'], 'restarted', lease_seconds=10)
        locator = operation['reservation']['reserved_run_locator']
        run_root = Path(root) / locator['case_id'] / locator['run_id']

        def advance(phase, publish):
            return coordinator.step(operation['operation_id'], operation['worker_owner_id'], operation['lease_epoch'], operation['phase_revision'], phase, publish)
        if crash:

            def create(db, current):
                exclusive_directory(run_root.parent)
                exclusive_directory(run_root)
                return {'reserved_run_locator': locator, 'current_lease_epoch': current['lease_epoch']}
            operation = advance('run_root_created', create)
            coordinator.freeze_publication(operation['operation_id'], 'worker', 1, 2, 'policy_published', run_root / 'budget_policy.json', overlay['canonical_budget_policy_bytes'].encode())

        def publish(db, current):
            coordinator.materialize_publication(db, current, 'policy_published', run_root / 'budget_policy.json', name='bootstrap.policy')
            return {'canonical_policy_bytes': current['reservation']['canonical_budget_policy_bytes'], 'policy_digest': current['reservation']['budget_policy_digest']}
        operation = advance('policy_published', publish)
        pipe.send((operation, coordinator.history(operation['operation_id'])))
    finally:
        coordinator.close()
        pipe.close()
