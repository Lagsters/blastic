---
name: verify
description: Sprawdź zmianę w działaniu — bramka, symulacja botów na kilku ziarnach, dowód z wyniku. Użyj przed stwierdzeniem, że coś działa.
---

# /verify

Zasady weryfikacji: sekcja „Autonomia i weryfikacja” w `CLAUDE.md`.

1. `python check.py` — musi zwrócić kod 0.
2. Symulacja na kilku ziarnach: `lua sim_blastic.lua 300 1`, `... 7`, `... 42`. Szukaj: `errors>0`,
   `timeouts>0`, skrajnie nierównych wygranych P1..P4, nagłej zmiany średniej długości rundy.
3. Dla zmienianej funkcji sprawdź jej skutek w danych (stan gracza, liczba bomb, mapa), nie tylko
   brak crasha. Brakujący test dopisz najpierw jako czerwony.
4. Cart: `python make_tic.py` i rozmiar kodu względem 65535 B.
5. Raport: co sprawdzono (z liczbami), czego nie i dlaczego (np. wygląd, dźwięk, sterowanie).
