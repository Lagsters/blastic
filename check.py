#!/usr/bin/env python3
"""Bramka "gotowe": testy minifikatora i logiki (źródło i kod z carta), build carta, limit kodu;
z --sim także symulacja botów."""
import shutil, subprocess, sys, os

winget_bin = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Lua", "bin")
lua = shutil.which("lua5.4") or shutil.which("lua") or shutil.which("lua", path=winget_bin)
if not lua:
    sys.exit("brak lua5.4/lua w PATH")

def run(name, cmd):
    print(f"== {name}", flush=True)
    if subprocess.run(cmd).returncode != 0:
        sys.exit(f"FAIL: {name}")

MIN = os.path.join(os.environ.get("TEMP", "/tmp"), "blastic.min.lua")
run("testy minifikatora", [sys.executable, "test_make_tic.py"])
run("testy logiki", [lua, "test_blastic.lua"])
run("minifikacja", [sys.executable, "make_tic.py", "--min", "blastic.lua", MIN])
run("testy logiki na kodzie z carta", [lua, "test_blastic.lua", MIN])
if "--sim" in sys.argv:  # only when bot behaviour changes; it takes minutes
    run("symulacja botow", [lua, "sim_blastic.lua", "300", "1"])
# make_tic.py fails the build when the code or the story section outgrows its place
run("build carta", [sys.executable, "make_tic.py", "blastic.lua", "blastic.tic"])
run("cart w działaniu", [lua, "tools/cart_run.lua", "blastic.tic"])
print("OK")
