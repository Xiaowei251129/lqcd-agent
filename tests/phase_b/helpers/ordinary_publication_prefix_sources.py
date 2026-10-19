"""Capture the original ordinary publication journal without runtime authority."""
from harness.temporary import mkdtemp
from base64 import b64decode
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3

from harness.ordinary_publication_prefix_trace import publication_stage
from harness.trace import event
from helpers.ordinary_sources import captured_source
from helpers.prior_code_evidence_sources import PriorCodeSources
from lqcd_agent.control.strict_json import canonical_bytes, digest, loads


class PublicationPrefixSources(PriorCodeSources):
    def finish(self, trace):
        super().finish(trace)
        proof = trace["proof"]
        records = {row["sha256"]: row["value"] for row in proof["objects"] if row["kind"] == "execution_0_4"}
        public = {}
        for record in records.values():
            key = record["case_id"], record["run_id"]
            if key not in public or record["event_index"] > public[key]["event_index"]:
                public[key] = record
        declarations = []
        for call in self.calls:
            if call["profile"] != "scoped_llm" or call["outcome"] is None or call["exception"] is not None:
                continue
            reservation = records[call["reservation_head"]]
            run = reservation["case_id"], reservation["run_id"]
            settlements = [row for row in records.values() if row.get("event") == "resource_settled" and
                (row["case_id"], row["run_id"]) == run and row["payload"]["resource_operation_id"] == reservation["payload"]["resource_operation_id"]
                and row["payload"]["actual"] is not None]
            if not settlements:
                continue
            settlement, = settlements
            row = self.coordinator.connection.execute("SELECT revision,value FROM invocation_capabilities WHERE capability_id=?",
                                                      (call["capability_id"],)).fetchone()
            journal = loads(row[1])
            identity = call["authorization"]["identity"]
            registered = any(member["member"] == identity["attempt_kind"] + "_diagnostic.json" and
                next(item["value"] for item in proof["objects"] if item["sha256"] == member["registration_head"])["attempt_id"] == identity["attempt_id"]
                for member in proof["ordinary_members"])
            if registered and journal["state"] == "finished":
                continue
            root = self.coordinator.root / run[0] / run[1]
            completion = journal.get("completion_intent")
            projected = []
            checkpoint = False
            checkpoint_committed = False
            if completion is not None:
                plan = completion["artifact_publication"]
                if plan is not None:
                    registration, = [loads(line) for line in plan["content"].encode().splitlines() if
                        loads(line)["event"] == "registered" and loads(line)["attempt_id"] == identity["attempt_id"]]
                    names = {member["canonical_path"]: member["logical_name"] for member in registration["members"]}
                    for member in plan["projections"]:
                        path = root / member["projection_path"]
                        if path.is_file() and path.read_bytes() == b64decode(member["content_base64"], validate=True):
                            projected.append(names[member["canonical_path"]])
                path = root / "checkpoints" / (completion["manifest"]["checkpoint_id"] + ".json")
                checkpoint = path.is_file() and loads(path.read_bytes()) == completion["manifest"]
                connection = sqlite3.connect((root / "checkpoints/graph_checkpoints.sqlite").as_uri() + "?mode=ro", uri=True)
                try:
                    stored = connection.execute("SELECT checkpoint FROM checkpoints WHERE checkpoint_id=?",
                                                (completion["manifest"]["checkpoint_id"],)).fetchone()
                    checkpoint_committed = stored is not None and loads(stored[0]) == completion["checkpoint"]
                finally:
                    connection.close()
            history = (root / "artifact_history.jsonl").read_text()
            index = (root / "artifact_index.json").read_text()
            execution_head = digest(public[run])
            index_source = "current_file"
            if journal["state"] == "finished":
                assert completion is not None and completion["published"] and checkpoint
                from lqcd_agent.control.execution import parse_ledger
                execution_head = parse_ledger(completion["content"].encode()).projection.value["execution_head"]
                index, index_source = completion["index"], "finished_journal_checkpoint"
                if completion["artifact_publication"] is None:
                    prefix = ""
                    for line in ["", *history.splitlines(keepends=True)]:
                        prefix += line
                        if sha256(prefix.encode()).hexdigest() == journal["authorization"]["artifact_history_digest"]:
                            history = prefix
                            break
                    else:
                        raise AssertionError("The original artifact history prefix is unavailable")
                else:
                    history = completion["artifact_publication"]["content"]
            publication = {"execution_head": execution_head, "artifact_history": history,
                           "artifact_index": index, "index_source": index_source,
                           "projected_members": sorted(projected), "checkpoint_committed": checkpoint_committed,
                           "checkpoint_published": checkpoint}
            envelope = captured_source("invocation_publication_journal", deepcopy(journal))
            snapshot = {"schema_version": "0.1", "capability_id": call["capability_id"], "journal_revision": row[0],
                        "binding": proof["binding"], "journal": envelope, "publication": publication}
            raw = canonical_bytes(snapshot)
            snapshot_hash = sha256(raw).hexdigest()
            directory = self.coordinator.root / "trace_prefix_evidence"
            directory.mkdir(exist_ok=True)
            destination = directory / (snapshot_hash + ".json")
            if destination.exists():
                assert destination.read_bytes() == raw
            else:
                destination.write_bytes(raw)
            producer = call["producer"]
            stage = publication_stage(journal, publication)
            declaration = {"schema_version": "0.1", "reservation_head": call["reservation_head"], "settlement_head": digest(settlement),
                "capability_id": call["capability_id"], "producer_operation_id": producer["operation_id"],
                "issuer": {"worker_id": journal["worker_id"], "invocation_epoch": journal["invocation_epoch"],
                           "producer_epoch": producer["lease_epoch"], "producer_revision": producer["phase_revision"]},
                "journal_revision": row[0], "journal": envelope, "publication": publication, "stage": stage,
                "snapshot_sha256": snapshot_hash}
            declarations.append(declaration)
            trace["events"].append(event("ordinary_publication_prefix", run_id=run[1], attempt_id=identity["attempt_id"],
                attempt_kind=identity["attempt_kind"], capability_id=call["capability_id"], operation_id=producer["operation_id"],
                owner=producer["operation_id"], lease_epoch=journal["invocation_epoch"], guard=stage,
                execution_head=publication["execution_head"],
                outcome="actual_settled_publication_prefix"))
        proof.update(schema_version="0.7", ordinary_publication_prefixes=declarations)
        return trace


