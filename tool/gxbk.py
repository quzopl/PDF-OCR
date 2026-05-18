#!/usr/bin/env python3
"""
gxbk — Backup Manager dla OCR PDF app.

Trzyma backupy projektu (backend/ + frontend/ + docs/ + tool/ + konfigi)
z opisami. Bez zewnętrznych zależności — używa tylko stdlib + systemowego `tar`.

Użycie:
    gxbk new "opis zmiany"          — utwórz backup z opisem
    gxbk new                         — pyta o opis interaktywnie
    gxbk list                        — lista wszystkich backupów (najnowsze pierwsze)
    gxbk show <id>                   — szczegóły jednego backupu
    gxbk restore <id>                — przywróć backup (z safety backup'em obecnego stanu)
    gxbk delete <id>                 — usuń backup z indeksu i z dysku
    gxbk migrate                     — zaimportuj istniejące *.tar.gz z roota repo

ID-y mogą być częściowe — np. `gxbk show 1137` znajdzie po fragmencie.

Pliki:
    backups/<id>.tar.gz              — sam archiwum
    backups/<id>.meta.json           — metadane (timestamp, opis, rozmiar, lista plików, git status)
    backups/index.json               — indeks wszystkich backupów (do szybkiego list)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # /home/bart/market_ai_mvp/
BACKUPS_DIR = ROOT / 'backups'
INDEX_FILE = BACKUPS_DIR / 'index.json'

# Co pakować przy `new` (jeśli istnieje):
DEFAULT_INCLUDE = [
    'backend',                   # FastAPI app + tests + pyproject (bez .venv/__pycache__)
    'frontend',                  # Next.js app (bez node_modules/.next)
    'docs',                      # specs + plany
    'tool',                      # samo gxbk
    '.env',                      # lokalna konfiguracja (jeśli istnieje)
    '.env.example',
    '.gitignore',
    'Makefile',
    'README.md',
    'start.sh',
]
DEFAULT_EXCLUDE = [
    'backups',                   # nie backupuj samych backupów
    '.venv',
    'venv',
    '.git',
    '.claude',
    '.pytest_cache',
    '.ruff_cache',
    '.mypy_cache',
    '__pycache__',
    '*.pyc',
    'node_modules',
    '.next',
    '.pnpm-store',
    'test-results',
    'playwright-report',
    'backend/tests/fixtures',    # generowane przez conftest, nie commitowane
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def slugify(s, maxlen=40):
    s = re.sub(r'[^a-zA-Z0-9À-ɏ]+', '-', s.lower()).strip('-')
    return s[:maxlen] or 'unnamed'

def load_index():
    if not INDEX_FILE.exists():
        return {'backups': []}
    try:
        return json.loads(INDEX_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[gxbk] WARN: index.json uszkodzony ({e}), startuję pusty', file=sys.stderr)
        return {'backups': []}

def save_index(idx):
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding='utf-8')

def find_backup(idx, query):
    """Znajdź backup po fragmencie ID. Zwraca (None, error_msg) jeśli brak/wieloznaczne."""
    matches = [b for b in idx['backups'] if query in b['id']]
    if not matches:
        return None, f'Brak backupu pasującego do "{query}".'
    if len(matches) > 1:
        ids = '\n  '.join(b['id'] for b in matches)
        return None, f'Wieloznaczne ({len(matches)} pasuje):\n  {ids}'
    return matches[0], None

def fmt_size(b):
    if b > 1024 * 1024:
        return f'{b/1024/1024:.1f} MB'
    if b > 1024:
        return f'{b/1024:.1f} KB'
    return f'{b} B'

def fmt_ts(iso):
    """ISO → human-readable krótki format."""
    try:
        dt = datetime.fromisoformat(iso.replace('Z',''))
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso

# ── Commands ─────────────────────────────────────────────────────────────────
def cmd_new(args):
    desc = args.description or ''
    if not desc:
        try:
            desc = input('Opis zmian: ').strip()
        except EOFError:
            print('[gxbk] Brak opisu (stdin EOF) — anuluję.', file=sys.stderr)
            sys.exit(1)
    if not desc:
        print('[gxbk] Opis nie może być pusty.', file=sys.stderr)
        sys.exit(1)

    ts = datetime.now()
    id_ = ts.strftime('%Y-%m-%d_%H%M') + '_' + slugify(desc, 40)

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    tar_path = BACKUPS_DIR / f'{id_}.tar.gz'
    meta_path = BACKUPS_DIR / f'{id_}.meta.json'

    if tar_path.exists():
        print(f'[gxbk] Backup o tym ID już istnieje: {id_}', file=sys.stderr)
        sys.exit(1)

    # Zbierz to co istnieje
    includes = [p for p in DEFAULT_INCLUDE if (ROOT / p).exists()]
    if not includes:
        print('[gxbk] Nic do spakowania (sprawdź ścieżki w DEFAULT_INCLUDE).', file=sys.stderr)
        sys.exit(1)

    tar_args = ['tar', '-czf', str(tar_path)]
    for ex in DEFAULT_EXCLUDE:
        tar_args.extend(['--exclude', ex])
    tar_args.extend(includes)

    print(f'[gxbk] Pakowanie ({len(includes)} ścieżek)... → {tar_path.name}')
    res = subprocess.run(tar_args, cwd=ROOT)
    if res.returncode != 0:
        print(f'[gxbk] tar zwrócił błąd ({res.returncode}). Backup NIE utworzony.', file=sys.stderr)
        if tar_path.exists():
            tar_path.unlink()
        sys.exit(1)

    size = tar_path.stat().st_size
    try:
        file_list = subprocess.check_output(['tar', '-tzf', str(tar_path)]).decode('utf-8', errors='replace').splitlines()
        file_count = len(file_list)
    except Exception:
        file_list = []
        file_count = 0

    # Git status snapshot (jeśli to repo git)
    git_status = ''
    git_head = ''
    try:
        git_status = subprocess.check_output(
            ['git', 'status', '--short'], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='replace').strip()
        git_head = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='replace').strip()
    except Exception:
        pass

    meta = {
        'id': id_,
        'timestamp': ts.isoformat(),
        'description': desc,
        'size_bytes': size,
        'file_count': file_count,
        'includes': includes,
        'git_head': git_head,
        'git_status': git_status,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')

    idx = load_index()
    idx['backups'].append(meta)
    save_index(idx)

    print(f'[gxbk] OK  id={id_}')
    print(f'        size={fmt_size(size)}  files={file_count}')
    if git_head:
        print(f'        git={git_head}{"  (dirty)" if git_status else ""}')
    return id_

def cmd_list(args):
    idx = load_index()
    if not idx['backups']:
        print('Brak backupów. Stwórz pierwszy: gxbk new "opis"')
        return

    backups = sorted(idx['backups'], key=lambda b: b['timestamp'], reverse=True)
    print(f'{"DATE":<17} {"SIZE":>8}  {"FILES":>6}  ID / OPIS')
    print('-' * 100)
    for b in backups:
        date = fmt_ts(b['timestamp'])
        size = fmt_size(b['size_bytes'])
        files = b.get('file_count', 0)
        # Wyświetl ID (skrócony do daty+slug) i opis
        short_id = b['id'].split('_', 2)[-1] if '_' in b['id'] else b['id']
        print(f'{date:<17} {size:>8}  {files:>6}  {short_id}')
        print(f'{"":<17} {"":<8}          ↳ {b["description"]}')
    print(f'\n  Razem: {len(backups)} backup(ów). Pełny ID: gxbk show <fragment>')

def cmd_show(args):
    idx = load_index()
    b, err = find_backup(idx, args.id)
    if err:
        print(f'[gxbk] {err}', file=sys.stderr)
        sys.exit(1)
    print(json.dumps(b, indent=2, ensure_ascii=False))
    tar_path = BACKUPS_DIR / f'{b["id"]}.tar.gz'
    if tar_path.exists():
        print(f'\nplik: {tar_path}')
    else:
        print(f'\n[!] plik nie istnieje na dysku: {tar_path}')

def cmd_restore(args):
    idx = load_index()
    b, err = find_backup(idx, args.id)
    if err:
        print(f'[gxbk] {err}', file=sys.stderr)
        sys.exit(1)

    tar_path = BACKUPS_DIR / f'{b["id"]}.tar.gz'
    if not tar_path.exists():
        print(f'[gxbk] Plik tarball nie istnieje: {tar_path}', file=sys.stderr)
        sys.exit(1)

    print(f'Backup do przywrócenia:')
    print(f'  ID:    {b["id"]}')
    print(f'  Data:  {fmt_ts(b["timestamp"])}')
    print(f'  Opis:  {b["description"]}')
    print(f'  Pliki: {b.get("file_count", "?")}')
    print(f'\nUWAGA: To NADPISZE pliki w {ROOT}.')
    print('       Najpierw zostanie zrobiony safety-backup obecnego stanu.')

    if not args.force:
        try:
            ans = input('Potwierdź (yes/no): ').strip().lower()
        except EOFError:
            print('Anulowano.', file=sys.stderr)
            sys.exit(1)
        if ans not in ('yes', 'y', 'tak', 't'):
            print('Anulowano.')
            return

    # Safety backup
    safety_args = argparse.Namespace(description=f'AUTO przed restore {b["id"][:30]}')
    print('\n[gxbk] Tworzę safety-backup obecnego stanu...')
    safety_id = cmd_new(safety_args)

    # Extract
    print(f'\n[gxbk] Restore z {tar_path.name}...')
    res = subprocess.run(['tar', '-xzf', str(tar_path)], cwd=ROOT)
    if res.returncode != 0:
        print(f'[gxbk] tar -xzf zwrócił błąd ({res.returncode}). Stan może być niespójny.', file=sys.stderr)
        print(f'        Safety backup: {safety_id} — możesz go restore-ować jeśli coś poszło nie tak.', file=sys.stderr)
        sys.exit(1)
    print(f'[gxbk] OK. Safety backup: {safety_id}')

def cmd_delete(args):
    idx = load_index()
    b, err = find_backup(idx, args.id)
    if err:
        print(f'[gxbk] {err}', file=sys.stderr)
        sys.exit(1)

    print(f'Backup do usunięcia: {b["id"]}')
    print(f'  Opis: {b["description"]}')
    if not args.force:
        try:
            ans = input('Potwierdź (yes/no): ').strip().lower()
        except EOFError:
            sys.exit(1)
        if ans not in ('yes', 'y', 'tak', 't'):
            print('Anulowano.')
            return

    tar_path = BACKUPS_DIR / f'{b["id"]}.tar.gz'
    meta_path = BACKUPS_DIR / f'{b["id"]}.meta.json'
    for p in (tar_path, meta_path):
        if p.exists():
            p.unlink()

    idx['backups'] = [x for x in idx['backups'] if x['id'] != b['id']]
    save_index(idx)
    print(f'[gxbk] Usunięto {b["id"]}')

def cmd_migrate(args):
    """Zaimportuj istniejące *.tar.gz z /refacor/ root i z poprzednich miejsc do indeksu."""
    idx = load_index()
    existing_ids = {b['id'] for b in idx['backups']}

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    # Wzorce nazw historycznych:
    # frontend.backup-2026-04-27-1137-stopnav-fix-OK.tar.gz
    # backend.backup-2026-04-27-1118-pre-launcher-osrm.tar.gz
    # project.backup-2026-04-27-1127.tar.gz
    pattern = re.compile(r'^(\w+)\.backup-(\d{4})-(\d{2})-(\d{2})(?:-(\d{4}))?(?:-(.+))?$')

    found = list(ROOT.glob('*.tar.gz'))
    imported = 0
    skipped = 0

    for f in sorted(found):
        if f.parent == BACKUPS_DIR:
            continue  # już w nowej lokalizacji
        stem = f.name.replace('.tar.gz', '')
        m = pattern.match(stem)
        if not m:
            print(f'  [skip] {f.name}  (nieznany wzorzec)')
            skipped += 1
            continue

        kind, yr, mo, dy, hm, slug_part = m.groups()
        hm = hm or '0000'
        try:
            ts = datetime(int(yr), int(mo), int(dy), int(hm[:2]), int(hm[2:]))
        except ValueError:
            print(f'  [skip] {f.name}  (zły timestamp)')
            skipped += 1
            continue

        slug_part = slug_part or kind
        id_ = ts.strftime('%Y-%m-%d_%H%M') + '_' + slugify(f'{kind}-{slug_part}', 40)

        if id_ in existing_ids:
            print(f'  [skip] {f.name}  (już w indeksie jako {id_})')
            skipped += 1
            continue

        new_path = BACKUPS_DIR / f'{id_}.tar.gz'
        if not new_path.exists():
            print(f'  [copy] {f.name} → backups/{new_path.name}')
            shutil.copy2(f, new_path)

        size = new_path.stat().st_size
        try:
            file_count = len(subprocess.check_output(['tar', '-tzf', str(new_path)]).decode().splitlines())
        except Exception:
            file_count = 0

        meta = {
            'id': id_,
            'timestamp': ts.isoformat(),
            'description': f'(migracja) {kind} — {slug_part.replace("-", " ")}',
            'size_bytes': size,
            'file_count': file_count,
            'imported_from': f.name,
        }
        idx['backups'].append(meta)
        existing_ids.add(id_)
        meta_path = BACKUPS_DIR / f'{id_}.meta.json'
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
        imported += 1

    save_index(idx)
    print(f'\n[gxbk] Migracja zakończona. Imported: {imported}, skipped: {skipped}')
    print(f'        Total w indeksie: {len(idx["backups"])}')
    if imported:
        print(f'        Oryginały zostawione w {ROOT} (nie usunięte). Po sprawdzeniu możesz')
        print(f'        je skasować ręcznie, kopie są już w backups/.')

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        prog='gxbk',
        description='Geonyx backup manager — backupy z opisami i indeksem.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Pliki:')[0] if __doc__ else '',
    )
    sub = ap.add_subparsers(dest='cmd', metavar='COMMAND', required=True)

    p = sub.add_parser('new', help='Stwórz nowy backup z opisem')
    p.add_argument('description', nargs='?', help='Opis zmian (jeśli brak — pyta interaktywnie)')
    p.set_defaults(func=cmd_new)

    p = sub.add_parser('list', help='Lista backupów (najnowsze pierwsze)')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('show', help='Szczegóły backupu (po fragmencie ID)')
    p.add_argument('id', help='ID lub fragment (np. "1137" albo "stopnav")')
    p.set_defaults(func=cmd_show)

    p = sub.add_parser('restore', help='Przywróć backup (z safety backup obecnego stanu)')
    p.add_argument('id', help='ID lub fragment')
    p.add_argument('--force', action='store_true', help='Bez potwierdzenia')
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser('delete', help='Usuń backup z indeksu i z dysku')
    p.add_argument('id')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser('migrate', help='Zaimportuj istniejące *.tar.gz z roota repo do indeksu')
    p.set_defaults(func=cmd_migrate)

    args = ap.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
