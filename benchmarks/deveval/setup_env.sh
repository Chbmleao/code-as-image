#!/bin/bash
# Run on phocus4 (login node, has internet). Downloads and installs only; runs no benchmark code.
set -euo pipefail
W=/snfs2/carlosleao/ufm7
mkdir -p $W/tools $W/deveval
export UV_INSTALL_DIR=$W/tools/uv UV_NO_MODIFY_PATH=1
export UV_PYTHON_INSTALL_DIR=$W/tools/python UV_CACHE_DIR=$W/tools/uv-cache
[ -x $W/tools/uv/uv ] || curl -LsSf https://astral.sh/uv/install.sh | sh
UV=$W/tools/uv/uv
[ -x $W/deveval/venv/bin/python ] || $UV venv --python 3.9.18 $W/deveval/venv
# requirement.txt from the DevEval repo, plus the pytest stack pinned in its environment.txt
$UV pip install --python $W/deveval/venv/bin/python -r $W/deveval/requirement.txt \
    pip==23.3 zope.interface==6.3 ruamel.yaml==0.18.6 ruamel.yaml.clib==0.2.8 jaraco.context==4.3.0 jaraco.functools==4.0.0 zope.deprecation==5.0 zope.event==5.0 zope.component==6.0 pytest==7.4.0 pytest-runner==6.0.0 setuptools==68.0.0 wheel==0.41.2 \
    exceptiongroup==1.0.4 iniconfig==1.1.1 packaging==23.1 pluggy==1.0.0 tomli==2.0.1
cd $W/deveval
[ -f Source_Code.tar.gz ] || curl -fL --retry 3 -o Source_Code.tar.gz \
    https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/Source_Code.tar.gz
[ -d src/Source_Code ] || { mkdir -p src && tar -xzf Source_Code.tar.gz -C src; }
du -sh $W/deveval/src; $W/deveval/venv/bin/python --version