PREFIX_MODES = {
    'settlement_before': ('budget.resource_settled', 'before'),
    'settlement_after': ('budget.resource_settled', 'after'),
    'completion_before': ('invocation.completion_intent', 'before'),
    'completion_after': ('invocation.completion_intent', 'after'),
    'projection_before': ('invocation.artifact_projection', 'before'),
    'projection_after': ('invocation.artifact_projection', 'after'),
    'history_before': ('invocation.artifact_registration', 'before'),
    'history_after': ('invocation.artifact_registration', 'after'),
    'finished_before': ('invocation.attempt_finished', 'before'),
    'finished_after': ('invocation.attempt_finished', 'after'),
    'index_before': ('invocation.artifact_index_replace', 'before'),
    'index_after': ('invocation.artifact_index_replace', 'after'),
    'checkpoint_before': ('checkpoint.sqlite_commit', 'before'),
    'checkpoint_after': ('checkpoint.sqlite_commit', 'after'),
    'manifest_before': ('file', 'before'),
    'manifest_after': ('file', 'after'),
    'unsettled_return': ('budget.resource_settled', 'before'),
}


def interrupted_source(output, mode, binding, *, material='validated', clock_time=100, identity_label=None):
    """Exit one actual product process; serialize only its passive observations."""
    import os
    from helpers.control_traces import ControlTrace
    from helpers.host_identity_fixture import HostIdentities
    from helpers.ordinary_maximum import PassiveClock
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.control.interfaces import ActorContext, StartRunRequest
    from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
    from test_b04_product_graph import StructuredOutcomes, diagnostic

    output = Path(output)
    with HostIdentities('c22-prefix-' + mode + ('' if identity_label is None else '-' + identity_label)).installed():
        clock = PassiveClock(FakeClock(clock_time, 0))
        coordinator = Coordinator(output, clock=clock)
        sources = PublicationPrefixSources(coordinator)
        capture = ControlTrace(output, version='0.10', ordinary_sources=sources)
        class Port(StructuredOutcomes):
            def run(self, node, context, *, timeout_seconds):
                result = super().run(node, context, timeout_seconds=timeout_seconds)
                if mode == 'exception':
                    raise RuntimeError('Actual controlled C22 exception')
                if mode == 'overrun':
                    clock.subject.advance(2)
                if mode == 'epoch':
                    clock.subject.epoch_id = 'changed_clock_epoch'
                if mode == 'host_rejected':
                    result['content']['run_id'] = 'foreign'
                result['content']['domain_material'] = material
                return result
        outcomes = {'method_planner': diagnostic(status='failed', category='planning_failure', affected_layer='plan',
                                                 human_need='clarification')} if mode == 'domain_non_success' else None
        agent = Port(outcomes)
        actor = ActorContext('operator', 'human', ('control.internal', 'resume', 'start'))
        runtime = CanonicalProductRuntime(coordinator, worker_id='product-host', actor=actor, agent_port=sources.agent(agent))
        locator, armed = None, mode in ('settlement_before', 'settlement_after', 'unsettled_return', 'completion_before')

        def receipt(name, side):
            value = {'schema_version': '0.1', 'process_id': os.getpid(), 'mode': mode, 'boundary': name, 'side': side,
                'binding': binding, 'locator': locator, 'calls': len(agent.contexts), 'clock_reads': clock.reads,
                'events': capture.events, 'observed_records': sorted(capture.observed_records),
                'sources': {key: {k: list(v) for k, v in sources.epochs.items()} if key == 'epochs' else getattr(sources, key)
                    for key in ('calls', 'failures', 'grants', 'epochs', 'maximum_evidence')}}
            (output / 'process-receipt.json').write_bytes(canonical_bytes(value))

        def observer(name, side, value):
            nonlocal armed
            sources.observer(capture, name, side, value)
            if name == 'invocation.completion_intent' and side == 'after':
                armed = True
            if mode in PREFIX_MODES and (name, side) == PREFIX_MODES[mode] and armed:
                receipt(name, side)
                os._exit(97)
        coordinator.observer = observer
        inputs = {'root_goal': {'goal': 'Validate the synthetic observable'}, 'input_snapshot': {'data': 'synthetic'}}
        started = runtime.plane.start_run(StartRunRequest('case', inputs, digest(inputs), 'start', 'balanced_v1'), actor=actor)
        locator = started['result']['run_locator']
        try:
            runtime.run(locator)
        except ValueError:
            assert mode == 'host_rejected'
            runtime.run(locator)
        assert mode in ('exception', 'overrun', 'epoch', 'host_rejected', 'domain_non_success')
        receipt('normal_return', 'after')
        coordinator.close()


