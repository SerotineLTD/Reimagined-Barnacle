#!/usr/bin/python

import pygit2
import os
import sys
import SocketServer
import shutil
import json
from collections import deque
from flask import Flask

PATH_TO_REPO = "/tmp/gitstore.git"
PATH_SEPERATOR = "/"

app = Flask(__name__)

class GitStore:
	def __init__(self,path=PATH_TO_REPO):
		self.repoPath = path
		if(not os.path.isdir(path)):
			pygit2.init_repository(path,True)
		self.repo = pygit2.Repository(path)

	def author(self,name,email):
		return pygit2.Signature(name,email)

	def undefine(self):
		if self.repoPath != None and os.path.isdir(self.repoPath) and self.repoPath != "/" and os.path.isfile(self.repoPath+"/HEAD"):
			shutil.rmtree(self.repoPath)

	def find_last_commit(self):
		master = self.repo.lookup_reference("refs/heads/master")
		last_commit = master.get_object()
		return last_commit

	def list_files_objs(self,path):
		try:
			last_commit = self.find_last_commit()
			files = []
			for entry in last_commit.tree:
				files.append(entry)
			return files
		except KeyError:
			return []

	def list_files(self,path):
		files = self.list_files_objs(path)
		fileNames = []
		for entry in files:
			fileNames.append(entry.name)
		return fileNames

	def new_commit(self,treeId,author,reason):
		try:
			last_commit = self.find_last_commit()
			self.repo.create_commit('refs/heads/master',author,author,reason,treeId,[last_commit.id])
		except KeyError:
			self.repo.create_commit('refs/heads/master',author,author,reason,treeId,[])

	def add_file(self,path,data,author,reason,treeBuilder=None):
		pathParts = deque(path.split(PATH_SEPERATOR))
		name = pathParts.popleft()
		if len(pathParts) < 1:
			if treeBuilder.get(name)!=None:
				raise ValueError(name+" already exists")
			id = self.repo.create_blob(data)
			treeBuilder.insert(name,id,pygit2.GIT_FILEMODE_BLOB)
			return treeBuilder
		else:
			sub_dir_path = PATH_SEPERATOR.join(pathParts)
			if name == "":
				# We add to root
				try:
					last_commit = self.find_last_commit()
					treeBuilder = self.repo.TreeBuilder(last_commit.tree)
				except KeyError:
					treeBuilder = self.repo.TreeBuilder()
				treeBuilder = self.add_file(sub_dir_path,data,author,reason,treeBuilder)
				treeId = treeBuilder.write()
				self.new_commit(treeId,author,reason)
			else:
				# we add to a named dir
				nextTree = self.repo.TreeBuilder()
				nextTree = self.add_file(sub_dir_path,data,author,reason,nextTree)
				treeId = nextTree.write()
				treeBuilder.insert(name,treeId,pygit2.GIT_FILEMODE_TREE)
				return treeBuilder

	def get_file(self,path):
		pathParts = path.split(PATH_SEPERATOR)
		filename = pathParts.pop()
		dirPath = PATH_SEPERATOR.join(pathParts)
		files = gitstore.list_files_objs(dirPath)
		targetFile = None
		for fileObj in files:
			if fileObj.name == filename:
				return gitstore.repo.read(fileObj.id)[1]
		
		

#HTTP handling stuff

gitstore = GitStore(PATH_TO_REPO)
@app.route("/")
def getPath():
	path = "/"
	pathParts = path.split("/")
	if pathParts[-1] == "":
		return to_json(gitstore.list_files("/"))
#	else
#		return gitstore.get_file(path)


def to_json(data):
	return json.dumps(data, sort_keys=True, indent=2)
