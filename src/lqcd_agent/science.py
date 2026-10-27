"""Deterministic scientific roles behind the canonical Agent port."""
import json
from pathlib import Path


class ScientificAgent:
    def __init__(self, host, config, *, provider=None, workspace=None):
        from .settings import workspace_root
        self.host, self.config = Path(host), config
        self.workspace = workspace_root(workspace)
        self.provider = provider
        self.timeout_seconds = provider.config.timeout_seconds if provider else 1

    def run(self, node, context, *, timeout_seconds):
        identity = context['identity']
        output = self.host / 'domain' / identity['attempt_id'] / identity['case_id'] / identity['run_id']
        output.mkdir(parents=True, exist_ok=True)
        diagnostic = {'status': 'success', 'category': 'validated_domain', 'affected_layer': 'none', 'evidence': [],
                      'retryability': 'not_retryable', 'candidates': [], 'confidence': 'unique', 'fingerprint': None,
                      'human_need': None, 'risk': 'low'}
        if node == 'method_planner':
            from .agents.method_planner import run_method_planner
            from .tools.repo_inventory import build_repo_inventory
            result = run_method_planner(user_goal=context['root_goal']['goal'], case_config=self.config,
                repo_inventory={**build_repo_inventory(self.workspace), 'dataset_snapshot': context['root_goal']['dataset_snapshot']},
                output_dir=output, run_id=identity['run_id'], provider=self.provider)
            if result['status'] != 'success' or result['code_needed']:
                diagnostic.update(status='failed', category='implementation_gap', affected_layer='plan', risk='high', human_need='approval')
            content = {'code_needed': False, 'domain_result': result}
        elif node == 'analysis_engineer':
            from .agents.analysis_engineer import run_analysis_engineer
            config = output / 'case.json'
            config.write_text(json.dumps(self.config))
            plan = self._artifact(context, 'method_plan.json')['domain_result']['method_plan_path']
            result = run_analysis_engineer(case_config_path=config, case_id=identity['case_id'], run_id=identity['run_id'],
                run_output_dir=output, method_plan_path=plan, repo_root=self.workspace,
                dataset_snapshot=context['root_goal']['dataset_snapshot'])
            if not result['run_success']:
                diagnostic.update(status='failed', category='analysis_execution', affected_layer='analysis', risk='high', human_need='approval')
            content = {'domain_result': result}
        elif node == 'scientific_reviewer':
            from .agents.scientific_reviewer import run_scientific_reviewer
            result = self._artifact(context, 'run_result.json')['domain_result']
            plan = self._artifact(context, 'method_plan.json')['domain_result']['method_plan_path']
            reviewed = run_scientific_reviewer(run_id=identity['run_id'], case_id=identity['case_id'], run_output_dir=output,
                run_result_path=result['run_result_path'], analysis_outputs_dir=result['analysis_outputs_dir'], method_plan_path=plan, provider=self.provider)
            # Scientific confirmation is Host policy, independent of model confidence or extra fields.
            diagnostic.update(risk='high', category='scientific_review', human_need='approval')
            if reviewed['status'] != 'success':
                diagnostic.update(status='failed', affected_layer='review')
            content = {'domain_result': reviewed}
        else:
            raise ValueError('Unsupported scientific role: ' + node)
        from hashlib import sha256
        content['domain_result']['member_digests'] = {
            str(p.relative_to(self.host)): sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob('*')) if p.is_file() and not p.is_symlink()}
        return {'diagnostic': diagnostic, 'content': content}

    def _artifact(self, context, filename):
        from .control.coordinator import read_regular
        from .control.strict_json import require, loads
        from hashlib import sha256
        matches = [r for r in context['current_evidence'] if Path(r['member']).name == filename]
        require(len(matches) == 1, 'Missing or ambiguous scientific input')
        ref = matches[0]
        root = self.host / context['identity']['case_id'] / context['identity']['run_id']
        path = root / ref['member']
        require(path == path.resolve() and path.is_relative_to(root), 'Scientific input escaped Run')
        raw = read_regular(path)
        require(sha256(raw).hexdigest() == ref['sha256'], 'Scientific input changed')
        value = loads(raw)
        for relative, expected in value['domain_result']['member_digests'].items():
            member = self.host / relative
            require(member == member.resolve() and member.is_relative_to(self.host / 'domain'), 'Scientific member escaped workspace')
            require(sha256(read_regular(member)).hexdigest() == expected, 'Scientific workspace member changed')
        return value
