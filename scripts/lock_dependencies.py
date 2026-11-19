"""Record installed dependency graphs without reading local configuration."""
from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def freeze(roots, name):
    pending = list(roots)
    packages = {}
    while pending:
        name_to_load = pending.pop()
        item = distribution(name_to_load)
        name_canonical = item.metadata['Name'].lower().replace('_', '-')
        if name_canonical in packages:
            continue
        packages[name_canonical] = item.version
        for text in item.requires or []:
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                pending.append(requirement.name)
    output = '# Resolved and tested on Python 3.14 / Windows. Regenerate after dependency upgrades.\n'
    output += '\n'.join(f'{key}=={value}' for key, value in sorted(packages.items())) + '\n'
    (ROOT / 'backend' / name).write_text(output, encoding='utf-8')


runtime = ['fastapi', 'uvicorn', 'pydantic-settings', 'oracledb']
freeze(runtime, 'requirements.lock.txt')
freeze(runtime + ['pytest', 'httpx', 'ruff'], 'requirements-dev.lock.txt')
print('Dependency lock files generated.')
