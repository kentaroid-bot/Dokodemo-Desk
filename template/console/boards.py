"""Read the existing shared boards without marking anything read or answered."""
import re
from datetime import datetime, timezone, timedelta


def header_field(text, name):
    header = text.split('\n## ', 1)[0]
    found = re.search(r'^- ' + re.escape(name) + r'[:：]\s*(.+)$', header, re.M)
    return found[1].strip() if found else ''


def table_in_section(text, heading, columns):
    section = re.search(r'^## ' + re.escape(heading) + r'\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not section:
        return None
    rows, seen = [], set()
    for line in section[1].splitlines():
        if not line.startswith('|'):
            continue
        cells = [cell.strip().strip('`') for cell in line.strip('|').split('|')]
        if len(cells) != columns or not re.fullmatch(r'[a-z][a-z0-9-]*', cells[0]):
            continue
        if cells[0] in seen:
            return None
        seen.add(cells[0])
        rows.append(cells)
    return rows or None


def parse_board(text, kind):
    title = re.search(r'^# (.+)$', text, re.M)
    item = {'title': title[1].strip() if title else '題名未記入',
            'created': header_field(text, '作成日時') or header_field(text, '作成日')}
    if kind == 'circulars':
        front = re.match(r'\A---\s*\n(.*?)\n---(?:\n|$)', text, re.S)
        values = re.findall(r'^status:\s*(\S+)\s*$', front[1], re.M) if front else []
        status = values[0] if len(values) == 1 and values[0] in ('open', 'closed') else 'unknown'
        rows = table_in_section(text, '対象と回答状況', 3)
        item.update(status=status, author=header_field(text, '発議者') or header_field(text, '発議者・管理'),
                    deadline=header_field(text, '返答期限'),
                    responses=None if rows is None else [{'role': row[0], 'state': row[1], 'at': row[2]} for row in rows])
    else:
        rows = table_in_section(text, '既読', 2)
        item.update(author=header_field(text, '作成担当'),
                    receipts=None if rows is None else [{'role': row[0], 'at': row[1]} for row in rows])
    return item


def load_boards(root, config, register_doc):
    result = {'circulars': [], 'mail': [], 'warnings': []}
    for kind in ('circulars', 'mail'):
        relative = config.get(kind)
        if not relative:
            result['warnings'].append({'kind': kind, 'message': '共有板の保存先が未設定です。'})
            continue
        try:
            folder = (root / relative).resolve()
            folder.relative_to(root)
            if not folder.is_dir():
                raise OSError()
        except (OSError, ValueError):
            result['warnings'].append({'kind': kind, 'message': '共有板のフォルダを読み取れません。'})
            continue
        for path in sorted(folder.glob('*.md'), reverse=True):
            if path.name.lower() == 'readme.md':
                continue
            try:
                resolved = path.resolve()
                parts = resolved.relative_to(root).parts
                if any(part.startswith('.') or part == 'runtime' for part in parts):
                    raise ValueError('この場所は読み取り対象外です。')
                item = parse_board(resolved.read_text(encoding='utf-8'), kind)
                item.update(document=register_doc(resolved), source=str(path.relative_to(root)),
                            updated=datetime.fromtimestamp(resolved.stat().st_mtime, timezone(timedelta(hours=9))).isoformat(timespec='seconds'))
                result[kind].append(item)
            except (OSError, UnicodeError, ValueError):
                result['warnings'].append({'kind': kind, 'message': path.name + ' を読み取れません。'})
    return result
