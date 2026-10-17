"""Writes packaging/mixie.ico from Mixie's own icon drawing (used for Mixie.exe)."""
import importlib.util
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("mixie", os.path.join(root, "mixie.py"))
mixie = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mixie)
out = os.path.join(root, "packaging", "mixie.ico")
mixie.save_ico(out)
print("wrote", out, os.path.getsize(out), "bytes")
sys.exit(0)
