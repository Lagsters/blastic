"""Tests of the cart builder's minifier: python test_make_tic.py (exit code 1 on failure)."""
import sys
from make_tic import minify, lz_pack, lz_unpack

CASES = [
    ("comment after code", 'x=1 -- note\n', 'x=1\n'),
    ("indentation and blank lines", '  if a then\n\n    b()\n  end\n', 'if a then\nb()\nend\n'),
    ("dashes inside strings stay", 's="a -- b" t=\'c -- d\'\n', 's="a -- b"t=\'c -- d\'\n'),
    ("escaped quotes", 's="say \\"hi\\" -- x" -- c\n', 's="say \\"hi\\" -- x"\n'),
    ("block comments", 'a=1 --[[ two\nlines ]] b=2\n', 'a=1 b=2\n'),
    ("leveled block comments", 'a=1 --[==[ ]] still ]==] b=2\n', 'a=1 b=2\n'),
    ("spaces around operators go", 'a = b + c , d ( e )\n', 'a=b+c,d(e)\n'),
    ("spaces between words stay single", 'local  x  =  not   y\n', 'local x=not y\n'),
    ("minus minus stays apart", 'x = a - -b\n', 'x=a- -b\n'),
    ("concat next to numbers stays apart", 'y = 1 .. 2 .. z\n', 'y=1 .. 2 ..z\n'),
    ("spaces in strings stay", 's = "a  b" .. \'c  d\'\n', 's="a  b"..\'c  d\'\n'),
    ("long strings stay", 's=[[ -- kept\n  indented ]]\n', 's=[[ -- kept\nindented ]]\n'),
    ("cart metadata stays", '-- title:  BlasTIC\n-- script: lua\n-- plain\n', '-- title:  BlasTIC\n-- script: lua\n'),
    ("index brackets are not long strings", 'a[b[1]]=2 -- c\n', 'a[b[1]]=2\n'),
]


LZ_CASES = [b'', b'a', b'abcabcabcabc', b'x' * 1000, bytes(range(256)) * 3,
            open('blastic.lua', 'rb').read()]


def main():
    failed = 0
    for k, data in enumerate(LZ_CASES):
        packed = lz_pack(data)
        ok = lz_unpack(packed) == data
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  LZ round trip {k} ({len(data)} -> {len(packed)} B)")
    for name, src, want in CASES:
        got = minify(src)
        ok = got == want
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f": {got!r} != {want!r}"))
    print(f"  {len(CASES) + len(LZ_CASES) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
