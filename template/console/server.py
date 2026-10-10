#!/usr/bin/env python3
"""Portable, read-only workspace console. Standard library, no account access."""
import argparse
import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from boards import load_boards
from work_records import load_records

ASSETS = Path(__file__).resolve().parent


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.documents = {}

    def safe(self, path):
        candidate = Path(path)
        if candidate.is_absolute():
            raise ValueError('原本の場所は仕事場からの相対パスで指定してください。')
        if any(p.startswith('.') for p in candidate.parts) or 'runtime' in candidate.parts:
            raise ValueError('この場所は画面で読み取る対象外です。')
        resolved = (self.root / candidate).resolve()
        resolved.relative_to(self.root)
        if any(p.startswith('.') or p == 'runtime' for p in resolved.relative_to(self.root).parts):
            raise ValueError('この場所は画面で読み取る対象外です。')
        return resolved

    def register(self, path):
        path = Path(path)
        relative = str(path.resolve().relative_to(self.root)) if path.is_absolute() else str(path)
        real = self.safe(relative)
        if real.suffix != '.md' or not real.is_file():
            raise ValueError('Markdownの原本が見つかりません。')
        key = hashlib.sha256(relative.encode()).hexdigest()[:20]
        self.documents[key] = relative
        return key

    def document(self, key):
        if key not in self.documents:
            raise KeyError('原本が見つかりません。画面の記録を更新してください。')
        relative = self.documents[key]
        path = self.safe(relative)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('原本が大きいため、ファイルを直接開いてください。')
        body = path.read_text(encoding='utf-8')
        links = {}
        for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)', body):
            parsed = urlparse(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            # Resolve ../ in authored document links, then enforce the same root.
            target = (path.parent / unquote(parsed.path)).resolve()
            try:
                links[href] = self.register(target)
            except (OSError, ValueError):
                continue
        return {'body': body, 'source': relative, 'links': links}

    def snapshot(self):
        config = json.loads(self.safe('workspace/site.json').read_text(encoding='utf-8'))
        registry = self.safe('workspace/agents/registry.md')
        roles, warnings, seen = [], [], set()
        for line in registry.read_text(encoding='utf-8').splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not line.startswith('|') or not cells or not re.fullmatch(r'[a-z][a-z0-9-]*', cells[0]):
                continue
            if len(cells) != 6 or cells[0] in seen:
                warnings.append('名簿に形式の不備または担当IDの重複があります：'+cells[0])
                continue
            seen.add(cells[0])
            link = re.search(r'\]\(([^)]+)\)', cells[4])
            try:
                if not link:
                    raise ValueError()
                doc = self.register((registry.parent / link[1]).resolve())
            except (ValueError, OSError):
                doc = None
                warnings.append(cells[1]+'の役割原本を読み取れません。')
            roles.append(dict(zip(('id', 'name', 'type', 'purpose', 'ignored', 'state'), cells), document=doc))
        works, issues = load_records(self.root, self.safe('workspace/operations/jobs'), seen)
        for work in works:
            try:
                work['document'] = self.register(work['source'])
            except (OSError, ValueError):
                work['document'] = None
                warnings.append(work['title']+'の原本は表示対象外です。')
        warnings.extend(i['source']+'：'+i['message'] for i in issues)
        reports = []
        for kind in ('daily', 'monthly'):
            for path in sorted(self.safe('workspace/operations/reports/'+kind).glob('*.md'), reverse=True):
                if path.name == 'README.md':
                    continue
                try:
                    reports.append({'date': path.stem, 'kind': '日報' if kind == 'daily' else '月報',
                                    'document': self.register(path)})
                except (ValueError, OSError):
                    warnings.append(path.name+'を読み取れません。')
        boards = load_boards(self.root, {'circulars': 'workspace/operations/circulars/items',
                                       'mail': 'workspace/operations/mail/bulletins'}, self.register)
        warnings.extend(w['message'] for w in boards['warnings'])
        guides = []
        for ident, title, description, path in [
                ('start', '総えもんへの相談のしかた', 'やりたいことから始め、必要な仲間を一緒に作る。', 'START.md'),
                ('purpose', 'この仕事場の目的', '大切にしたいこと、本人の言葉とAIの理解。', 'workspace/purpose.md'),
                ('onboarding', '導入の設定と再開', '設定と導入作業の原本をたどり、続きから始める。', 'workspace/onboarding.md'),
                ('add', '担当を増やす・変える', '必要な仕事に合わせて追加・変更・休止・再開。', 'workspace/agents/workflows/add-desk.md'),
                ('github', 'GitHubで保存・再開', '自分の保管庫を作り、別のパソコンでも続ける。', 'workspace/recovery/github.md'),
                ('handoff', 'AIへ仕事を渡す', '目的と次の一手を、次の担当へつなぐ。', 'workspace/agents/workflows/handoff.md'),
                ('practice', '架空の一件を試す', '動機から担当、仕事、成果までたどる。', 'examples/walkthrough.md'),
                ('learning', '立て直しと学び', '自分で試す時間と、支援を任せる道。', 'workspace/agents/workflows/collaboration-recovery.md'),
                ('backup', 'ZIPで保存・戻す', '変更前に手元へ保存して、別の場所へ戻す。', 'workspace/recovery/README.md')]:
            guides.append({'id': ident, 'title': title, 'description': description,
                           'document': self.register(path)})
        return {'name': config['name'], 'mode': config['mode'], 'version': config['version'],
                'generated': datetime.now(timezone.utc).isoformat(), 'roles': roles, 'works': works,
                'reports': reports, 'boards': boards, 'guides': guides, 'warnings': warnings}


def handler(workspace):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, body, mime='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            port = self.server.server_address[1]
            if self.headers.get('Host') not in ('127.0.0.1:'+str(port), 'localhost:'+str(port)):
                return self.reply(403, b'{"error":"Host not allowed"}')
            parsed = urlparse(self.path)
            try:
                if parsed.path == '/api/snapshot':
                    data = workspace.snapshot()
                elif parsed.path == '/api/document':
                    data = workspace.document(parse_qs(parsed.query).get('id', [''])[0])
                elif parsed.path in ('/', '/index.html', '/app.js', '/styles.css'):
                    name = 'index.html' if parsed.path == '/' else parsed.path[1:]
                    file = ASSETS / name
                    return self.reply(200, file.read_bytes(), (mimetypes.guess_type(name)[0] or 'text/plain')+'; charset=utf-8')
                else:
                    return self.reply(404, b'{"error":"Not found"}')
                self.reply(200, json.dumps(data, ensure_ascii=False).encode())
            except KeyError:
                self.reply(404, json.dumps({'error': '原本が見つかりません。記録を更新してください。'}, ensure_ascii=False).encode())
            except (OSError, ValueError, UnicodeError):
                self.reply(422, json.dumps({'error': '原本を読み取れません。保存場所と記入内容をご確認ください。'}, ensure_ascii=False).encode())

        def do_POST(self):
            self.reply(405, b'{"error":"Read only"}')
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='仕事場の原本を読むローカル画面')
    parser.add_argument('--root', type=Path, default=ASSETS.parent)
    parser.add_argument('--port', type=int, default=8772)
    args = parser.parse_args()
    workspace = Workspace(args.root)
    workspace.snapshot()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(workspace))
    print('仕事の地図：http://127.0.0.1:'+str(server.server_address[1]), flush=True)
    print('終了はControl+C。原本は読み取りのみ。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
