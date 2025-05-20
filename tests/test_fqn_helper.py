import unittest
from fqn_helper import FQNHelper

class TestFQNHelper(unittest.TestCase):
    def test_map_with_namespace(self):
        fqn = FQNHelper.map('module.sub.Class')
        self.assertEqual(fqn.namespace, 'module.sub')
        self.assertEqual(fqn.name, 'Class')

    def test_map_without_namespace(self):
        fqn = FQNHelper.map('Class')
        self.assertEqual(fqn.namespace, '')
        self.assertEqual(fqn.name, 'Class')

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            FQNHelper.map('')

if __name__ == '__main__':
    unittest.main()
