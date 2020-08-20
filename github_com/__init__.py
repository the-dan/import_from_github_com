import sys
import io

import os
import types
import logging

import pip

from pip._internal.vcs.versioncontrol import vcs, RevOptions

from functools import reduce
from pathlib import Path


from IPython import get_ipython
from nbformat import read


from IPython.core.interactiveshell import InteractiveShell

logger = logging.getLogger(__name__)

class IntermediateModule:
    """Module for paths like `github_com.nvbn`."""

    def __init__(self, fullname):
        self.__package__ = fullname
        self.__path__ = fullname.split('.')
        self.__name__ = fullname

class GithubComFinder:
    """Handles `github_com....` modules."""

    def find_module(self, module_name, package_path):
        if module_name.startswith("github_com.gist"):
            return GistLoader()
        if module_name.startswith('github_com'):
            return GithubComLoader()

class NotebookImporter:
    @classmethod
    def import_notebook(cls, modulename, nbpath):
        if nbpath is None:
            raise ImportError("No path")

        logger.debug("importing Jupyter notebook from %s" % nbpath)

        # load the notebook object
        with io.open(nbpath, 'r', encoding='utf-8') as f:
            nb = read(f, 4)

        mod = types.ModuleType(modulename)
        mod.__file__ = nbpath
        mod.__loader__ = None
        mod.__dict__['get_ipython'] = get_ipython

        shell = InteractiveShell.instance()

        # extra work to ensure that magics that would affect the user_ns
        # actually affect the notebook module's ns
        save_user_ns = shell.user_ns
        shell.user_ns = mod.__dict__

        try:
          for cell in nb.cells:
            if cell.cell_type == 'code':
                # transform the input to executable Python
                code = shell.input_transformer_manager.transform_cell(cell.source)
                # run the code in themodule
                exec(code, mod.__dict__)
        finally:
            shell.user_ns = save_user_ns

        return mod


class GistLoader:
    def __init__(self):
        # as per https://www.python.org/dev/peps/pep-0370/
        full_path = os.path.expanduser("~/.local/var/lib/pyremoteimport/")
        self.clone_path = full_path

    def _import_notebook(self, fullname):
        """import a notebook as a module"""

        gist_hash = fullname[len("github_com.gist"):fullname.rindex(".")]
        clone_path = self.clone_path % (gist_hash,)

        logger.debug(f"Gist hash: {gist_hash}. Clone path: {clone_path}")

        path = find_notebook(fullname, [clone_path])
        mod = NotebookImporter.import_notebook(fullname, path)

        return mod

    def _is_installed(self, fullname):
        try:
            self._import_module(fullname)
            return True
        except ImportError:
            return False

    def _is_intermediate_path(self, fullname):
        return fullname.count('.') < 2

    def _is_repository_path(self, fullname):
        return fullname.count('.') == 2

    def _detect_module(self, repo_path, name_parts):
        # TODO: it also might be a pip'able directory

        path = reduce(lambda u,v: os.path.join(u,v), [repo_path] + name_parts)
        nbpath = path + ".ipynb"
        pypath = path + ".py"

        nbpath_spaces = reduce(lambda u,v: os.path.join(u,v), [repo_path] + name_parts[:-1] + [name_parts[-1].replace("_", " ")])
        nbpath_spaces += ".ipynb"

        if os.path.isfile(nbpath):
            return ("notebook", nbpath)
        elif os.path.isfile(nbpath_spaces):
            return ("notebook", nbpath_spaces)
        elif os.path.isfile(pypath):
            return ("python", pypath)
        else:
            return ("unknown", None)

    def _import_module(self, fullname):
        try:
            logger.debug("Trying to import regular python")
            actual_name = '.'.join(fullname.split('.')[2:])
            logger.debug(f"Actual name: {actual_name}")
            m = __import__(actual_name)
            sys.modules[fullname] = m
            return m
        except (ImportError, KeyError):
            return self._import_notebook(fullname)
        
    def _ensure_clone_path_present(self):
        Path(self.clone_path).mkdir(parents=True, exist_ok=True)


    def _install_module(self, fullname, gist_hash):
        repo_path = os.path.join(self.clone_path, gist_hash)

        #if not self._is_installed(fullname):
        url = "https://gist.github.com/%s.git" % (gist_hash,)
        
        self._ensure_clone_path_present()

        repo_path = os.path.join(self.clone_path, gist_hash)
        git = vcs.get_backend_for_scheme("git+https")
        if not os.path.exists(repo_path):
            logger.debug("Cloning %s to %s", url, repo_path)
            git.fetch_new(repo_path, url, RevOptions(git, "master"))
        else:
            logger.debug("Updating %s from %s", repo_path, url)
            git.update(repo_path, url, RevOptions(git, "master"))

        return repo_path

    def load_module(self, fullname):
        logger.debug(f"Trying to load module {fullname}")

        if self._is_intermediate_path(fullname):
            module = IntermediateModule(fullname)
            sys.modules[fullname] = module
            return

        parts = fullname.split(".")
        actual_module_root = parts[1]
        if actual_module_root.startswith("gist"):
            gist_hash = actual_module_root[len("gist"):]
        else:
            # TODO: GithubCom loader should be used here
            # though it seems that gist importer is wider than Github importer
            raise ImportError("Not a gist")

        repo_path = self._install_module(fullname, gist_hash)
        
        module_type, filepath = self._detect_module(repo_path, parts[2:])

        if module_type == "unknown":
            raise ImportError("Can't load this module: %s" % (".".join(parts[2:])))

        if module_type == "notebook":
            module = NotebookImporter.import_notebook(fullname, filepath)
        elif module_type == "python":
            actual_name = '.'.join(fullname.split('.')[2:])
            sys.path.append(repo_path)
            module = __import__(actual_name)

        sys.modules[fullname] = module
        


class GithubComLoader:
    """Installs and imports modules from github."""

    def _is_installed(self, fullname):
        try:
            self._import_module(fullname)
            return True
        except ImportError:
            return False

    def _import_module(self, fullname):
        actual_name = '.'.join(fullname.split('.')[2:])
        return __import__(actual_name)

    def _install_module(self, fullname):
        if not self._is_installed(fullname):
            url = fullname.replace('.', '/') \
                .replace('github_com', 'git+https://github.com', 1)
            pip.main(['install', url])

    def _is_repository_path(self, fullname):
        return fullname.count('.') == 2

    def _is_intermediate_path(self, fullname):
        return fullname.count('.') < 2

    def load_module(self, fullname):
        if self._is_repository_path(fullname):
            self._install_module(fullname)

        if self._is_intermediate_path(fullname):
            module = IntermediateModule(fullname)
        else:
            module = self._import_module(fullname)

        sys.modules[fullname] = module


logger.debug("Installing github remote packages finder")
sys.meta_path.append(GithubComFinder())
#sys.meta_path.append(GithubComFinder)
