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
- **DECYZJA** 2026-11-01: start z jedną bombą (`MAX_BOMBS=1`); chodzenie dwa razy wolniejsze
  przez ruch co drugą klatkę (`MOVE_PERIOD=2`), bo pozycje są całkowite i nie da się ruszać o
  pół piksela; czas ucieczki bota (`BOT_FLEE_FRAMES`) i warunek bezpiecznej bomby liczą się
  z tą prędkością.
- **DECYZJA** 2026-11-01: bonusy mają ikony 8×8 w kolorach bez czerwieni (2), żeby leżąca bomba
  nigdy nie wyglądała jak bonus dodatkowej bomby.
- **FAKT** 2026-11-01: po wyrównaniu mapy lewy górny róg nadal wygrywa ok. 5 punktów
  procentowych częściej (4000 rund). Skos idzie za rogiem, nie za numerem gracza (sprawdzone
  obrotem `STARTS`). Losowa kolejność kierunków w BFS go nie usunęła (**ŚLEPA ULICZKA**,
  wycofane). Nieprzebadane: półpikselowa asymetria środka postaci (`p.c` zmienia się przy 4 px w
  prawo, a przy 5 px w lewo), kolejność generowania bloków.
- **FAKT** 2026-11-01: `/blastic.tic` w korzeniu domeny dawał 404 na Pages, bo odtwarzacz
  TIC-80 traktuje argument ze znakiem `/` na początku jako ścieżkę od korzenia; cart musi być
  podany ścieżką względną.
- **FAKT** 2026-11-02: w symulacji ok. 98% zgonów botów to śmierć od własnej bomby. Przyczyną był
  losowy spacer, który wchodził w linię wybuchu tykającej bomby (nie patrzył na mapę zagrożeń)
  oraz ucieczka zaczynana dopiero 100 klatek przed wybuchem. Po poprawce (spacer omija pola
  zagrożone, ucieczka przed każdą bombą, planista ucieczki z czasem i reakcją łańcuchową)
  samobójstw jest ok. 12× mniej.
- **FAKT** 2026-11-02: ostrożne boty rzadko się zabijają, więc rundy trwają ok. 3700 klatek zamiast
  ok. 650 i kończy je zamykająca się arena; symulacja 300 rund trwa kilka minut.
- **FAKT** 2026-11-02: bomba-pułapka (wróg bez drogi ucieczki, bot z drogą) to ok. 3% stawianych
  bomb; polowanie na pułapki nie zmieniło liczby zabójstw (24 na 25 rund w obu wariantach).
  Test pułapki w ślepym zaułku przechodzi także bez polowania na pułapki, więc nie dowodzi ich
  działania. Dalsza agresja wymaga innego mechanizmu niż pojedyncza pułapka.
