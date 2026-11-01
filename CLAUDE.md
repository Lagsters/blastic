# BlasTIC — gra TIC-80 (Lua)

Arena dla czterech graczy (P1, P2 ludzie; P3, P4 boty). Kod to jeden plik `blastic.lua`,
cart `.tic` budowany z niego przez `make_tic.py`. Grafika i muzyka powstają w kodzie.
Cart pobiera aplikacja Melancholy z releasów tego repo.

## Zasady nadrzędne

Rozstrzygają każdy spór, w tej kolejności.

1. **Prostota.** Jeden plik, płaskie funkcje, bez abstrakcji na zapas. Działająca rozgrywka
   ważniejsza niż efekty.
2. **Standard ponad własne.** API TIC-80 (`btn`, `rect`, `sfx`…) i biblioteka standardowa Lua
   tak, jak są. Własne rozwiązanie tylko, gdy wskażesz w dokumentacji TIC-80, czego dokładnie
   brakuje; wtedy wiersz w `DEVIATIONS.md` i jedno zdanie w kodzie. Nowego wiersza nie dopisuj
   bez mojej decyzji.
3. **Kod tłumaczy się sam.** Nazwy mówią prawdę, domyślnie bez komentarza. Zostaje tylko zdanie,
   które zmieni decyzję kogoś zmieniającego kod (powód, ostrzeżenie przed regresją). Komentarz
   opisuje stan, nie historię. Bez zakomentowanego kodu. `TODO` tylko z odsyłaczem `#nr` issue.
4. **Grę pisze i testuje Claude, autonomicznie.** Szczegóły niżej.

## Autonomia i weryfikacja

- Bramka „gotowe”: `python check.py` (kod wyjścia 0). Uruchamia testy logiki
  (`lua test_blastic.lua`), symulację botów (`lua sim_blastic.lua 300 1`), build carta i sprawdza
  limit kodu 65535 B. Kodu wyjścia nie maskuj potokiem (`| tail`).
- Zmiana funkcji nie jest skończona bez testu w `test_blastic.lua`, który ją pokrywa.
- Błąd: **najpierw test, który go odtwarza (czerwony), potem poprawka.** Zielony test dowodzi,
  że poprawka pomogła.
- Rozgrywkę oceniasz mierzalnie, nie „na oko”: `sim_blastic.lua` zlicza wygrane, remisy, rundy
  bez końca, średnią długość rundy i sprawdza niezmienniki (gracz w ścianie, bomba na bloku,
  licznik bomb). „Brak błędu” stwierdzasz tylko ze źródła, które by go pokazało.
- Nie mówisz „działa”, dopóki sam nie uruchomisz i nie zobaczysz wyniku.
- Nowy mechanizm losowy sprawdzaj symulacją na wielu ziarnach (`lua sim_blastic.lua 300 <ziarno>`).
- Granice: zabawę, sterowanie i brzmienie ocenia tylko człowiek; wizualnie sprawdza je prawdziwy
  TIC-80, o ile jest zainstalowany.

## Architektura

| Plik | Rola |
|---|---|
| `blastic.lua` | cała gra; globalne `TIC()` i `init()` wymagane przez TIC-80 |
| `test_blastic.lua` | testy logiki, API TIC-80 zamockowane, ziarno stałe |
| `sim_blastic.lua` | symulator czterech botów bez grafiki, z niezmiennikami |
| `make_tic.py` | buduje `.tic` (tylko chunk kodu; wolny TIC-80 nie zapisuje `.lua`) |
| `check.py` | bramka „gotowe” |

- Statystyki gracza (`stats.bombs`, `stats.len`) są w `players[i].stats`; `humans[i]` mówi, czy
  gracz jest człowiekiem. Symulator ustawia wszystkich na boty.
- Limit kodu carta to 65535 B. Mierz po każdej większej zmianie.
- Teksty dla gracza po angielsku (ekran 240×136).

## Narzędzia

| Polecenie | Opis |
|---|---|
| `python check.py` | pełna bramka |
| `lua test_blastic.lua` | testy logiki |
| `lua sim_blastic.lua [rund] [ziarno]` | symulacja botów |
| `python make_tic.py` | build `blastic.tic` |
| `lua tools/shot.lua <dir>` + `python tools/shot.py <dir> <out>` | screeny tytułu i rozgrywki z kodu gry (napisy dorysowuje Pillow, więc krój pisma różni się od TIC-80) |

Lua 5.4, jak `lua5.4` w CI na Ubuntu 24.04. Windows: `winget install DEVCOM.Lua`.

## Proces

- Zadania to issue na GitHubie (`gh`). Gałąź `<nr-issue>-<opis>`; nie commituj do `main`.
- Commit: `<typ>(<zakres>): <temat>`; w stopce `Refs #nr` albo `Closes #nr`.
- Commit robisz lokalnie sam. **Push, merge, wpis w issue i PR tylko za moją zgodą.**
- Przed PR uruchom skill `audit`.

### Gdzie zapisujemy wiedzę

Każda treść ma jedno miejsce, w drugim jest tylko odsyłacz.

| Miejsce | Co | Czego nie |
|---|---|---|
| issue | co i po co, językiem skutku | rozwiązania w kodzie |
| commit / PR | co zmienia ta zmiana, wynik bramki | opisu architektury |
| komentarz w kodzie | dlaczego kod jest taki (stan obecny) | historii zmian |
| `DEVIATIONS.md` | własne rozwiązanie zamiast standardu: co, dlaczego, warunek powrotu | decyzji niezwiązanych ze standardem |
| `docs/decisions/` (ADR) | odrzucona opcja, którą ktoś bez kontekstu wybrałby sam | wyborów oczywistych |
| `HISTORY.md` | FAKT / DECYZJA / ŚLEPA ULICZKA z badań i sesji | stanu prac |
| `TODO.md` | stan prac i następny krok (górna sekcja = ostatnia sesja) | wiedzy na stałe |
| `CLAUDE.md` | reguły pracy | szczegółów jednego przypadku |

Na początku sesji czytaj `HISTORY.md` i górną sekcję `TODO.md`, żeby nie powtarzać odrzuconych
prób. Na końcu sesji aktualizuj `TODO.md`.
