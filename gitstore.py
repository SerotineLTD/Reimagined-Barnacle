#!/usr/bin/python

import pygit2
import os
import sys
import time
from collections import deque

PATH_TO_REPO = "/tmp/gitstore.git"
PATH_SEPERATOR = "/"

def find_last_commit():
	master = repo.lookup_reference("refs/heads/master")
	last_commit = master.get_object()
	return last_commit


def list_files(path):
	try:
		last_commit = find_last_commit()
		files = []
		for entry in last_commit.tree:
			files.append(entry.name)
		return files
	except KeyError:
		return []

def new_commit(treeId,author,reason):
	try:
		last_commit = find_last_commit()
		repo.create_commit('refs/heads/master',author,author,reason,treeId,[last_commit.id])
	except KeyError:
		repo.create_commit('refs/heads/master',author,author,reason,treeId,[])
		


def add_file(path,data,author,reason,treeBuilder=None):
	pathParts = deque(path.split(PATH_SEPERATOR))
	name = pathParts.popleft()
	if len(pathParts) < 1:
		if treeBuilder.get(name)!=None:
			raise ValueError(name+" already exists")
		id = repo.create_blob(data)
		treeBuilder.insert(name,id,pygit2.GIT_FILEMODE_BLOB)
		return treeBuilder
	else:
		sub_dir_path = PATH_SEPERATOR.join(pathParts)
		if name == "":
			# We add to root
			try:
				last_commit = find_last_commit()
				treeBuilder = repo.TreeBuilder(last_commit.tree)
			except KeyError:
				treeBuilder = repo.TreeBuilder()
			treeBuilder = add_file(sub_dir_path,data,author,reason,treeBuilder)
			treeId = treeBuilder.write()
			new_commit(treeId,author,reason)
		else:
			# we add to a named dir
			nextTree = repo.TreeBuilder()
			nextTree = add_file(sub_dir_path,data,author,reason,nextTree)
			treeId = nextTree.write()
			treeBuilder.insert(name,treeId,pygit2.GIT_FILEMODE_TREE)
			return treeBuilder
		
		
		


if(not os.path.isdir(PATH_TO_REPO)):
	pygit2.init_repository(PATH_TO_REPO,True)
repo = pygit2.Repository(PATH_TO_REPO)

files = list_files("/")

if len(files) < 1:
	data = '{"id":1}'
	add_file("/doc.json",data,pygit2.Signature('Sam Jones','sam@serotine.org'),'Adding test file')
	files = list_files("/")

if len(files) < 2:
	data = '{"id":2,"joke":"My dog\'s got no nose."}'
	add_file("/jokes/joke.json",data,pygit2.Signature('Sam Jones','sam@serotine.org'),'Adding a joke')
	files = list_files("/")



for fname in files:
	print "File: "+fname
sys.exit(0)


#for commit in repo.walk(repo.head.target):
#	print commit.message
#	for entry in commit.tree:
#		print(entry.id, entry.type, entry.name)
#		print repo[entry.id].data
#

#id = repo.create_blob("my dog has no nose")
#print id
#blob = repo[id]
#print blob.data

#treeBuilder = repo.TreeBuilder()
#treeBuilder.insert("dogJoke.txt",id,pygit2.GIT_FILEMODE_BLOB)
#treeId = treeBuilder.write()

#author = pygit2.Signature('Sam Jones','sam@serotine.org')
#repo.create_commit('refs/heads/master',author,author,'a commit message',treeId,[])

