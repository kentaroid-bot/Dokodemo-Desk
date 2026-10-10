#!/usr/bin/env python3
"""Create a standalone workspace without replacing any existing destination."""
import argparse
import json
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / 'template'
DEMO_FILES = (
    'workspace/agents/roles/purpose-partner.md',
    'workspace/agents/desks/quotation.md',
    'workspace/operations/jobs/example-quotation/TASK.md',
    'workspace/operations/reports/daily/2026-10-07.md',
    'workspace/operations/circulars/items/example-start.md',
    'projects/example-studio/README.md',
    'projects/example-studio/quotation-draft.md',
)


def create(destination, name='小さな制作室', blank=False):
    if not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError('名前は改行を含まない1〜80文字にしてください。')
    dest = Path(destination).expanduser().absolute()
    if dest.exists() or dest.is_symlink():
        raise FileExistsError('保存先が既にあります。新しいフォルダ名を指定してください。')
    for path in TEMPLATE.rglob('*'):
        if path.is_symlink():
            raise ValueError('雛形にリンクが含まれています。展開を中止しました。')
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
    site = dest / 'workspace/site.json'
    config = json.loads(site.read_text(encoding='utf-8'))
    config.update(name=name.strip(), mode='blank' if blank else 'example')
    site.write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if blank:
        for relative in DEMO_FILES:
            (dest / relative).unlink()
        registry = dest / 'workspace/agents/registry.md'
        registry.write_text('\n'.join(line for line in registry.read_text(encoding='utf-8').splitlines()
                                      if not line.startswith(('| quotation |', '| purpose-partner |')))+'\n', encoding='utf-8')
        shutil.copyfile(dest / 'workspace/agents/templates/purpose.md', dest / 'workspace/purpose.md')
        (dest / 'workspace/catalog.json').write_text('{"projects": []}\n', encoding='utf-8')
        for relative in ('workspace/operations/jobs/example-quotation', 'projects/example-studio'):
            (dest / relative).rmdir()
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='新しいフォルダにAI協働の仕事場を作ります。')
    parser.add_argument('destination', help='まだ存在しない保存先')
    parser.add_argument('--name', default='小さな制作室', help='画面に表示する事業所名')
    parser.add_argument('--blank', action='store_true', help='練習用の担当・仕事・日報・回覧を入れない')
    args = parser.parse_args()
    try:
        created = create(args.destination, args.name, args.blank)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error)+'\n')
    print('作成しました：'+str(created))
    print('START.mdを開くか、次のファイルをPythonで実行してください：')
    print(str(created / 'console/server.py'))
