# MCP Kdenlive — Wymagania (MoSCoW)

## Kontekst

Budujemy MCP tool server, który pozwoli agentom AI (Claude, GPT, etc.) na pełny nieliniowy montaż wideo w Kdenlive — bez GUI, bez zrzutów ekranu, operując wyłącznie na strukturze projektu i minimalnych podglądach wizualnych.

**Zasada naczelna: Token Efficiency.**
Agent AI płaci za każdy token kontekstu. Dlatego:
- Stan projektu → tekst (listy, tabele), nigdy screenshoty GUI
- Podgląd klatek → thumbnail max 480px (krótszy bok), JPEG q70
- Kontrola jakości → wycinek 1:1 (np. 480×480px z wybranego regionu), nigdy pełna klatka 1920×1080 czy 4K
- Podgląd audio → dane liczbowe (RMS, peak, waveform jako lista wartości), nigdy spektrogram jako obraz

---

## MUST HAVE — bez tego agent nie zmontuje niczego

### M1. Orientacja w projekcie
Agent musi umieć "rozejrzeć się" po projekcie — co mam do dyspozycji?

- Listowanie wszystkich mediów w Media Pool (nazwa, typ, duration, rozdzielczość, codec, fps)
- Listowanie folderów w Media Pool
- Odczyt stanu timeline jako tekst: tabela klipów z pozycjami (start, end, track, nazwa pliku, typ przejścia na krawędziach)
- Odczyt ustawień projektu (fps, rozdzielczość, nazwa)
- Odczyt liczby i nazw tracków (video, audio, subtitle)

### M2. Import mediów
Agent musi umieć wciągnąć pliki do projektu.

- Import listy plików (ścieżki) do Media Pool
- Import z wzorcem glob (np. `scene-*/scene*-final.png`)
- Tworzenie folderów w Media Pool i organizacja klipów
- Rozpoznanie typu: video vs still image vs audio (i ustawienie domyślnego duration dla still)

### M3. Budowanie timeline
Agent musi umieć ułożyć klipy na osi czasu.

- Tworzenie pustego timeline z parametrami (nazwa, fps, rozdzielczość)
- Dodawanie klipu na konkretną pozycję (track, frame/timecode)
- Sekwencyjne dopisywanie klipów (append)
- Ustawianie duration klipu (rozciąganie still frames, trimowanie video)
- Przesuwanie klipu na timeline (zmiana pozycji)
- Usuwanie klipu z timeline
- Dodawanie ścieżki audio i umieszczanie na niej pliku audio

### M4. Trimowanie i dopasowanie
Agent musi umieć przycinać klipy.

- Ustawianie in/out point klipu źródłowego (który fragment pliku jest widoczny)
- Trim z lewej/prawej (skracanie klipu na timeline)
- Ripple edit (przesunięcie reszty timeline po trimie)
- Odczyt aktualnego in/out point i duration

### M5. Przejścia
Agent musi umieć definiować przejścia między klipami.

- Dodanie przejścia między dwoma sąsiednimi klipami (dissolve, wipe, cut)
- Ustawienie duration przejścia (w klatkach lub sekundach)
- Usunięcie przejścia
- Listowanie przejść na timeline

### M6. Zapis i odczyt projektu
Agent musi umieć zapisywać i wczytywać stan.

- Zapis projektu do pliku .kdenlive
- Wczytanie istniejącego projektu .kdenlive
- Roundtrip: wczytaj → modyfikuj → zapisz (bez utraty danych dodanych w GUI)

### M7. Eksport / render
Agent musi umieć wyrenderować wynik.

- Render timeline do pliku video (MP4/H264 jako minimum)
- Ustawienie parametrów renderowania (format, codec, rozdzielczość, quality)
- Sprawdzenie statusu renderowania (progress, done/error)
- Render fragmentu timeline (in/out range)

### M8. Tekstowy podgląd stanu
Agent potrzebuje "oczu" w formie tekstu, nie pikseli.

- `get_timeline_summary` → tabela markdown: nr | track | start TC | end TC | duration | filename | transition
- `get_project_info` → dict z ustawieniami
- `get_media_pool_contents` → lista z metadanymi
- `get_track_summary` → ile klipów, łączny czas, gaps

---

## SHOULD HAVE — znacząco poprawia jakość montażu

### S1. Podgląd wizualny (thumbnail)
Agent czasem musi "zobaczyć" klatkę — ale tanio tokenowo.

- Render pojedynczej klatki z timeline na danym timecode → JPEG thumbnail (max 480px krótszy bok)
- Render klatki z Media Pool item (np. klatka 0, środkowa, ostatnia)
- Opcja: strip thumbnailowy (np. 8 klatek równomiernie rozłożonych z klipu, w jednym obrazku jak contact sheet)
- Zwracanie jako base64 inline lub ścieżka do pliku tymczasowego

