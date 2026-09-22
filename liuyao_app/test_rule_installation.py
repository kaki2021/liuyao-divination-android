import os
import tempfile
import unittest
from pathlib import Path

from .rulebook import (
    ROOT,
    RuleBook,
    RulesNotInstalled,
    compile_rules,
    export_workbook,
    load_rules,
    read_workbook,
    save_rules,
    schema,
)
from .server import Application


def public_placeholder_rows():
    rows = []
    for key, spec in schema()['rules'].items():
        if spec['type'] == 'branch':
            value = '子'
        elif key == 'BASE_SCORE':
            value = 5
        elif key == 'LEVEL_WEAK':
            value = 3
        elif key == 'LEVEL_STRONG':
            value = 7
        elif spec.get('min') == spec.get('max'):
            value = spec['min']
        elif spec.get('min', 0) <= 0 <= spec.get('max', 0):
            value = 0
        else:
            value = spec.get('min', 0)
        rows.append({
            'id': key,
            'value': value,
            'enabled': bool(spec.get('required')),
            'source': '',
            'explanation': '公开测试占位值，不是正式规则。',
            'notes': '',
        })
    return rows


class RuleInstallationTests(unittest.TestCase):
    def test_public_tree_has_no_active_rulebook(self):
        if os.environ.get('LIUYAO_TEST_WITH_PRIVATE_RULES') == '1':
            self.skipTest('private maintainer rulebook temporarily installed')
        self.assertFalse((ROOT / 'compiled_rules.json').exists())
        self.assertFalse((ROOT / 'rules.xlsx').exists())
        with self.assertRaises(RulesNotInstalled):
            load_rules()

    def test_application_can_start_before_rule_installation(self):
        if os.environ.get('LIUYAO_TEST_WITH_PRIVATE_RULES') == '1':
            self.skipTest('private maintainer rulebook temporarily installed')
        with tempfile.TemporaryDirectory() as directory:
            app = Application(directory)
            try:
                with self.assertRaises(RulesNotInstalled):
                    load_rules(app.rules_directory)
            finally:
                app.close()

    def test_exported_placeholder_can_be_installed_to_private_data(self):
        placeholder = RuleBook(compile_rules(public_placeholder_rows()))
        raw = export_workbook(placeholder)
        with tempfile.TemporaryDirectory() as directory:
            installed = save_rules(Path(directory), read_workbook(raw))
            self.assertEqual(installed.compiled, placeholder.compiled)
            self.assertEqual(load_rules(directory).version, placeholder.version)

    def test_blank_public_template_is_not_an_installable_rulebook(self):
        with self.assertRaises(ValueError):
            read_workbook((ROOT / 'rules_template.xlsx').read_bytes())


if __name__ == '__main__':
    unittest.main()
