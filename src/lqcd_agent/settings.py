"""Application-owned settings and credentials, never exported to child processes."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import stat

def workspace_root(path=None):
    """Resolve the operator's workspace, independently of package installation."""
    root = Path(path) if path is not None else Path(os.environ.get('LQCD_AGENT_WORKSPACE', str(Path.cwd())))
    if (not root.is_absolute() or root != root.resolve() or not root.is_dir() or
            root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o002):
        raise ValueError('The operator workspace must be an owned canonical directory.')
    return root


def read_env(path=None):
    path = Path(path) if path is not None else workspace_root() / '.env'
    if not path.exists():
        return {}
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError('The application .env must be an owned private regular file (chmod 600).')
        with os.fdopen(descriptor, encoding='utf-8', closefd=False) as stream:
            lines = stream.read().splitlines()
    finally:
        os.close(descriptor)
    values = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        name, separator, value = line.partition('=')
        if not separator or not name.strip().isidentifier():
            raise ValueError('Invalid application .env entry.')
        values[name.strip()] = value.strip().strip('\"\'')
    return values


def child_environment():
    """Allow only runtime/network plumbing; no API keys or personal Codex overrides."""
    names = {'PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'LD_LIBRARY_PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
             'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy', 'no_proxy',
             'LQCD_AGENT_WORKSPACE'}
    return {k: v for k, v in os.environ.items() if k in names}


@dataclass(frozen=True)
class ApplicationSettings:
    api_key: str = field(repr=False)
    api_base: str = 'https://api.openai.com/v1'
    model: str = 'gpt-6-luna'
    coding_model: str = 'gpt-6-luna'
    timeout_seconds: float = 180
    max_output_tokens: int = 2048
    code_timeout_seconds: float = 240

    @classmethod
    def load(cls, path=None):
        values = read_env(path)
        key = values.get('OPENAI_API_KEY') or os.environ.get('LQCD_AGENT_API_KEY')
        if not key:
            raise ValueError('Configure OPENAI_API_KEY in the private application .env.')
        return cls(api_key=key, api_base=values.get('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                   model=values.get('OPENAI_MODEL', 'gpt-6-luna'),
                   coding_model=values.get('LQCD_CODE_MODEL', values.get('OPENAI_MODEL', 'gpt-6-luna')))

    def provider(self):
        from .llm.base import LLMProviderConfig
        from .llm.openai_client import OpenAIResponsesProvider
        config = LLMProviderConfig(schema_version='0.1', provider='openai', api_base=self.api_base,
            default_model=self.model, timeout_seconds=self.timeout_seconds, max_tokens=self.max_output_tokens)
        return OpenAIResponsesProvider(config, api_key=self.api_key, enabled=True)
