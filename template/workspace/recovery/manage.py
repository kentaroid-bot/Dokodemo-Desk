#!/usr/bin/env python3
"""Local backup and restore to a new folder; no network or overwrite."""
import argparse
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


def excluded(parts):
    return any(p.startswith('.') and p != '.gitignore' for p in parts) or '__pycache__' in parts or (
        len(parts) > 2 and parts[:2] == ('workspace', 'runtime') and parts != ('workspace', 'runtime', 'README.md'))


def backup(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    if target == root or root in target.parents:
        raise ValueError('保存ZIPは仕事場の外に置いてください。')
    paths, skipped = [], []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if path.is_symlink():
            skipped.append(str(relative))
        elif path.is_file() and not excluded(relative.parts) and path.suffix not in ('.pyc', '.zip'):
            paths.append((path, relative))
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, relative in paths:
            archive.write(path, str(relative))
    return len(paths), skipped


def restore(source, destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('復元先は、まだ存在しない新しいフォルダにしてください。')
    with zipfile.ZipFile(source) as archive:
        seen, entries, total = set(), [], 0
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            total += entry.file_size
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename
                    or not path.parts or excluded(path.parts) or str(path) in seen
                    or stat.S_ISLNK(entry.external_attr >> 16) or total > 512 * 1024 * 1024):
                raise ValueError('この保存ZIPは復元条件を満たしていません。原本を確認してください。')
            seen.add(str(path))
            entries.append((entry, path))
        if 'START.md' not in seen or 'workspace/site.json' not in seen:
            raise ValueError('仕事場の保存ZIPではありません。')
        destination.mkdir(parents=True)
        for entry, path in entries:
            out = destination.joinpath(*path.parts)
            if entry.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open('xb') as stream:
                    stream.write(archive.read(entry))
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='仕事場を保存し、新しいフォルダへ戻します。')
    sub = parser.add_subparsers(dest='command', required=True)
    save = sub.add_parser('backup')
    save.add_argument('zip_path')
    load = sub.add_parser('restore')
    load.add_argument('zip_path')
    load.add_argument('--to', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            count, skipped = backup(ROOT, args.zip_path)
            print(str(count)+'ファイルを保存しました。runtime・隠しファイル・ZIP・リンクは対象外です。')
            if skipped:
                print('リンクのため保存しなかったもの：'+', '.join(skipped))
        else:
            print('復元しました：'+str(restore(args.zip_path, args.to)))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error)+'\n')
