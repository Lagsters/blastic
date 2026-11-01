# BlasTIC

Four-player arena game for [TIC-80](https://tic80.com): drop blasts, break blocks and be the
last one standing. P1 and P2 are human, P3 and P4 are bots. Graphics and music are generated
in Lua; the cart contains only the code chunk.

Melancholy (Android TV libretro frontend by Lagsters) downloads the cart from this
repository's releases and uses it in its instrumented tests.

## Files

| File | Purpose |
|---|---|
| `blastic.lua` | game source (TIC-80 Lua cart) |
| `test_blastic.lua` | logic tests, TIC-80 API mocked; run with `lua test_blastic.lua` |
| `make_tic.py` | builds the binary `.tic` cart from the `.lua` source |

## Build

```
python make_tic.py
```

Writes `blastic.tic` next to `blastic.lua`. The free TIC-80 cannot load or save `.lua`
text carts (PRO feature), so the cart is built by `make_tic.py` instead of the TIC-80 CLI.

## Release

CI (`.github/workflows/build.yml`) tests and builds the cart on every push. Pushing a
`v*` tag publishes `blastic.tic` and its SHA-256 as release assets:

```
git tag v1.0.0 && git push origin v1.0.0
```

## License

All rights reserved, see `LICENSE`. The only permitted use without written consent is the
Melancholy application downloading and running the cart.

The TIC-80 engine is MIT-licensed; its license does not apply to carts made for it.
