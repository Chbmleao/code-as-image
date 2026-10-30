#!/bin/bash
# Defects4J v2.0.1 without root or Docker: JDK 8 and svn from conda-forge, Perl deps via cpanm
# into a local lib. Everything lives under $ROOT on /snfs2. Run on phocus4 (needs internet).
set -euo pipefail
ROOT=/snfs2/carlosleao/ufm7/d4j
mkdir -p $ROOT && cd $ROOT

if [ ! -x bin/micromamba ]; then
  curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba
fi
export MAMBA_ROOT_PREFIX=$ROOT/mamba
if [ ! -d env ]; then
  bin/micromamba create -y -p $ROOT/env -c conda-forge openjdk=8 subversion
fi

[ -d defects4j ] || git clone https://github.com/rjust/defects4j.git
(cd defects4j && git checkout -q v2.0.1)

[ -f cpanm ] || curl -sL https://cpanmin.us -o cpanm

# subversion pulls a conda perl into env/bin. Putting env/bin on PATH would shadow /usr/bin/perl,
# and that perl builds XS modules with a conda gcc that does not exist here. Expose only the
# Java and svn binaries.
mkdir -p $ROOT/shim
for b in java javac jar svn svnadmin svnversion; do ln -sf $ROOT/env/bin/$b $ROOT/shim/$b; done
cat > $ROOT/activate.sh <<A
export PATH=$ROOT/shim:$ROOT/defects4j/framework/bin:\$PATH
export JAVA_HOME=$ROOT/env
export PERL5LIB=$ROOT/perl5/lib/perl5\${PERL5LIB:+:\$PERL5LIB}
export TZ=America/Los_Angeles
A
# shellcheck source=/dev/null
source $ROOT/activate.sh
/usr/bin/perl cpanm --notest -l $ROOT/perl5 --installdeps ./defects4j

(cd defects4j && ./init.sh)
defects4j info -p Lang | head -5
