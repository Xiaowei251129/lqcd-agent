"""One strict JSON/YAML loader for case, task and provider configuration."""
from pathlib import Path
from typing import Any
import yaml


class _ConfigLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        value = {}
        for key, item in self.construct_pairs(node, deep=deep):
            if not isinstance(key, str) or key in value:
                raise ValueError('Configuration keys must be unique strings.')
            value[key] = item
        return value


def read_config(path: str | Path) -> dict[str, Any]:
    """Load JSON/YAML once, rejecting duplicate keys and non-JSON values."""
    from lqcd_agent.control.strict_json import canonical_bytes, loads
    config_path = Path(path)
    text = config_path.read_text(encoding='utf-8')
    if config_path.suffix == '.json':
        value = loads(text, canonical=False)
    elif config_path.suffix in ('.yaml', '.yml'):
        try:
            value = yaml.load(text, Loader=_ConfigLoader)
        except yaml.YAMLError as error:
            raise ValueError('Invalid YAML configuration') from error
    else:
        raise ValueError('Configuration must be JSON or YAML.')
    if not isinstance(value, dict):
        raise ValueError('Configuration must be an object.')
    canonical_bytes(value)
    return value
