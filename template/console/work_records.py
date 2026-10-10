"""Read explicitly opted-in Japanese work records; never infer a job's state."""
import re
from collections import Counter
from datetime import datetime

START = '<!-- monku-work:v1 -->'
END = '<!-- /monku-work -->'
REQUIRED = ('作業ID', '件名', '担当', 'ステータス', '更新日時', '目的', '次の一手', '今回の到達点', '報告先')


def parse_record(text):
    if START not in text:
        return None
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError('仕事の現在地の開始・終了を一組だけ記してください。')
    match = re.search(r'^' + re.escape(START) + r'\s*\n(.*?)^' + re.escape(END) + r'\s*$', text, re.M | re.S)
    if not match:
        raise ValueError('仕事の現在地の開始・終了の位置を確認してください。')
    fields = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        entry = re.fullmatch(r'- ([^:：]+)[:：]\s*(.*)', line)
        if not entry:
            raise ValueError('仕事の現在地は「- 項目: 内容」の一行ずつで記してください。')
        key, value = entry[1].strip(), entry[2].strip()
        if key in fields:
            raise ValueError(f'「{key}」が重複しています。')
        fields[key] = value
    missing = [key for key in REQUIRED if not fields.get(key)]
    if missing:
        raise ValueError('未記入の項目：' + '、'.join(missing))
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', fields['作業ID']):
        raise ValueError('作業IDは英小文字・数字・ハイフンで記してください。')
    try:
        updated = datetime.fromisoformat(fields['更新日時'].replace('Z', '+00:00'))
        if updated.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError('更新日時は時差を含む日時で記してください（例：2026-10-07T13:00:00+09:00）。') from None
    roles = list(dict.fromkeys([fields['担当']] + re.split(r'\s*[,、]\s*', fields.get('関係する担当', ''))))
    return {'id': fields['作業ID'], 'title': fields['件名'], 'owner': fields['担当'],
            'roles': [role for role in roles if role], 'status': fields['ステータス'],
            'recordedAt': updated.isoformat(), 'date': updated.date().isoformat(),
            'summary': fields['目的'], 'next': fields['次の一手'], 'flow': [],
            'doneWhen': fields['今回の到達点'], 'reportTo': fields['報告先'],
            'result': fields.get('成果', ''), 'sourceKind': 'record'}


def load_records(root, folder, known_roles):
    records, warnings = [], []
    if not folder.is_dir():
        return [], [{'source': str(folder.relative_to(root)), 'message': '作業記録のフォルダが見つかりません。'}]
    paths = sorted(set(folder.glob('*/README.md')) | set(folder.glob('*/TASK.md')))
    for path in paths:
        source = str(path.relative_to(root))
        try:
            resolved = path.resolve()
            parts = resolved.relative_to(root).parts
            if any(part.startswith('.') or part == 'runtime' for part in parts):
                raise ValueError('この場所は読み取り対象外です。')
            text = resolved.read_text(encoding='utf-8')
            record = parse_record(text)
            if record is None:
                continue
            unknown = [role for role in record['roles'] if role not in known_roles]
            if unknown:
                raise ValueError('名簿にない担当ID：' + '、'.join(unknown))
            records.append({**record, 'source': source})
        except (OSError, UnicodeError, ValueError) as error:
            message = str(error) if isinstance(error, ValueError) and not isinstance(error, UnicodeError) and 'is not in the subpath' not in str(error) else '原本を読み取れません。保存先を確認してください。'
            warnings.append({'source': source, 'message': message})
    counts = Counter(record['id'] for record in records)
    valid = []
    for record in records:
        if counts[record['id']] > 1:
            warnings.append({'source': record['source'], 'message': '作業IDが重複しています。一件につき原本を一つにしてください。'})
        else:
            valid.append(record)
    valid.sort(key=lambda record: datetime.fromisoformat(record['recordedAt']), reverse=True)
    return valid, warnings
