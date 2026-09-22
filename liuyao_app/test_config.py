"""Writable configuration survives replacing/moving the application bundle."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import config

class ConfigurationChecks(unittest.TestCase):
    def test_home_separates_data_and_credentials_from_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)/'用户 资料'
            with patch.dict(os.environ, {'LIUYAO_HOME': str(home)}, clear=True):
                target=config.initialize_configuration()
                self.assertEqual(target, home/'.env')
                self.assertEqual(config.data_directory(),home/'data')
                self.assertTrue(target.is_file())
                target.write_text('DEEPSEEK_API_KEY=example-only\n', encoding='utf-8')
                config.initialize_configuration()
                self.assertEqual(target.read_text(), 'DEEPSEEK_API_KEY=example-only\n')
                config.load_env()
                self.assertEqual(os.environ['DEEPSEEK_API_KEY'],'example-only')

    def test_explicit_environment_wins_over_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            path.write_text('DEEPSEEK_MODEL=from-file\n',encoding='utf-8')
            with patch.dict(os.environ, {'DEEPSEEK_MODEL':'from-process'}, clear=True):
                config.load_env(path)
                self.assertEqual(os.environ['DEEPSEEK_MODEL'],'from-process')

    def test_existing_configuration_is_not_replaced_even_when_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env';path.touch()
            with patch.dict(os.environ, {'LIUYAO_HOME':directory},clear=True):
                config.initialize_configuration()
                self.assertEqual(path.read_bytes(),b'')

    def test_legacy_flash_preset_upgrades_once_with_exact_original_backup(self):
        original=(b'# Keep this comment\r\nDEEPSEEK_API_KEY=example-only\r\n'
                  b'DEEPSEEK_MODEL="deepseek-flash"\r\nDEEPSEEK_MODELS=deepseek-flash\r\n'
                  b'DEEPSEEK_THINKING=disabled\r\nDEEPSEEK_MAX_TOKENS=8192\r\n'
                  b'AI_TIMEOUT_SECONDS=90\r\nDOUBAO_MODEL=ep-custom\r\n')
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LIUYAO_HOME':directory},clear=True):
            p=Path(directory)/'.env';p.write_bytes(original)
            config.initialize_configuration();config.load_env(p)
            self.assertEqual(os.environ['DEEPSEEK_MODEL'],'deepseek-v4-pro')
            self.assertEqual(os.environ['DEEPSEEK_REASONING_EFFORT'],'max')
            self.assertEqual(os.environ['DEEPSEEK_THINKING'],'enabled')
            self.assertEqual(os.environ['DEEPSEEK_MAX_TOKENS'],'131072')
            self.assertEqual(os.environ['AI_TIMEOUT_SECONDS'],'600')
            self.assertEqual(os.environ['DEEPSEEK_API_KEY'],'example-only')
            self.assertEqual(os.environ['DOUBAO_MODEL'],'ep-custom')
            self.assertEqual((p.parent/'.env.before-deepseek-pro-max').read_bytes(),original)
            # Subsequent deliberate changes are not reset on the next startup.
            p.write_text(p.read_text().replace('DEEPSEEK_MODEL=deepseek-v4-pro','DEEPSEEK_MODEL=deepseek-flash'))
            before=p.read_bytes();config.initialize_configuration();self.assertEqual(p.read_bytes(),before)

    def test_custom_model_allowlist_and_ambiguous_files_are_not_rewritten(self):
        for text in ('DEEPSEEK_MODEL=ep-custom\nDEEPSEEK_MODELS=ep-custom\n',
                     'DEEPSEEK_MODEL=deepseek-flash\nDEEPSEEK_MODELS=deepseek-flash,ep-private\n',
                     'DEEPSEEK_MODEL=deepseek-flash\nDEEPSEEK_MODEL=another\n'):
            with tempfile.TemporaryDirectory() as directory:
                p=Path(directory)/'.env';p.write_text(text)
                self.assertFalse(config.upgrade_deepseek_defaults(p));self.assertEqual(p.read_text(),text)

    def test_new_install_has_pro_and_max_without_old_configuration_backup(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LIUYAO_HOME':directory},clear=True):
            config.initialize_configuration();config.load_env()
            self.assertEqual(os.environ['DEEPSEEK_MODEL'],'deepseek-v4-pro')
            self.assertEqual(os.environ['DEEPSEEK_REASONING_EFFORT'],'max')
            self.assertFalse((Path(directory)/'.env.before-deepseek-pro-max').exists())

    def test_previous_pro_model_without_quality_is_upgraded(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'.env'
            p.write_text('DEEPSEEK_MODEL=deepseek-v4-pro\nDEEPSEEK_THINKING=disabled\n')
            self.assertTrue(config.upgrade_deepseek_defaults(p))
            self.assertIn('DEEPSEEK_REASONING_EFFORT=max',p.read_text())
            self.assertIn('DEEPSEEK_THINKING=enabled',p.read_text())

if __name__=='__main__':unittest.main()
