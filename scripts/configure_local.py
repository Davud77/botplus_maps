#!/usr/bin/env python3
"""Create the local-only Compose configuration without overwriting existing secrets."""
from pathlib import Path
import os
import secrets


def main():
    project = Path(__file__).resolve().parents[1]
    (project / 'data' / 'sources').mkdir(parents=True, exist_ok=True)
    target = project / '.env.local'
    content = '\n'.join([
        '# Local-only configuration. Do not commit or share this file.',
        'COMPOSE_PROJECT_NAME=botplus-local',
        'APP_PORT=5580',
        'POSTGRES_PASSWORD=' + secrets.token_urlsafe(32),
        'MINIO_ROOT_USER=botpluslocal',
        'MINIO_ROOT_PASSWORD=' + secrets.token_urlsafe(32),
        'SECRET_KEY=' + secrets.token_urlsafe(48),
        'JWT_SECRET=' + secrets.token_urlsafe(48),
        '',
    ])
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print('.env.local already exists; existing configuration preserved.')
        return
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(content)
    print('Created .env.local. Start compose.local.yml and open http://localhost:5580')


if __name__ == '__main__':
    main()
