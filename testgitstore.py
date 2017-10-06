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

	def test_list_files(self):
		author = self.gitstore.author('Bob Carmack','bob@example.org')
		data = '{"id":42,"testString":"the quick brown fox"}'
		self.gitstore.add_file("/testfile.json",data,author,"testing")
		self.gitstore.add_file("/testfiletwo.json",data,author,"testing")
		self.gitstore.add_file("/subdirectory/testfilethree.json",data,author,"testing")
		files = self.gitstore.list_files("/")
		self.assertTrue(len(files) == 3)
		self.assertEqual("testfile.json",files[1])
		self.assertEqual("testfiletwo.json",files[2])
		self.assertEqual("subdirectory",files[0])

	def test_get_file(self):
		author = self.gitstore.author('Bob Carmack','bob@example.org')
		data = '{"id":45,"testString":"the quick brown fox"}'
		self.gitstore.add_file("/testget.json",data,author,"testing")
		returnData = self.gitstore.get_file("/testget.json")
		self.assertEqual(data,returnData)

if __name__ == '__main__':
    unittest.main()
