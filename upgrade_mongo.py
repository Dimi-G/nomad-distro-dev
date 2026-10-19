#!/usr/bin/env python3
"""
MongoDB Sequential Upgrade Script (5→6→7→8)
Upgrades MongoDB through Docker Compose with proper version compatibility handling.
"""
# /// script
# requires-python = ">=3.8"
# ///

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple
 

def run_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f'Executing: {" ".join(cmd)}')
    try:
        result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout.strip())
        return result
    except subprocess.CalledProcessError as e:
        print(f'Command failed: {e}')
        if e.stderr:
            print(f'Error output: {e.stderr}')
        if check:
            sys.exit(1)
        return e


def backup_mongodb(container_name: str, version: str) -> None:
    """Create a backup of MongoDB data."""
    print('Creating MongoDB backup...')
    backup_path = f'/data/backup_pre_{version}'
    local_backup_path = f'./mongo_backup_pre_{version}'

    run_command(['docker', 'exec', container_name, 'mongodump', '--out', backup_path])
    run_command(['docker', 'cp', f'{container_name}:{backup_path}', local_backup_path])
    print(f'Backup saved to: {local_backup_path}')


def update_compose_file(compose_file: Path, from_version: str, to_version: str) -> None:
    """Update the MongoDB version in docker compose file."""
    print(
        f'Updating docker compose file from mongo:{from_version} to mongo:{to_version}'
    )
    content = compose_file.read_text()
    updated_content = content.replace(f'mongo:{from_version}', f'mongo:{to_version}')

    if content == updated_content:
        print(f'Warning: No changes made. mongo:{from_version} not found.')
    compose_file.write_text(updated_content)


def restart_services(compose_file: Path) -> None:
    """Restart Docker Compose services."""
    print('Restarting Docker Compose services...')
    run_command(['docker', 'compose', '-f', str(compose_file), 'down'], check=False)
    run_command(['docker', 'compose', '-f', str(compose_file), 'pull'], check=False)
    run_command(['docker', 'compose', '-f', str(compose_file), 'up', '-d'])


def wait_for_mongodb(
    container_name: str, timeout: int = 300, interval: int = 5
) -> None:
    """Wait until MongoDB is up and responding."""
    print('Waiting for MongoDB to become ready...')
    start_time = time.time()
    while time.time() - start_time < timeout:
        result = run_command(
            [
                'docker',
                'exec',
                container_name,
                'mongosh',
                '--eval',
                'db.runCommand({ ping: 1 })',
            ],
            check=False,
        )
        if result.returncode == 0:
            print('MongoDB is responding.')
            return
        time.sleep(interval)

    print(f'MongoDB did not respond within {timeout} seconds.')
    sys.exit(1)


def set_feature_compatibility(container_name: str, version: str) -> None:
    """Set the feature compatibility version in MongoDB."""
    print(f'Setting feature compatibility version to {version}...')
    if version == '6.0':
        cmd = f"db.adminCommand({{ setFeatureCompatibilityVersion: '{version}' }})"
    else:
        cmd = f"db.adminCommand({{ setFeatureCompatibilityVersion: '{version}', confirm: true }})"
    run_command(['docker', 'exec', container_name, 'mongosh', '--eval', cmd])


def verify_upgrade(container_name: str) -> None:
    """Verify the MongoDB upgrade was successful."""
    print('Verifying MongoDB upgrade...')
    run_command(['docker', 'exec', container_name, 'mongosh', '--eval', 'db.version()'])
    run_command(
        [
            'docker',
            'exec',
            container_name,
            'mongosh',
            '--eval',
            'db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 })',
        ]
    )


def upgrade_mongodb(
    container_name: str, compose_file: Path, from_version: str, to_version: str
) -> None:
    """Upgrade MongoDB from one version to another."""
    print('=' * 50)
    print(f'Upgrading MongoDB from {from_version} to {to_version}')
    print('=' * 50)

    try:
        backup_mongodb(container_name, to_version)
        update_compose_file(compose_file, from_version, to_version)
        restart_services(compose_file)
        wait_for_mongodb(container_name)
        set_feature_compatibility(container_name, to_version)
        verify_upgrade(container_name)
        print(f'Upgrade to {to_version} completed successfully.\n')
    except Exception as e:
        print(f'Upgrade to {to_version} failed: {e}')
        sys.exit(1)


def update_healthcheck_to_mongosh(compose_file: Path) -> None:
    """Safely update healthcheck command from mongo to mongosh."""
    print("Updating healthcheck command from 'mongo' to 'mongosh'...")

    content = compose_file.read_text()

    pattern = r'(healthcheck:.*?test:.*?- "CMD"\s*- )"mongo"'
    updated_content = re.sub(pattern, r'\1"mongosh"', content, flags=re.DOTALL)

    if content == updated_content:
        print("Warning: No healthcheck 'mongo' command found.")
    else:
        compose_file.write_text(updated_content)
        print("Healthcheck updated to use 'mongosh'.")


def main():
    parser = argparse.ArgumentParser(
        description='MongoDB Sequential Upgrade Script (5→6→7→8)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mongodb_upgrade.py -c mongo_db -f docker compose.yaml
  python mongodb_upgrade.py --container mongo1 --compose-file ./docker compose.yml
""",
    )

    parser.add_argument(
        '-c', '--container', required=True, help='Name of the MongoDB Docker container'
    )
    parser.add_argument(
        '-f',
        '--compose-file',
        required=True,
        type=Path,
        help='Path to the docker compose.yaml file',
    )
    parser.add_argument(
        '--from-version',
        default='5.0.6',
        help='Starting MongoDB version (default: 5.0.6)',
    )
    parser.add_argument(
        '--sleep-between',
        type=int,
        default=10,
        help='Seconds to sleep between upgrades (default: 10)',
    )

    args = parser.parse_args()

    if not args.compose_file.exists():
        print(f'Docker Compose file not found: {args.compose_file}')
        sys.exit(1)

    update_healthcheck_to_mongosh(args.compose_file)

    upgrade_path: List[Tuple[str, str]] = [
        (args.from_version, '6.0'),
        ('6.0', '7.0'),
        ('7.0', '8.0'),
    ]

    print('Starting MongoDB sequential upgrade')
    print(f'Container: {args.container}')
    print(f'Compose file: {args.compose_file}')
    print(f'Upgrade path: {args.from_version} → 6.0 → 7.0 → 8.0\n')

    response = input(
        'This will perform backups and upgrade MongoDB through multiple versions. Continue? (y/N): '
    )
    if response.strip().lower() not in ['y', 'yes']:
        print('Upgrade cancelled by user.')
        sys.exit(0)

    for i, (from_ver, to_ver) in enumerate(upgrade_path):
        upgrade_mongodb(args.container, args.compose_file, from_ver, to_ver)
        if i < len(upgrade_path) - 1:
            print(f'Sleeping {args.sleep_between} seconds before next upgrade...')
            time.sleep(args.sleep_between)

    print('All upgrades completed. MongoDB is now running version 8.0')
    print('Please verify that your application is functioning as expected.')


if __name__ == '__main__':
    main()