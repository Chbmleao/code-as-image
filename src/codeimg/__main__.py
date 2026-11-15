"""python -m codeimg <stage> [args]. Stages are imported lazily, so the graders' Python 3.9
environment never imports the 3.11+ config loader."""
import importlib
import sys

STAGES = ["prompts", "sample", "generate", "claude", "answers", "collect"]


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
        sys.exit(f"usage: python -m codeimg {{{','.join(STAGES)}}} [args]")
    importlib.import_module(f"codeimg.{sys.argv[1]}").main(sys.argv[2:])


if __name__ == "__main__":
    main()
