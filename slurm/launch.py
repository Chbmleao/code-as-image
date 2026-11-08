"""Run a codeimg module from the code dir this file sits in, under `python -I`.

-I drops PYTHONPATH and the script's directory from sys.path, which keeps a stray module in a
benchmark repo or the working directory from shadowing ours. This adds back only <code>/src.

usage: python -I slurm/launch.py codeimg.grade.coderujb ARGS...
"""
import os
import runpy
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
module = sys.argv[1]
sys.argv = [module] + sys.argv[2:]
runpy.run_module(module, run_name="__main__", alter_sys=True)
