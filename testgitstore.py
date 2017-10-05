#!/usr/bin/python
import unittest
from gitstore import GitStore

class TestGitStore(unittest.TestCase):

	def setUp(self):
		self.gitstore = GitStore()

	def tearDown(self):
		self.gitstore.undefine()

	def test_author(self):
		self.gitstore.author('Bob Carmack','bob@example.org')
		self.assertTrue(True)

	def test_add_file(self):
		author = self.gitstore.author('Bob Carmack','bob@example.org')
		data = '{"id":42,"testString":"the quick brown fox"}'
		self.gitstore.add_file("/testfile.json",data,author,"testing")
		self.assertTrue(True)

	def test_add_directory(self):
		author = self.gitstore.author('Bob Carmack','bob@example.org')
		data = '{"id":42,"testString":"the quick brown fox"}'
		self.gitstore.add_file("/foobar/directory/testfile.json",data,author,"testing")
		self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