### S2. Kontrola jakości (crop 1:1)
Agent musi umieć ocenić ostrość, artefakty, detale — ale na wycinku, nie na pełnym kadrze.

- Render wycinku klatki z timeline w skali 1:1 (np. 480×480px z podanego regionu: center, top-left, face area)
- Predefiniowane regiony: `center`, `top-third`, `bottom-third`, `left-third`, `right-third`, `custom(x,y,w,h)`
- Użycie: agent sprawdza np. czy twarz jest ostra, czy nie ma artefaktów na krawędziach

### S3. Markery
Agent musi umieć oznaczać punkty na timeline.

- Dodanie markera na timeline (frame, kolor, nazwa, notatka)
- Listowanie markerów
- Usuwanie markerów
- Markery na klipach w Media Pool

### S4. Batch operacje
Agent często robi to samo 38 razy (raz per scena).

- Batch import z mapą: `{scene_nr → file_path}`
- Batch append: lista klipów z durations → sekwencyjnie na timeline
- Batch transitions: mapa `{(scene_a, scene_b) → transition_type, duration}`
- Batch replace: podmień klip N na nowy plik, zachowaj pozycję i duration

### S5. Podmiana klipu (replace)
Agent musi umieć podmienić scenę na nową wersję.

- Podmiana klipu na timeline: nowy plik, zachowana pozycja + duration + sąsiednie przejścia
- Podmiana w Media Pool: relink do nowego pliku
- Opcje: replace video only / audio only / both

### S6. Audio — podstawy
Agent musi umieć pracować z audio.

- Ustawienie głośności klipu audio (gain, w dB)
- Fade in / fade out audio (długość w klatkach)
- Mute/unmute tracku
- Odczyt peak/RMS audio (jako liczby, nie obraz) dla synchronizacji
- Przesunięcie audio relative do video (offset w klatkach/ms)

### S7. Cofanie zmian
Agent musi umieć się wycofać z błędu.

- Undo ostatniej operacji
- Undo N operacji
- Checkpoint: zapisz stan → eksperymentuj → przywróć checkpoint
- Alternatywa: operuj na kopii projektu, potem zamień

---

## COULD HAVE — rozszerza możliwości, nie blokuje MVP

### C1. Efekty video
- Aplikowanie filtra do klipu (brightness, contrast, saturation, blur)
- Keyframe'y efektów (wartość efektu zmienia się w czasie)
- Speed ramp (przyspieszenie/zwolnienie klipu)
- Opacity klipu (dla kompozycji na wielu trackach)

### C2. Tekst i tytuły
- Dodanie klipu tekstowego (title) na timeline
- Ustawienie treści, fontu, rozmiaru, pozycji, koloru
- Lower thirds, napisy

### C3. Color grading — podstawy
- Lift / Gamma / Gain per klip
- LUT: załaduj i zastosuj do klipu lub tracku
- Kopiowanie grade'a z jednego klipu na inne

### C4. Multi-track compositing
- Układ klipów na wielu trackach video (overlay)
- Ustawienie blend mode klipu (normal, multiply, screen, overlay)
- Picture-in-picture (pozycja, skala klipu na wyższym tracku)
- Crop klipu (kadrowanie)

### C5. Analiza mediów
- Wykrywanie cięć w pliku video (scene detection)
- Średnia jasność/kolor per klatka (jako dane liczbowe — do oceny spójności kolorystycznej)
- Detekcja czarnych klatek (glitch detection)
- Porównanie dwóch klatek: SSIM/PSNR score (jako liczba, nie obraz)

### C6. Timeline navigation
- Konwersja frame ↔ timecode ↔ sekundy
- Wyszukiwanie klipów po nazwie/atrybucie
- Snap to: najbliższe cięcie, marker, beat (jeśli audio beat-mapped)

### C7. Audio — zaawansowane
- Waveform jako lista wartości (np. RMS co 0.1s) — do wizualizacji lub beat detection po stronie agenta
- Normalizacja audio
- Ducking: automatyczne ściszanie muzyki pod dialogiem
- Crossfade audio na przejściach

### C8. Eksport do formatów wymiany
- Eksport timeline do EDL, FCPXML, OTIO (OpenTimelineIO)
- Import timeline z EDL/FCPXML/OTIO
- Eksport listy materiałów (media manifest) do CSV/JSON

---

## WON'T HAVE — nie robimy w tym projekcie

### W1. Streaming podglądu w czasie rzeczywistym
Agent nie ogląda wideo w real-time. Nie budujemy playbacku ani streamingu klatek.

### W2. Zrzuty ekranu GUI Kdenlive
Agent nie potrzebuje widzieć interfejsu. Wszystko przez API tekstowe + punktowe thumbnails.

### W3. Full-resolution preview
Nigdy nie wysyłamy agentowi klatki 1920×1080, 2K, 4K. Thumbnails max 480px, crop 1:1 max 480×480px.

