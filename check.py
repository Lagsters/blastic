#!/usr/bin/env python3
"""Bramka "gotowe": testy logiki, symulacja botów, build carta, limit rozmiaru kodu."""
import shutil, subprocess, sys, os

LIMIT = 65535
lua = shutil.which("lua5.4") or shutil.which("lua")
if not lua:
    sys.exit("brak lua5.4/lua w PATH")

def run(name, cmd):
    print(f"== {name}", flush=True)
    if subprocess.run(cmd).returncode != 0:
        sys.exit(f"FAIL: {name}")

run("testy logiki", [lua, "test_blastic.lua"])
run("symulacja botow", [lua, "sim_blastic.lua", "300", "1"])
run("build carta", [sys.executable, "make_tic.py", "blastic.lua", "blastic.tic"])
size = os.path.getsize("blastic.lua")
print(f"rozmiar kodu: {size}/{LIMIT} B")
if size > LIMIT:
    sys.exit("FAIL: kod przekracza limit carta")
print("OK")
