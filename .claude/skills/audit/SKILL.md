---
name: audit
description: Audyt gałęzi przed PR — agent bez historii rozmowy sprawdza bramkę, standard i odstępstwa, komentarze, wiedzę na swoim miejscu. Tylko raportuje.
context: fork
agent: general-purpose
---

# /audit

Audytujesz gałąź względem `main` (`git diff main...HEAD` plus niezacommitowane zmiany). Nie znasz
rozmowy, w której powstała. **Niczego nie zmieniasz.** Najpierw przeczytaj `CLAUDE.md`
(„Zasady nadrzędne”, „Gdzie zapisujemy wiedzę”) i `DEVIATIONS.md`.

**Bramka:** `python check.py`; oceniaj kod wyjścia. Czerwona = „Do poprawy” bez dalszych przejść,
podaj pierwszy błąd.

**Przejście 1 — standard i odstępstwa:** własny mechanizm tam, gdzie wystarczy API TIC-80 albo
stdlib Lua, bez wiersza w `DEVIATIONS.md`; funkcja bez testu w `test_blastic.lua`; poprawka błędu
bez testu, który bez niej jest czerwony.

**Przejście 2 — komentarze i nazwy:** użyj skilla `global-comment-style` na zmienionych plikach.

**Przejście 3 — wiedza na swoim miejscu:** zgodność z tabelą w `CLAUDE.md` dla `HISTORY.md`,
`TODO.md`, commitów, opisu PR i issue; `TODO` w kodzie bez `#nr`; otwarty wątek review w PR.

Zgłaszasz tylko nieprawdę, sprzeczność, odstępstwo bez wiersza i treść w złym miejscu — każde
z dowodem (plik:linia). Nie zgłaszasz stylu ani sformułowań.

**Raport:** pierwsza linia: „OK — gotowe do PR” albo „Do poprawy: N blokujących”; wynik bramki;
blokujące; najwyżej 3 „do rozważenia”; czego nie sprawdzono. Znalezisko opisane w PR w sekcji
„Świadomie zostawione” nie wraca.
