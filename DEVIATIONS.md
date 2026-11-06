# Odstępstwa od zasady „standard ponad własne”

Własne rozwiązanie tylko tu wpisane. Nowego wiersza nie dopisuj bez decyzji właściciela.

| Co | Dlaczego (czego brakuje w stocku) | Warunek powrotu do standardu |
|---|---|---|
| Minifikacja kodu przy budowie carta (`make_tic.py`: bez komentarzy, wcięć i pustych linii) | Kod w banku carta TIC-80 to najwyżej 64 KB (`TIC_BANK_SIZE`, `src/tic.h`), a gra z kampanią przekracza to z komentarzami; kod w kilku bankach (do 512 KB, `TIC_CODE_SIZE`) nie jest pewny w rdzeniu Melancholy. Decyzja właściciela 2026-11-07. Testy biegną też na kodzie zminifikowanym (`check.py`). | Rdzeń Melancholy obsługuje kod w wielu bankach albo kod mieści się w 64 KB bez minifikacji. |
