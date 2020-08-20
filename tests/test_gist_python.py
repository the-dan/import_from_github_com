from github_com.gist26b151d6a0cbf7b044a9595f444a726f.sayhi import *

def test_import_module_bind():
	from github_com.gist26b151d6a0cbf7b044a9595f444a726f import sayhi

	assert callable(sayhi.sayHi)

def test_import_local_bind():
	

	assert callable(sayHi)

