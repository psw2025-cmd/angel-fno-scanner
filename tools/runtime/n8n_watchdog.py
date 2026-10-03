#!/usr/bin/env python3
"""Bounded recovery of existing n8n and the single local sandbox Compose project."""
import fcntl
import json
import subprocess
import time
import urllib.request
from pathlib import Path

STATE = Path('/var/lib/angel-n8n-watchdog/state.json')
COMPOSE = ['docker', 'compose', '-p', 'angel-n8n-sandbox', '-f', '/opt/n8n-sandbox-service/compose.yaml']
USERCTL = ['systemctl', '--machine=pritam@.host', '--user']


def run(args, timeout=10):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    # Never log arbitrary command output: service environments may contain secrets.
    if result.returncode:
        raise RuntimeError('command failed: ' + ' '.join(args[:3]))
    return result.stdout.strip()


def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=5) as r:
            return r.status == 200 and json.load(r) == {'status': 'ok'}
    except Exception:
        return False


def container_health(service):
    try:
        ids = run(COMPOSE + ['ps', '-a', '-q', service]).splitlines()
        if len(ids) != 1:
            return False
        result = json.loads(run(['docker', 'inspect', '--format', '{{json .State}}', ids[0]]))
        return result['Running'] and result.get('Health', {}).get('Status') == 'healthy'
    except Exception:
        return False


def observe():
    try:
        n8n_active = run(USERCTL + ['is-active', 'n8n.service']) == 'active'
    except Exception:
        n8n_active = False
    return {'n8n': health(5678) and n8n_active, 'api': health(8080) and container_health('api'),
            'runner': container_health('runner')}


def save_state(state):
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2) + '\n')
    temp.replace(STATE)


def main():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open('/run/angel-n8n-watchdog.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            state = json.loads(STATE.read_text())
        except (FileNotFoundError, ValueError):
            state = {'failures': {}, 'last_recovery': {}, 'recoveries': {}}
        checks = observe()
        now = time.time()
        actions = []
        errors = []
        for name, healthy in checks.items():
            state['failures'][name] = 0 if healthy else state['failures'].get(name, 0) + 1
            # Require two failed samples; allow four minutes for runner warmup after recovery.
            if healthy or state['failures'][name] < 2 or now - state['last_recovery'].get(name, 0) < 240:
                continue
            state['last_recovery'][name] = now
            state['recoveries'][name] = state['recoveries'].get(name, 0) + 1
            # Persist attempted recovery before any external command can hang or be killed.
            state.update({'checked_at_utc_epoch': now, 'health': checks,
                          'actions': actions, 'errors': errors})
            save_state(state)
            try:
                if name == 'n8n':
                    # Existing user service owns n8n; do not install another n8n instance.
                    run(USERCTL + ['restart', 'n8n.service'], timeout=30)
                else:
                    run(['systemctl', 'start', 'docker.service', 'sysbox.service'], timeout=30)
                    ids = run(COMPOSE + ['ps', '-a', '-q', name]).splitlines()
                    if not ids:
                        run(COMPOSE + ['up', '-d', name], timeout=60)
                    else:
                        run(COMPOSE + ['restart', name], timeout=30)
                actions.append(name)
            except Exception as exc:
                errors.append(name + ': ' + type(exc).__name__)
        state.update({'checked_at_utc_epoch': now, 'health': observe() if actions else checks,
                      'actions': actions, 'errors': errors})
        save_state(state)
        print(json.dumps({'health': state['health'], 'actions': actions, 'errors': errors}))
        if not all(state['health'].values()) or errors:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
