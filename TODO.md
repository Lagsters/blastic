# Stan prac

## Sesja 2026-11-07 (gałąź `amiga-music`, scenki fabularne)
- Zrobione: fabuła „Legenda o siarce” (Wrocław, Ślęża, Kraków, piekło) w pięciu filmach,
  intro, menu z językiem (EN/PL), nastroje muzyki; tła szczegółowe i realistyczne; postacie
  realistyczne ze szkieletu (`tools/scenes/body.py`): chód biomechaniczny, 8 klatek na cykl,
  stopa się nie ślizga, rzuty i skoki z ziemską grawitacją; zbliżenia z tego samego modelu.
- Grafika w bankach pamięci TIC-80: postacie w banku 0, tła w bankach 1–7 (`sync`, raz na
  klatkę); sprawdzone w TIC-80 1.4.1. Nie sprawdzone w rdzeniu Melancholy.
- Narzędzia dev: `lua tools/film.lua <dir>` + `python tools/film.py` (MP4 z dźwiękiem),
  `python make_tic.py --films` (cart `films.tic`).
- Do oceny przez człowieka: wygląd postaci i zbliżeń, tempo filmów, hejnał jako dźwięk.
- PR po `audit`. Odłożone z audytu: wiersze w `DEVIATIONS.md` (tracker PCM, polskie litery w
  czcionce, fabuła LZ w MUSIC PATTERNS, grafika w bankach przez `sync`) do decyzji właściciela;
  issue dla tej pracy.
- NASTĘPNY KROK: ocena właściciela na stronie; sprawdzenie banków w Melancholy.

## Sesja 2026-11-06 (gałąź `amiga-music`)
- Zrobione: 60-sekundowa piosenka w klimacie Jaguar XJ220 (bas z próbek, synth, perkusja) z
  `tools/music/compose.py`, konwerter WAV → IMA ADPCM z listą kolejności taktów
  (`tools/music/wav2tic.py`), odtwarzanie przez kanał PCM TIC-80 1.4, `music.bin` w carcie.
  Brzmienie zaakceptowane przez właściciela (odsłuch). Później zastąpione trackerem (`HISTORY.md`).
- Do oceny przez człowieka: głośność muzyki względem efektów (`--gain` 1.0, mało zapasu dla SFX).
- Do sprawdzenia: czy rdzeń libretro TIC-80 w Melancholy to wersja 1.4+ (starsza nie ma PCM: cisza).
- NASTĘPNY KROK: issue dla tej zmiany i dla błędnych adresów SFX w `initAudio`, potem PR po `audit`.

## Sesja 2026-11-02
- Zrobione: poprawa botów (spacer omija pola zagrożone, ucieczka przed każdą bombą, planista
  ucieczki z czasem, zbieranie bonusów, bomba na wroga w linii, polowanie na pułapki).
- Zamykanie areny: boki do kwadratu, potem obrys równo (miganie coraz szybsze); boty uciekają w głąb.
- Skos narożników w symulacji botów zmalał do poziomu szumu (losowa kolejność kierunków BFS na
  bota); do potwierdzenia na większej próbie, patrz `HISTORY.md`.
- NASTĘPNY KROK: zagranie z żywym człowiekiem (tempo rund ok. 3100 klatek, remisy 14%, czas
  zamykania do strojenia), potem PR po `audit`.

## Sesja 2026-11-01
- Zrobione: wszystkie funkcje areny (łańcuch, bonusy, bot BFS, HUD i mecz, zamykająca się arena,
  dźwięk i animacje), MIT, Pages (https://lagsters.github.io/blastic/), release v1.1.0; w tej
  gałęzi: start z jedną bombą, chodzenie dwa razy wolniejsze, ikony bonusów zamiast kwadratów,
  testy helperów, przegląd komentarzy, szeroka symulacja (4000 rund, 0 błędów).
- NASTĘPNY KROK: zagranie w prawdziwym TIC-80 i w przeglądarce (wygląd, sterowanie, dźwięk,
  tempo po spowolnieniu), potem strojenie: szansa dropu, siła bota, czas zamykania areny.
- Melancholy: przypięcie sumy SHA-256 nowego releasu robi sesja `melancholy-e6` (jej repo).
