# Stan prac

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
