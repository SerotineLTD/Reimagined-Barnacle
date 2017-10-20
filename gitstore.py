#!/usr/bin/python

import pygit2
import os
import sys
import SocketServer
import shutil
import json
import re
from collections import deque
from flask import Flask
from flask import request
from werkzeug.routing import BaseConverter

PATH_TO_REPO = "/srv/gitstore/gitstore.git"
PATH_SEPERATOR = "/"
COMMITTER_REGEX = re.compile("(.*?) ?<(.*)>")

app = Flask(__name__)

class RegexConverter(BaseConverter):
	def __init__(self,url_map, *items):
		super(RegexConverter, self).__init__(url_map)
		self.regex = items[0]

app.url_map.converters['regex'] = RegexConverter

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

	def list_files_objs(self,path,tree=None):
#		print "list_files_objs("+path+")"
		if path == "/" or path == "":
			if tree==None:
				last_commit = self.find_last_commit()
				tree = last_commit.tree
			files = []
			for entry in tree:
#				print "Appending "+entry.name
				files.append(entry)
			return files
		else:
			pathParts = deque(path.split(PATH_SEPERATOR))
			if pathParts[0] == "":
				last_commit = self.find_last_commit()
				tree = last_commit.tree
				pathParts.popleft()
			name = pathParts.popleft()
			for entry in tree:
#				print "tree entry: "+entry.name
				if entry.name == name:
					subPath = PATH_SEPERATOR.join(pathParts)
					subTree = gitstore.repo.get(entry.id).peel(pygit2.Tree)
					return gitstore.list_files_objs(subPath,subTree)

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
				nextTree = None
				if treeBuilder.get(name) == None:
					nextTree = self.repo.TreeBuilder()
				else:
					nextTree = self.repo.TreeBuilder(gitstore.repo.get(treeBuilder.get(name).id))
				nextTree = self.add_file(sub_dir_path,data,author,reason,nextTree)
				treeId = nextTree.write()
				treeBuilder.insert(name,treeId,pygit2.GIT_FILEMODE_TREE)
				return treeBuilder

	def delete_file(self,path, author,reason,treeBuilder=None):
		#print "delete_file("+path+")"
		pathParts = deque(path.split(PATH_SEPERATOR))
		if treeBuilder==None:
			#We're at the start
			if path == "/" or path == "" or path == None:
				raise ValueError("Invalid path")
			else:
				try:
					last_commit = self.find_last_commit()
					treeBuilder = self.repo.TreeBuilder(last_commit.tree)
				except KeyError:
					treeBuilder = self.repo.TreeBuilder()
				if pathParts[0]=="":
					pathParts.popleft()
				subPath = PATH_SEPERATOR.join(pathParts)
				self.delete_file(subPath,author,reason,treeBuilder)
				treeId = treeBuilder.write()
				self.new_commit(treeId,author,reason)
		else:
			#We're mid recurse.
			if len(pathParts) == 0 :
				raise ValueError("Invalid path")
			if len(pathParts) == 1 or (len(pathParts)==2 and pathParts[1] == ""):
				treeBuilder.remove(pathParts[0])
			else:
				if pathParts[0]=="":
					pathParts.popleft()
				name = pathParts.popleft()
				nextFolder = treeBuilder.get(name)
				nextTreeBuilder = self.repo.TreeBuilder(gitstore.repo.get(nextFolder.id))
				subPath = PATH_SEPERATOR.join(pathParts)
				self.delete_file(subPath,author,reason,nextTreeBuilder)
				tree = nextTreeBuilder.write()
				treeBuilder.insert(name,tree,pygit2.GIT_FILEMODE_TREE)

	def patch_file(self,path, changeSet ,author,reason,treeBuilder=None):
		#print "patch_file("+path+")"
		pathParts = deque(path.split(PATH_SEPERATOR))
		if treeBuilder==None:
			#We're at the start
			if path == "/" or path == "" or path == None:
				raise ValueError("Invalid path")
			else:
				try:
					last_commit = self.find_last_commit()
					treeBuilder = self.repo.TreeBuilder(last_commit.tree)
				except KeyError:
					treeBuilder = self.repo.TreeBuilder()
				if pathParts[0]=="":
					pathParts.popleft()
				subPath = PATH_SEPERATOR.join(pathParts)
				self.patch_file(subPath,changeSet,author,reason,treeBuilder)
				treeId = treeBuilder.write()
				self.new_commit(treeId,author,reason)
		else:
			#We're mid recurse.
			if len(pathParts) == 0 :
				raise ValueError("Invalid path")
			if len(pathParts) == 1 or (len(pathParts)==2 and pathParts[1] == ""):
				#print "Let's search the treebuilder for "+pathParts[0]
				originalData = gitstore.repo.read(treeBuilder.get(pathParts[0]).id)[1]
				#print "Original JSON:\n"+originalData+"\n\nPatch JSON:\n"+changeSet
				doc = json.loads(originalData)
				changes = json.loads(changeSet)
				for key in changes.keys():
					doc[key]=changes[key]
				newJson = json.dumps(doc)
				# print "Resulting JSON:\n"+newJson
				id = self.repo.create_blob(newJson)
				treeBuilder.insert(pathParts[0],id,pygit2.GIT_FILEMODE_BLOB)
				
			else:
				if pathParts[0]=="":
					pathParts.popleft()
				name = pathParts.popleft()
				nextFolder = treeBuilder.get(name)
				nextTreeBuilder = self.repo.TreeBuilder(gitstore.repo.get(nextFolder.id))
				subPath = PATH_SEPERATOR.join(pathParts)
				self.patch_file(subPath,changeSet,author,reason,nextTreeBuilder)
				tree = nextTreeBuilder.write()
				treeBuilder.insert(name,tree,pygit2.GIT_FILEMODE_TREE)

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
@app.route('/v1.0/<regex(".*"):path>', methods=['GET'])
def getPath(path):
	path = "/"+path
	pathParts = path.split("/")
	if pathParts[-1] == "":
		return to_json(gitstore.list_files(path))
	else:
		try:
			return gitstore.get_file(path)
		except KeyError:
			return ("Not found\n", 404,None)

@app.route('/v1.0/<regex(".*"):path>', methods=['POST'])
def postPath(path):
	path = "/"+path
	data = json.dumps(request.get_json())
	committer = parse_committer(request.headers['Committer'])
	commitMessage = request.headers['Commit-Message']
	gitstore.add_file(path,data,committer,commitMessage)
	return data

@app.route('/v1.0/<regex(".*"):path>', methods=['DELETE'])
def delPath(path):
	path = "/"+path
	committer = parse_committer(request.headers['Committer'])
	commitMessage = request.headers['Commit-Message']
	gitstore.delete_file(path,committer,commitMessage)
	return ("Deleted\n", 200, None)

@app.route('/v1.0/<regex(".*"):path>', methods=['PATCH'])
def patchPath(path):
	path = "/"+path
	data = json.dumps(request.get_json())
	committer = parse_committer(request.headers['Committer'])
	commitMessage = request.headers['Commit-Message']
	gitstore.patch_file(path,data,committer,commitMessage)
	return gitstore.get_file(path)

def parse_committer(committerStr):
	if committerStr == None or committerStr == "":
		raise ValueError("No committer specified (did you set the Committer header)")
	match = COMMITTER_REGEX.match(committerStr)
	if match:
		return gitstore.author(match.group(1),match.group(2))
	else:
		return gitstore.author(committerStr,"none@example.org")

def to_json(data):
	return json.dumps(data, sort_keys=True, indent=2)

if __name__ == '__main__':
	app.run(debug=True, host='0.0.0.0', port=5000)
