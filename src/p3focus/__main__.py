"""`python -m p3focus run …` (A §5). The command itself is `run.py`."""
import sys

from p3focus.run import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
