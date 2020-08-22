import os
import logging

def test_custom_repo():

	d = os.path.dirname(__file__)
	local_repo_url = os.path.join(d, "%s")
	logging.debug("Local repo url: %s", local_repo_url)

	from github_com import register
	register("local", local_repo_url)

	from local.gitrepo import repo

	assert callable(repo.repoTest)
	assert "repo function" == repo.repoTest()

