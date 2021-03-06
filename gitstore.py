#!/usr/bin/python

import pygit2
import os
import sys
import SocketServer
import shutil
import json
import re
import subprocess
from multiprocessing import Process
from collections import deque
from flask import Flask
from flask import request
from werkzeug.routing import BaseConverter

PATH_TO_REPO = "/srv/gitstore/gitstore.git"
STATUS_PATH = "/tmp/gscs/status"
PATH_SEPERATOR = "/"
COMMITTER_REGEX = re.compile("(.*?) ?<(.*)>")

running_post_commit_process = None

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
		last_commit = master.peel()
		return last_commit

	def list_files_objs(self,path,tree=None):
#		print "list_files_objs("+path+")"
		if path == "/" or path == "":
			files = []
			try:
				if tree==None:
					last_commit = self.find_last_commit()
					tree = last_commit.tree
				for entry in tree:
	#				print "Appending "+entry.name
					files.append(entry)
			except KeyError:
				print "No previous commit\n"
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
		if files == None:
			raise KeyError("Directory does not exist")
		for entry in files:
			fileNames.append(entry.name)
		return fileNames

	def run_post_commit(self,directory):
		commitHookFile = directory+"/hooks/post-commit"
		os.chdir(directory)
		subprocess.call([commitHookFile])

	def new_commit(self,treeId,author,reason):
		global running_post_commit_process
		try:
			last_commit = self.find_last_commit()
			self.repo.create_commit('refs/heads/master',author,author,reason,treeId,[last_commit.id])
		except KeyError:
			self.repo.create_commit('refs/heads/master',author,author,reason,treeId,[])
		commitHookFile = PATH_TO_REPO+"/hooks/post-commit"
		if(os.path.exists(commitHookFile)):
			start_post_commit_process = False
			if(running_post_commit_process == None):
				start_post_commit_process = True
			if(running_post_commit_process != None and not running_post_commit_process.is_alive()):
				start_post_commit_process = True

			if(start_post_commit_process):
				running_post_commit_process = Process(target=self.run_post_commit,args=[PATH_TO_REPO])
				running_post_commit_process.start()

	def add_file(self,path,data,author,reason,treeBuilder=None):
		pathParts = deque(path.split(PATH_SEPERATOR))
		name = pathParts.popleft()
		if len(pathParts) < 1:
#			if treeBuilder.get(name)!=None:
#				raise ValueError(name+" already exists")
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
#				print "Found the file: "+fileObj.id
				return gitstore.repo.read(fileObj.id)[1]
		raise KeyError("No such file")

	def standard_respose_headers(self):
		responseHeaders = {}
		if os.path.exists(STATUS_PATH):
			try:
				status_file = open(STATUS_PATH,'r')
				status_data = status_file.read()
				status_file.close()
				status_json = json.loads(status_data)
				responseHeaders["Node-Status"] = status_json["last-status"]
			except:
				print "Couldn't read status file "+STATUS_PATH
		try:
			responseHeaders["Last-Commit"] = self.find_last_commit().id
		except KeyError:
			pass
		return responseHeaders
		
	def http_get_path(self,path):	
		path = "/"+path
		pathParts = path.split("/")
		responseHeaders = self.standard_respose_headers()
		try:
			if pathParts[-1] == "":
				return (to_json(gitstore.list_files(path)),200,responseHeaders)
			else:
				return (gitstore.get_file(path),200,responseHeaders)
		except KeyError:
			return ("Not found\n", 404,responseHeaders)
		except ValueError:
			return ("Not found\n", 404,responseHeaders)

#HTTP handling stuff

gitstore = GitStore(PATH_TO_REPO)
@app.route('/v1.0/<regex(".*"):path>', methods=['GET'])
def getPath(path):
	return gitstore.http_get_path(path)

@app.route('/v1.0/<regex(".*"):path>', methods=['POST'])
def postPath(path):
	path = "/"+path
	data = json.dumps(request.get_json())
	committer = parse_committer(request.headers['Committer'])
	commitMessage = request.headers['Commit-Message']
	responseHeaders = gitstore.standard_respose_headers()
	gitstore.add_file(path,data,committer,commitMessage)
	responseHeaders["This-Commit"] = gitstore.find_last_commit().id
	return (data,201,responseHeaders)

@app.route('/v1.0/<regex(".*"):path>', methods=['DELETE'])
def delPath(path):
	path = "/"+path
	committer = parse_committer(request.headers['Committer'])
	commitMessage = request.headers['Commit-Message']
	responseHeaders = gitstore.standard_respose_headers()
	gitstore.delete_file(path,committer,commitMessage)
	responseHeaders["This-Commit"] = gitstore.find_last_commit().id
	return ("Deleted\n", 200, responseHeaders)

@app.route('/v1.0/<regex(".*"):path>', methods=['PATCH'])
def patchPath(path):
	path = "/"+path
	data = json.dumps(request.get_json())
	committer = parse_committer(request.headers['Committer'])
	commitMessage = request.headers['Commit-Message']
	responseHeaders = gitstore.standard_respose_headers()
	gitstore.patch_file(path,data,committer,commitMessage)
	responseHeaders["This-Commit"] = gitstore.find_last_commit().id
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
