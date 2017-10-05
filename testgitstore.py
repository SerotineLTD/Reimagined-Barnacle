#!/usr/bin/python
import unittest
import gitstore

class TestGitStore(unittest.TestCase):
	def test_author(self):
		gitstore.author('Bob Carmack','bob@example.org')
		self.assertTrue(True)

	def test_add_file(self):
		author = gitstore.author('Bob Carmack','bob@example.org')
		data = '{"id":42,"testString":"the quick brown fox"}'
		gitstore.add_file("/testfile.json",data,author,"testing")
		self.assertTrue(True)



if __name__ == '__main__':
    unittest.main()
