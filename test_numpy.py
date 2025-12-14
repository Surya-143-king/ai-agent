# test_numpy.py -- run this from your project root (with venv active)
import os, sys, traceback

print("CWD:", os.getcwd())
print("FILES in CWD:", os.listdir("."))

print("\n--- Trying to import numpy ---")
try:
    import numpy as np
    print("numpy imported OK, version:", np.__version__)
    print("numpy file:", getattr(np, "__file__", "no __file__"))
except Exception:
    traceback.print_exc()

print("\n--- sys.path first 6 entries ---")
for p in sys.path[:6]:
    print(" -", p)
