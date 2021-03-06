 #!/usr/bin/env bash

if ! type "conda" > /dev/null; then
    wget http://repo.continuum.io/miniconda/Miniconda-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p ~/anaconda
    echo "export PATH=~/anaconda/bin/:$PATH" | tee -a ~/.bash_profile
    ~/anaconda/bin/conda config --set always_yes yes
    ~/anaconda/bin/conda config --add create_default_packages pip --add create_default_packages ipython
fi

CONDA_ENV_NAME=memex-explorer
~/anaconda/bin/conda update conda --yes
~/anaconda/bin/conda install -c conda conda-env --yes
~/anaconda/bin/conda env create --name=$CONDA_ENV_NAME --file=environment.yml
~/anaconda/bin/conda install -c binstar supervisor -n $CONDA_ENV_NAME --yes

echo `which python`
. activate $CONDA_ENV_NAME

if [ -n "${ACHE_HOME}" ]; then
  echo "ACHE HOME IS SET"
else
  echo "export ACHE_HOME=~/anaconda/envs/memex-explorer/lib/python2.7/site-packages/ache/" | tee -a ~/.bash_profile
  . ~/.bash_profile
  . activate $CONDA_ENV_NAME
fi

supervisord -c /vagrant/scripts/supervisord.conf
