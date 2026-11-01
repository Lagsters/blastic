---
name: orient
description: Orientacja na początku sesji — gałąź, stan repo, bramka, następny krok z TODO.md. Tylko rozpoznanie, bez implementacji.
---

# /orient

Nie zaczynaj implementacji — zbierz stan i streść go.

1. Przeczytaj górną sekcję `TODO.md` („NASTĘPNY KROK”) i `HISTORY.md` w całości (to ślepe uliczki,
   których nie wolno powtarzać).
2. Stan repo:
   ```bash
   git branch --show-current
   git log --oneline -8
   git status --short
   git rev-list --left-right --count origin/main...HEAD
   ```
   Niezacommitowane zmiany to prawdopodobnie przerwana praca — porównaj z `TODO.md`.
3. Bramka: `python check.py`; oceń kod wyjścia, nie ostatnią linię.
4. Issue powiązane z gałęzią: `gh issue view <nr>` (numer z nazwy gałęzi).
5. Raport: gdzie jesteśmy, czy bramka przechodzi, następny krok (zacytuj z `TODO.md`).
   Zapytaj, czy zaczynać.

Mapa projektu i polecenia: sekcje „Architektura” i „Narzędzia” w `CLAUDE.md`.
