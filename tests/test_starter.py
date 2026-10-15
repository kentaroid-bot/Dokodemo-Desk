import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'template/console'))
from create_workspace import create
from server import Workspace

spec = importlib.util.spec_from_file_location('recovery', BASE / 'template/workspace/recovery/manage.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='desk-starter-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = create(self.base / '日本語の仕事場', '試験の制作室')
        self.app = Workspace(self.root)

    def test_portable_example_and_links(self):
        state = self.app.snapshot()
        self.assertEqual((len(state['roles']),len(state['works']),len(state['reports'])),(4,1,1))
        self.assertEqual(state['warnings'],[])
        work = state['works'][0]
        doc = self.app.document(work['document'])
        key = next(v for k,v in doc['links'].items() if 'quotation-draft' in k)
        self.assertIn('35,000円', self.app.document(key)['body'])
        moved = self.base / '移動後'
        self.root.rename(moved)
        self.assertEqual(Workspace(moved).snapshot()['name'], '試験の制作室')

    def test_blank_is_two_roles_without_demo_records(self):
        root = create(self.base / 'empty','新しい仕事場',True)
        state = Workspace(root).snapshot()
        self.assertEqual(state['mode'],'blank')
        self.assertEqual(len(state['roles']),2)
        self.assertEqual(state['works'],[])
        self.assertEqual(state['reports'],[])
        self.assertEqual(state['boards']['circulars'],[])
        self.assertEqual(state['warnings'],[])
        self.assertFalse((root/'projects/example-studio').exists())

    def test_existing_destination_and_edits_not_overwritten(self):
        source = self.root / 'START.md'
        source.write_text('私たちの編集')
        with self.assertRaises(FileExistsError):
            create(self.root, '変更されない')
        self.assertEqual(source.read_text(),'私たちの編集')

    def test_names_are_data_and_validated(self):
        root=create(self.base/'markup','<script>alert(1)</script>')
        self.assertEqual(Workspace(root).snapshot()['name'],'<script>alert(1)</script>')
        with self.assertRaises(ValueError):
            create(self.base/'bad','改行\nあり')

    def test_new_role_job_and_pause_reactivate(self):
        registry=self.root/'workspace/agents/registry.md'
        desk=self.root/'workspace/agents/desks/invoice.md'
        desk.write_text('# 請求支援\n練習用です。')
        registry.write_text(registry.read_text()+'\n| invoice | 請求支援 | 業務 | 下書きを作る | [原本](desks/invoice.md) | 使用中 |\n')
        original=self.root/'workspace/operations/jobs/example-quotation/TASK.md'
        path=self.root/'workspace/operations/jobs/example-invoice/TASK.md'
        path.parent.mkdir()
        path.write_text(original.read_text().replace('example-quotation','example-invoice').replace('担当: quotation','担当: invoice').replace('下書き済み・人間の確認待ち','引き継ぎ準備済み'))
        state=self.app.snapshot()
        self.assertEqual(len(state['roles']),5)
        self.assertEqual(len(state['works']),2)
        self.assertEqual(next(w for w in state['works'] if w['owner']=='invoice')['status'],'引き継ぎ準備済み')
        registry.write_text(registry.read_text().replace('| 使用中 |','| 休止中 |'))
        self.assertEqual(next(r for r in self.app.snapshot()['roles'] if r['id']=='invoice')['state'],'休止中')
        registry.write_text(registry.read_text().replace('| 休止中 |','| 使用中 |'))
        self.assertEqual(next(r for r in self.app.snapshot()['roles'] if r['id']=='invoice')['state'],'使用中')

    def test_record_updates_without_ui_configuration(self):
        path=self.root/'workspace/operations/jobs/example-quotation/TASK.md'
        path.write_text(path.read_text().replace('下書き済み・人間の確認待ち','確認済み・練習完了'))
        self.assertEqual(self.app.snapshot()['works'][0]['status'],'確認済み・練習完了')

    def test_outside_hidden_runtime_and_symlinks_rejected(self):
        outside=self.base/'private.md';outside.write_text('outside-only')
        hidden=self.root/'.private.md';hidden.write_text('hidden-only')
        runtime=self.root/'workspace/runtime/private.md';runtime.write_text('runtime-only')
        for path in (outside,hidden,runtime):
            with self.assertRaises(ValueError):self.app.register(path)
        link=self.root/'projects/link.md';link.symlink_to(runtime)
        with self.assertRaises(ValueError):self.app.register(link)
        doc=self.root/'projects/reference.md';doc.write_text('[外部](../../private.md)\n[内部](../workspace/runtime/private.md)')
        self.assertEqual(self.app.document(self.app.register(doc))['links'],{})

    def test_runtime_job_link_not_read(self):
        original=self.root/'workspace/operations/jobs/example-quotation/TASK.md'
        secret=self.root/'workspace/runtime/secret.md'
        secret.write_text(original.read_text().replace('example-quotation','hidden-job'))
        folder=self.root/'workspace/operations/jobs/hidden-job';folder.mkdir()
        (folder/'TASK.md').symlink_to(secret)
        state=self.app.snapshot()
        self.assertEqual(len(state['works']),1)
        self.assertTrue(state['warnings'])

    def test_backup_restore_and_no_overwrite(self):
        (self.root/'workspace/runtime/private.md').write_text('not-for-backup')
        (self.root/'.env').write_text('NOT_A_SECRET=test')
        archive=self.base/'backup.zip'
        count,skipped=recovery.backup(self.root,archive)
        self.assertGreater(count,20)
        with zipfile.ZipFile(archive) as z:
            self.assertNotIn('workspace/runtime/private.md',z.namelist())
            self.assertNotIn('.env',z.namelist())
        with self.assertRaises(FileExistsError):recovery.backup(self.root,archive)
        destination=self.base/'restored'
        recovery.restore(archive,destination)
        self.assertEqual(Workspace(destination).snapshot()['works'],Workspace(self.root).snapshot()['works'])
        with self.assertRaises(FileExistsError):recovery.restore(archive,destination)
        with self.assertRaises(ValueError):recovery.backup(self.root,self.root/'bad.zip')

    def test_restore_rejects_escape_before_creating_folder(self):
        archive=self.base/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('START.md','starter')
            z.writestr('workspace/site.json','{}')
            z.writestr('../outside.md','escape')
        dest=self.base/'rejected'
        with self.assertRaises(ValueError):recovery.restore(archive,dest)
        self.assertFalse(dest.exists())
        self.assertFalse((self.base/'outside.md').exists())

    def test_all_authored_markdown_links_resolve(self):
        blank=create(self.base/'blank-links','リンク確認',True)
        for root in (self.root,blank):
            for path in root.rglob('*.md'):
                for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)',path.read_text()):
                    if '://' in href or href.startswith('#'):continue
                    self.assertTrue((path.parent/href.split('#')[0]).exists(),(path,href))

    def test_purpose_guides_are_available_in_both_modes(self):
        blank=create(self.base/'blank-guides','はじめての仕事場',True)
        for root in (self.root,blank):
            app=Workspace(root)
            state=app.snapshot()
            self.assertEqual(state['version'],'0.2')
            guides={g['id']:g for g in state['guides']}
            self.assertEqual(len(guides),9)
            for key in ('start','purpose','onboarding','github'):
                self.assertIn('body',app.document(guides[key]['document']))
            self.assertEqual(next(r for r in state['roles'] if r['id']=='general-affairs')['name'],'総えもん')
        self.assertNotIn('事務の負担を減らして', (blank/'workspace/purpose.md').read_text())
        self.assertFalse((blank/'workspace/agents/roles/purpose-partner.md').exists())
        self.assertTrue((blank/'workspace/agents/templates/purpose-partner.md').exists())

    @unittest.skipUnless(shutil.which('git'),'Git is needed for the local transport test')
    def test_personalized_onboarding_survives_git_clone(self):
        root=create(self.base/'personal','試験用の仕事場',True)
        # Simulate the documented onboarding output, not an app conversation.
        purpose=root/'workspace/purpose.md'
        purpose.write_text('# この仕事場の目的\n本人の希望：制作に使う時間を増やしたい。\n')
        role=root/'workspace/agents/roles/purpose-partner.md'
        role.write_text('# 試験の伴走役\n[目的](../../purpose.md)に沿って仕事を提案します。\n')
        registry=root/'workspace/agents/registry.md'
        registry.write_text(registry.read_text()+'| purpose-partner | 試験の伴走役 | 共通 | 制作の時間を戻す | [役割](roles/purpose-partner.md) | 依頼時 |\n')
        progress=root/'workspace/onboarding.md'
        task=root/'workspace/operations/jobs/setup/TASK.md'
        task.parent.mkdir()
        task.write_text('# 仕事場を準備する\n\n<!-- monku-work:v1 -->\n'
                        '## 仕事の現在地\n- 作業ID: setup\n- 件名: 仕事場を準備する\n'
                        '- 担当: general-affairs\n- ステータス: UI確認待ち\n'
                        '- 更新日時: 2026-10-10T10:00:00+09:00\n- 目的: 制作の仕事場を整える\n'
                        '- 次の一手: 担当と原本を画面で確認する\n- 今回の到達点: 初回画面まで\n'
                        '- 報告先: 導入相談\n- 成果: 目的と伴走役を作成\n<!-- /monku-work -->\n')
        progress.write_text('# 導入の設定と再開\n保存方式：ローカルGitの試験\n'
                            '[導入作業の原本](operations/jobs/setup/TASK.md)\n')
        (root/'workspace/runtime/connection.txt').write_text('fixture-local-only')
        (root/'.env').write_text('FIXTURE_TOKEN=not-a-real-token')
        def git(*args,cwd=root):
            return subprocess.run(['git',*map(str,args)],cwd=cwd,check=True,capture_output=True,text=True)
        git('init','--initial-branch=main')
        git('add','.')
        git('-c','user.name=Starter Test','-c','user.email=starter@example.invalid','commit','-m','Portable fixture')
        remote=self.base/'local-remote.git'
        git('clone','--bare',root,remote)
        git('remote','add','origin',remote)
        task.write_text(task.read_text().replace('UI確認待ち','引き継ぎ準備済み')
                        .replace('10:00:00','10:05:00')
                        .replace('担当と原本を画面で確認する','次の会話で原本を読み続ける'))
        git('add','workspace/operations/jobs/setup/TASK.md')
        git('-c','user.name=Starter Test','-c','user.email=starter@example.invalid','commit','-m','Handoff note')
        git('push','origin','main')
        resumed=self.base/'resumed'
        git('clone',remote,resumed)
        for path in ('workspace/purpose.md','workspace/onboarding.md','workspace/agents/registry.md',
                     'workspace/agents/roles/purpose-partner.md','workspace/operations/jobs/setup/TASK.md'):
            self.assertEqual((root/path).read_bytes(),(resumed/path).read_bytes())
        self.assertFalse((resumed/'.env').exists())
        self.assertFalse((resumed/'workspace/runtime/connection.txt').exists())
        app=Workspace(resumed)
        state=app.snapshot()
        self.assertEqual(len(state['roles']),3)
        self.assertEqual(len([r for r in state['roles'] if r['id']=='purpose-partner']),1)
        self.assertEqual(state['warnings'],[])
        self.assertEqual(len(state['works']),1)
        work=state['works'][0]
        self.assertEqual((work['owner'],work['status']),('general-affairs','引き継ぎ準備済み'))
        guide=next(g for g in state['guides'] if g['id']=='onboarding')
        link=app.document(guide['document'])['links']['operations/jobs/setup/TASK.md']
        self.assertEqual(app.document(link)['source'],work['source'])
        self.assertEqual(git('rev-parse','HEAD').stdout,git('rev-parse','HEAD',cwd=resumed).stdout)

    def test_no_live_identifiers_or_personal_paths(self):
        for path in self.root.rglob('*'):
            if not path.is_file():continue
            text=path.read_text()
            self.assertNotRegex(text,r'/Users/|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
            # Public distribution link, not a workspace account or private identifier.
            if path.relative_to(self.root).as_posix() in {
                'README.md', 'START.md',
                'workspace/agents/workflows/mesh-collaboration.md',
            }:
                text = text.replace('](https://github.com/kentaroid-bot/dokodemo-mesh)', ']([public-mesh-template])')
            self.assertNotIn('kentaroid',text)


if __name__=='__main__':unittest.main()