### W4. Rozpoznawanie treści video (vision AI)
MCP server nie analizuje zawartości klatek (face detection, object recognition). To zadanie agenta po stronie klienta, jeśli dostanie thumbnail.

### W5. Obsługa efektów Fusion / OFX
Nie replikujemy pipeline'u efektów DaVinci Resolve. Podstawowe filtry MLT — tak. Node-based compositing — nie.

### W6. Interaktywna sesja z GUI
Nie sterujemy GUI Kdenlive w czasie rzeczywistym (jak Selenium). Operujemy na plikach projektu offline lub przez potencjalny MLT rendering pipeline.

### W7. Synchronizacja wieloosobowa / collaboration
Brak obsługi wielu agentów edytujących ten sam projekt jednocześnie.

---

## Architektura MCP — szkic procesowy

```
┌─────────────┐     MCP Protocol      ┌──────────────────┐      D-Bus       ┌───────────────┐
│  AI Agent    │◄─────────────────────►│  MCP Server      │◄───────────────►│  Kdenlive GUI  │
│  (Claude)    │  tools + resources    │  (Python)        │  org.kde.        │  (uruchomione) │
│              │                       │                  │  kdenlive.       │                │
│  - planuje   │                       │  kdenlive_api    │  scripting       │  Q_SCRIPTABLE  │
│  - decyduje  │                       │  ├── Resolve     │                  │  metody w      │
│  - sprawdza  │                       │  ├── Project     │  44 metody       │  mainwindow.cpp│
│              │                       │  ├── MediaPool   │                  │                │
│              │                       │  ├── Timeline    │                  │                │
│              │                       │  └── TimelineItem│                  │                │
└─────────────┘                       └──────────────────┘                  └───────────────┘
```

**Architektura jest identyczna jak DaVinci Resolve API:**
- Resolve łączy się przez `fusionscript.dll` → runtime Resolve
- Kdenlive łączy się przez `D-Bus` → runtime Kdenlive (zmodyfikowany build z `org.kde.kdenlive.scripting`)
- Agent woła `project.GetMediaPool()`, `timeline.GetItemListInTrack("video", 1)` — identyczne sygnatury
- Kdenlive **musi być uruchomione** — tak samo jak Resolve musi być uruchomione dla swojego API
- MCP Server to cienka warstwa: mapuje MCP tool calls → metody `kdenlive_api` → D-Bus → Kdenlive

### Przepływ pracy agenta

1. **Rozpoznanie** — agent woła `get_project_info`, `get_media_pool_contents`, `get_timeline_summary`
2. **Planowanie** — na podstawie tekstu (scenariusz, timing) agent ustala plan montażu
3. **Budowanie** — agent woła `create_timeline`, `import_media`, `append_clips`, `add_transition`
4. **Weryfikacja** — agent woła `get_timeline_summary` (tekst) + `render_thumbnail` (na kluczowych momentach)
5. **Korekta** — agent woła `replace_clip`, `trim_clip`, `move_clip`
6. **Kontrola jakości** — `render_crop_1to1` na wybranych fragmentach (ostrość, artefakty)
7. **Finalizacja** — `render_video` → gotowy plik

### Budżet tokenów per operacja (szacunek)

| Operacja | Tokeny (input) | Tokeny (output) |
|----------|----------------|-----------------|
| `get_timeline_summary` (38 klipów) | ~50 | ~800 |
| `get_media_pool_contents` (80 plików) | ~50 | ~1200 |
| `render_thumbnail` (480px JPEG) | ~50 | ~1500 (base64) |
| `render_crop_1to1` (480×480 JPEG) | ~50 | ~2000 (base64) |
| `append_clips` (batch 38) | ~600 | ~100 |
| `add_transition` (1 para) | ~80 | ~50 |

Pełny montaż 38-scenowego klipu (bez iteracji): ~15-25K tokenów na toole.
Z 2-3 rundami korekcji i 10 thumbnails: ~40-60K tokenów.

---

## Priorytety implementacji

### Faza 1: Fundament (M1-M6 + M8)
Agent umie stworzyć projekt, zaimportować media, zbudować timeline, dodać przejścia, zapisać.
Weryfikuje stan przez tekst (summary). Brak podglądu wizualnego.

### Faza 2: Oczy (M7 + S1 + S2)
Agent umie renderować i dostaje thumbnails + crop 1:1.
Może ocenić wynik wizualnie (za cenę ~2K tokenów per podgląd).

### Faza 3: Iteracja (S3-S7)
Agent umie podmieniać klipy, pracować z audio, cofać zmiany, działać batchowo.
Pełen cykl produkcyjny music video.

### Faza 4: Finezja (C1-C8)
Efekty, tytuły, color grading, compositing, analiza, eksport.
Agent staje się samodzielnym montażystą.