def product_prefix_trace(mode, *, material='validated', clock_time=100, recover=False, identity_label=None):
    """Read a stopped process and optionally publish its original frozen suffix."""
    import multiprocessing
    import os
    from pathlib import Path
    from harness.trace import normalize
    from helpers.control_traces import ControlTrace
    from helpers.ordinary_maximum import PassiveClock
    from helpers.trace_sources import current_binding
    from lqcd_agent.control.clock import FakeClock
    from lqcd_agent.control.coordinator import Coordinator
    from lqcd_agent.control.capabilities import ArtifactEffectPort, InvocationLeases
    from lqcd_agent.control.execution import parse_ledger

    output = Path(mkdtemp(prefix='lqcd-agent-b00c22-' + mode + '-', dir='/private/tmp'))
    binding = current_binding()
    process = multiprocessing.get_context('spawn').Process(target=interrupted_source, args=(output, mode, binding),
                                                            kwargs={'material': material, 'clock_time': clock_time, 'identity_label': identity_label})
    process.start()
    process.join(60)
    if process.is_alive():
        process.terminate()
        process.join(10)
        raise AssertionError('The independent C22 source process exceeded its bounded wait')
    assert process.exitcode == (97 if mode in PREFIX_MODES else 0)
    observed = loads((output / 'process-receipt.json').read_bytes())
    assert observed['process_id'] == process.pid != os.getpid() and observed['binding'] == binding and observed['mode'] == mode
    coordinator = Coordinator(output, clock=PassiveClock(FakeClock(clock_time, 0)))
    try:
        sources = PublicationPrefixSources(coordinator)
        for key, value in observed['sources'].items():
            setattr(sources, key, value)
        coordinator.clock.reads[:] = observed['clock_reads']
        capture = ControlTrace(output, version='0.10', ordinary_sources=sources)
        capture.events, capture.observed_records = observed['events'], set(observed['observed_records'])
        coordinator.observer = lambda name, side, value: sources.observer(capture, name, side, value)
        root = output / observed['locator']['case_id'] / observed['locator']['run_id']
        caps = [(row[0], loads(row[1])) for row in coordinator.connection.execute('SELECT capability_id,value FROM invocation_capabilities')]
        key, original = next((key, value) for key, value in caps if value['authorization']['identity']['attempt_kind'] == 'method_planner')
        leases = InvocationLeases(coordinator)
        if mode == 'settlement_before':
            ArtifactEffectPort(leases, None, key, original['worker_id'], original['invocation_epoch']).publish_budget()
        trace = capture.finish(coordinator)
        (output / 'raw.json').write_bytes(canonical_bytes(trace))
        normalized = normalize(trace, binding=binding)
        (output / 'normalized.json').write_bytes(canonical_bytes(normalized))
        prefix = parse_ledger((root / 'execution_history.jsonl').read_bytes())
        facts = {'mode': mode, 'run_status': prefix.projection.value['run_status'], 'calls': observed['calls'],
            'completion_frozen': original.get('completion_intent') is not None,
            'stages': [row['stage'] for row in trace['proof']['ordinary_publication_prefixes']],
            'B04_owned': False, 'actual_process_exit': process.exitcode, 'original_suffix_recovered': False}
        if recover and original.get('completion_intent') is not None and original['state'] == 'started':
            leases.publish_completion(key, original['worker_id'], original['invocation_epoch'])
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            leases.publish_completion(key, original['worker_id'], original['invocation_epoch'])
            assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            normalize(trace, binding=binding)
            facts['original_suffix_recovered'] = True
        elif recover and mode in ('settlement_before', 'settlement_after', 'completion_before', 'unsettled_return'):
            from lqcd_agent.control.interfaces import ActorContext
            from lqcd_agent.graph.analysis_graph import CanonicalProductRuntime
            from test_b04_product_graph import StructuredOutcomes
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            probe = StructuredOutcomes()
            runtime = CanonicalProductRuntime(coordinator, worker_id=original['worker_id'],
                actor=ActorContext('operator', 'human', ('control.internal', 'resume', 'start')), agent_port=sources.agent(probe))
            for _ in range(2):
                try:
                    runtime.run(observed['locator'])
                except ValueError as error:
                    assert 'requires explicit recovery' in str(error)
                else:
                    raise AssertionError('An uncertain target was reexecuted')
            assert not probe.contexts and before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            normalize(trace, binding=binding)
        (output / 'facts.json').write_bytes(canonical_bytes(facts))
        return trace, output, facts
    finally:
        coordinator.close()
