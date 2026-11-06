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
- **FAKT** 2026-11-01: po wyrównaniu mapy lewy górny róg nadal wygrywał ok. 5 punktów
  procentowych częściej (4000 rund); skos szedł za rogiem, nie za numerem gracza. Losowa kolejność
  kierunków w BFS **wywoływana w każdej klatce** go nie usunęła (**ŚLEPA ULICZKA**, wycofane;
  trasa drżała). Przyczynę ustalono 2026-11-02, patrz niżej (stała losowa kolejność na bota).
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
- **DECYZJA** 2026-11-02: arena zamyka się krokami co 180 klatek (`SHRINK_CYCLE`), pierwszy po 1200 (`SHRINK_DELAY`): najpierw dwie
  boczne kolumny naraz, aż pole jest prawie kwadratowe, potem cały obrys równo; krok miga 120
  klatek (`SHRINK_WARN`), coraz szybciej, i zamyka się całością. Bez pojedynczych kafelków, bo
  o wygranej decydowałby los (wcześniejszy wariant z kafelkami na końcu to **ŚLEPA ULICZKA**).
  Boty traktują migający krok jako ogień i uciekają w głąb.
- **FAKT** 2026-11-02: przyczyną skosu narożników była stała kolejność kierunków w BFS botów
  (góra, dół, lewo, prawo): przy równie krótkich trasach bot zawsze wybierał ten sam kierunek.
  Przed poprawką P4 (prawy dolny) wygrywał ok. 40%, P1 (lewy górny) ok. 13%; odwrócenie kolejności
  przesunęło skos. Teraz każdy bot dostaje stałą na rundę losową kolejność (`botOrder`): udział
  wygranych 17/21/30/26% (150 rund, χ² p≈0,11, w granicach szumu). Losowanie w każdej klatce
  dawałoby drżenie trasy (**ŚLEPA ULICZKA**).
- **DECYZJA** 2026-11-02: czasy zamykania skrócone z 1800/300/180 do 1200/180/120 klatek (start,
  cykl, miganie): rundy z botami trwają ok. 3100 klatek zamiast ok. 4900; kosztem są remisy
  (14% zamiast 7%, bo ocaleni giną w ostatnim kroku razem). Okno migania 120 klatek wystarcza
  na ucieczkę z korytarza długiego na 7 pól; dłuższa ślepa uliczka na skraju areny kończy się
  śmiercią.
- **FAKT** 2026-11-06: TIC-80 1.4 ma kanał PCM: co klatkę gra 128 bajtów bez znaku z `0x14E24`
  (7680 Hz, 8 bit), niezależnie od czterech kanałów SFX, i zeruje je na początku klatki
  (`src/core/sound.c`, `runPcm`). Muzyka gry to pętla IMA ADPCM dekodowana w `TIC()`.
- **FAKT** 2026-11-06: wolna pamięć carta, której gra nie używa: kafle+sprite'y+mapa (49 024 B) i
  wzorce+ścieżki muzyki (11 928 B); region SFX zostaje dla efektów. Przy 4 bitach na próbkę
  mieści się 15,8 s; pętla ma 8 taktów (13,8 s, 139 BPM, SNR 21 dB względem 7680 Hz).
- **ŚLEPA ULICZKA** 2026-11-06: dłuższa pętla przez podmianę podobnych taktów lub beatów jedną
  próbką (k-medoids na log-mel, lista kolejności jak w module Amigi): SNR ok. 0 dB, bo muzyka z
  MusicGen nigdy nie powtarza się próbka w próbkę; zostaje jako opcja `--slice` dla dłuższych utworów.
- **FAKT** 2026-11-06: `initAudio` w `blastic.lua` pisze fale pod `0x14000` i SFX pod `0x14100`;
  w TIC-80 1.x to głośność stereo i pamięć trwała (pmem). Fale są pod `0x0FFE4`, SFX pod `0x100E4`.
  Błąd nienaprawiony (osobne zadanie).
- **FAKT** 2026-11-06: w TIC-80 1.4.1 na Windows przechwytywanie okna przez gdigrab po tytule daje
  stałą klatkę; zrzut pulpitu (`-i desktop`) pokazuje stan faktyczny.
- **ŚLEPA ULICZKA** 2026-11-06: muzyka z MusicGen-small (dwie serie po kilka prób, także z opisem
  „gitary z przodu”): właściciel odrzucił, brak przekonujących gitar; ACE-Step 1.5 nie zmieścił się
  na dysku. Synteza basu (Karplus-Strong) brzmiała sztucznie. Zostały próbki gitary basowej z
  GeneralUser GS (Finger/Slap Bass) i synteza reszty w `compose.py`.
- **FAKT** 2026-11-06: wzorzec brzmienia to Jaguar XJ220 (Amiga). Jego bas ma słabą podstawę i
  harmoniczne 2–4 o 12–20 dB mocniejsze, energię w 60–250 Hz i wybrzmienie ok. 300 ms; bas w E1
  (41 Hz) na głośnikach laptopa jest niesłyszalny, dlatego riff gra od E2.
- **FAKT** 2026-11-06: utwór z kodu ma 32 takty z 8 typów; podmiana taktów w `wav2tic.py`
  przypisuje je bezbłędnie i daje SNR 26 dB przy 60 s w 57,7 KB (ciągła pętla zmieściłaby 15,9 s).
