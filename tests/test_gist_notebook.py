
def test_notebook_import():
	from github_com.gist26b151d6a0cbf7b044a9595f444a726f import mock

	assert callable(mock.mock_run)

def test_notebook_filename_with_spaces():
	from github_com.gist26b151d6a0cbf7b044a9595f444a726f import mock_with_spaces as m

	assert callable(m.mock_run)