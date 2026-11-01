# Historia ustaleń

Format wpisu: **FAKT** / **DECYZJA** / **ŚLEPA ULICZKA**, data, jedno–dwa zdania.

- **DECYZJA** 2026-11-01: licencja MIT (Lagsters); gra darmowa, do pobrania w Melancholy i do
  grania w przeglądarce.
- **DECYZJA** 2026-11-01: testy lokalnie na natywnym Lua 5.4.6 (winget), jak `lua5.4` w CI;
  Docker odrzucony jako zbyt wolny w pętli autonomicznej.
- **DECYZJA** 2026-11-01: bez bonusu szybkości; bonusy to bomba, zasięg i osłonka.
- **FAKT** 2026-11-01: mapa 30×17 z filarami w parzystych kolumnach nie jest lustrzana (odbicie
  kolumny zmienia parzystość), więc rogi po prawej wygrywały ~3× częściej; filary są teraz
  rozmieszczone symetrycznie (test `walls mirror left-right`).
- **DECYZJA** 2026-11-01: zasięg wybuchu liczony osobno dla każdej bomby (`b.len`, ustawiany przy
  stawianiu), bo bonus zasięgu zmienia `stats.len` już po postawieniu innych bomb.
- **FAKT** 2026-11-01: worktree agentów workflow powstają z pierwotnego commita repo, nie z
  bieżącej gałęzi; praca musi być na tym commicie albo scalana ręcznie.
- **ŚLEPA ULICZKA** 2026-11-01: zapis plików skryptem Pythona w trybie tekstowym na Windows daje
  CRLF; `.gitattributes` wymusza LF.
