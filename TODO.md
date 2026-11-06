# Stan prac

## Sesja 2026-11-06 (gałąź `amiga-music`)
- Zrobione: muzyka w klimacie Amigi z MusicGen (lokalnie, GPU), konwerter WAV → IMA ADPCM
  (`tools/music/wav2tic.py`), odtwarzanie przez kanał PCM TIC-80 1.4, `music.bin` w carcie.
  Sprawdzone w TIC-80 1.4.1: nagranie wyjścia audio koreluje z pętlą i zawija się na końcu.
- Do oceny przez człowieka: brzmienie, głośność muzyki względem efektów (`--gain`, teraz 0.8).
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
