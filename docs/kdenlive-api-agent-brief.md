# Kdenlive API Wrapper — Agent Brief

## Cel projektu

Zbudować Pythonową bibliotekę (`kdenlive_api`) do programowego sterowania projektami Kdenlive, z API wzorowanym na [DaVinci Resolve Scripting API](https://deric.github.io/DaVinciResolve-API-Docs/). Biblioteka operuje na plikach projektowych Kdenlive (XML/MLT) i pozwala automatycznie budować timeline z klatek i klipów wideo generowanych przez AI.

## Kontekst

Produkujemy music video "Chory Świat" (38 scen) w pipeline:
1. **Flux2 Klein** generuje pierwszą klatkę każdej sceny (PNG)
2. **WAN 2.2** generuje 5-sekundowy klip wideo z tej klatki (MP4)
3. Klipy trzeba złożyć w timeline z odpowiednim timingiem, przejściami i synchronizacją z muzyką

Struktura danych projektu:
```
mv-mad-world/
├── img/scenes/scene-{NN}/scene{NN}-final.png   — pierwsza klatka
├── output/video/scene-{NN}.mp4                  — klip wideo (5s, 25fps)
├── script-scenes.md                             — scenariusz z timingiem
└── audio/chory-swiat.wav                        — ścieżka audio
```

## Architektura API

API ma być **kompatybilne w nazewnictwie i strukturze** z DaVinci Resolve API tam, gdzie to możliwe. Kdenlive nie ma runtime API — operujemy na plikach XML projektu (.kdenlive).

### Klasy i metody (wzorowane na Resolve API)

```
Resolve (punkt wejścia)
├── GetProjectManager() → ProjectManager
│
ProjectManager
├── CreateProject(name) → Project
├── LoadProject(filePath) → Project          # wczytaj .kdenlive
├── SaveProject() → Bool
├── GetCurrentProject() → Project
│
Project
├── GetMediaPool() → MediaPool
├── GetTimelineCount() → int
├── GetTimelineByIndex(idx) → Timeline       # 1-based
├── GetCurrentTimeline() → Timeline
├── SetCurrentTimeline(timeline) → Bool
├── GetName() → string
├── SetName(name) → Bool
├── GetSetting(key) → string
├── SetSetting(key, value) → Bool
│
MediaPool
├── GetRootFolder() → Folder
├── AddSubFolder(folder, name) → Folder
├── ImportMedia([filePaths]) → [MediaPoolItem]
├── CreateEmptyTimeline(name) → Timeline
├── AppendToTimeline([clips]) → Bool
├── AppendToTimeline([{clipInfo}]) → Bool    # z startFrame/endFrame
├── CreateTimelineFromClips(name, [clips]) → Timeline
├── GetCurrentFolder() → Folder
├── SetCurrentFolder(folder) → Bool
├── DeleteClips([clips]) → Bool
│
Folder
├── GetName() → string
├── GetClipList() → [MediaPoolItem]
├── GetSubFolderList() → [Folder]
│
MediaPoolItem
├── GetName() → string
├── GetMetadata(key?) → dict
├── SetMetadata(key, value) → Bool
├── GetClipProperty(key?) → dict
├── SetClipProperty(key, value) → Bool
├── GetMediaId() → string
├── AddMarker(frameId, color, name, note, duration) → Bool
├── GetMarkers() → dict
│
Timeline
├── GetName() → string
├── SetName(name) → Bool
├── GetStartFrame() → int
├── GetEndFrame() → int
├── GetTrackCount(trackType) → int           # "video" / "audio"
├── GetItemListInTrack(trackType, idx) → [TimelineItem]
├── AddMarker(frameId, color, name, note, duration) → Bool
├── GetMarkers() → dict
├── DeleteMarkersByColor(color) → Bool
├── DeleteMarkerAtFrame(frame) → Bool
├── GetTrackName(trackType, idx) → string
├── SetTrackName(trackType, idx, name) → Bool
│
TimelineItem
├── GetName() → string
├── GetDuration() → int                      # w klatkach
├── GetStart() → int                         # pozycja na timeline
├── GetEnd() → int
├── GetLeftOffset() → int                    # trim z lewej
├── GetRightOffset() → int                   # trim z prawej
├── GetMediaPoolItem() → MediaPoolItem
├── SetClipColor(color) → Bool
├── GetClipColor() → string
├── AddMarker(frameId, color, name, note, duration) → Bool
├── GetMarkers() → dict
```

### Dodatkowe metody (specyficzne dla Kdenlive, nie z Resolve)

```
Project
├── SetAudioTrack(filePath) → Bool           # ścieżka audio projektu
├── ExportToFile(filePath) → Bool            # zapisz .kdenlive XML

Timeline
├── AddTransition(itemA, itemB, type, duration) → Bool
│   type: "dissolve" | "wipe" | "cut"
│   duration: int (klatki)
├── InsertClipAt(trackType, trackIdx, mediaPoolItem, position) → Bool
│   position: int (klatka na timeline)
├── SetClipDuration(timelineItem, frames) → Bool
├── GetTotalDuration() → int
│
MediaPool
├── ImportMediaFromFolder(dirPath, pattern) → [MediaPoolItem]
│   np. ImportMediaFromFolder("img/scenes/", "scene*-final.png")
```

## User Stories

### US-1: Tworzenie projektu z pliku scenariusza
**Jako** producent music video,
**chcę** uruchomić skrypt, który wczyta `script-scenes.md` i automatycznie stworzy projekt Kdenlive z pustym timeline o odpowiedniej długości (3:30) i ustawieniach (25fps, 1920x1080),
**żeby** nie musieć ręcznie konfigurować projektu od zera.

**Kryteria akceptacji:**
- [ ] Projekt .kdenlive tworzony programowo
- [ ] Poprawne ustawienia: 25fps, 1920x1080, ~3:30 długości
- [ ] Ścieżka audio zaimportowana i umieszczona na tracku audio

---

### US-2: Import mediów z struktury katalogów
**Jako** producent,
**chcę** zaimportować wszystkie finalne klatki (`scene-XX-final.png`) i klipy wideo (`scene-XX.mp4`) do Media Pool,
**żeby** mieć je gotowe do ułożenia na timeline.

**Kryteria akceptacji:**
- [ ] Rekurencyjny import z `img/scenes/` i `output/video/`
- [ ] Pliki zorganizowane w folderach w Media Pool (per scena)
- [ ] Obsługa PNG (jako still frame z domyślnym duration 5s) i MP4

---

### US-3: Automatyczne budowanie timeline
**Jako** producent,
**chcę** z jednego polecenia zbudować timeline, w którym 38 scen jest ułożonych sekwencyjnie z odpowiednimi długościami (z `script-scenes.md`),
**żeby** mieć wstępny montaż do przejrzenia.

**Kryteria akceptacji:**
- [ ] Sceny ułożone w kolejności 1-38 na tracku wideo
- [ ] Każda scena ma długość zgodną z timingiem ze scenariusza
- [ ] Still frames (PNG) rozciągnięte do wymaganej długości
- [ ] Klipy wideo (MP4) przycięte lub powtórzone do wymaganej długości
- [ ] Audio track zsynchronizowany

---

### US-4: Przejścia między scenami
**Jako** producent,
**chcę** definiować przejścia między scenami (hard cut, cross-dissolve, fade) zgodnie z sekcjami utworu,
**żeby** klip miał odpowiednią dynamikę.

**Kryteria akceptacji:**
- [ ] Hard cut (default)
- [ ] Cross-dissolve z konfigurowalnym duration (0.5s–1.5s)
- [ ] Fade in/out na początku i końcu timeline
- [ ] Batch: ustaw przejścia na podstawie mapy `{scene_range: transition_type}`

---

### US-5: Markery sekcji muzycznych
**Jako** producent,
**chcę** mieć markery na timeline odpowiadające sekcjom piosenki (Intro, Verse 1, Build-up, Drop, Chorus, itd.),
**żeby** łatwo nawigować po projekcie.

**Kryteria akceptacji:**
- [ ] Markery z nazwami sekcji i kolorami
- [ ] Markery dodawane z poziomu API
- [ ] Zgodne z formatem markerów Kdenlive

---

### US-6: Podmiana klatki/klipu sceny
**Jako** producent,
**chcę** jednym poleceniem podmienić klip w scenie X na nowy wariant (np. inny seed lub re-generacja),
**żeby** szybko iterować nad poszczególnymi scenami.

**Kryteria akceptacji:**
- [ ] `timeline.ReplaceClip(sceneNumber, newMediaPoolItem)` lub equivalent
- [ ] Zachowanie pozycji, duration i przejść sąsiednich scen
- [ ] Opcja podmiany: only still / only video / both

---

### US-7: Export i roundtrip
**Jako** producent,
**chcę** wczytać projekt .kdenlive (edytowany ręcznie w GUI), zmodyfikować go programowo (np. podmienić scenę) i zapisać z powrotem,
**żeby** API i manualna edycja mogły współistnieć.

**Kryteria akceptacji:**
- [ ] Wczytanie istniejącego .kdenlive bez utraty danych
- [ ] Modyfikacja (dodanie/usunięcie/podmiana klipów)
- [ ] Zapis z zachowaniem efektów, kolorów i ustawień dodanych ręcznie w GUI

---

### US-8: Podgląd timeline w terminalu
**Jako** producent,
**chcę** wypisać tekstowy podgląd timeline (lista scen z ich pozycjami, długościami i przejściami),
**żeby** szybko zweryfikować montaż bez otwierania Kdenlive.

**Kryteria akceptacji:**
- [ ] `timeline.PrintSummary()` wypisuje tabelę scen
- [ ] Kolumny: nr sceny, start timecode, duration, typ przejścia, nazwa pliku
- [ ] Opcja eksportu do markdown

---

## Checklist funkcjonalności

### Warstwa 1: Fundament (MVP)
- [ ] Parser XML projektu Kdenlive (read/write .kdenlive)
- [ ] Klasa `Resolve` jako punkt wejścia
- [ ] Klasa `ProjectManager` — tworzenie i wczytywanie projektów
- [ ] Klasa `Project` — ustawienia (fps, rozdzielczość, nazwa)
- [ ] Klasa `MediaPool` + `Folder` — import plików (PNG, MP4, WAV)
- [ ] Klasa `MediaPoolItem` — metadane, properties
- [ ] Klasa `Timeline` — tworzenie, dodawanie klipów sekwencyjnie
- [ ] Klasa `TimelineItem` — pozycja, duration, trim
- [ ] Export do poprawnego pliku .kdenlive otwieralnego w GUI
- [ ] Testy: roundtrip (create → save → open in Kdenlive → works)

### Warstwa 2: Montaż
- [ ] `AppendToTimeline` z listą klipów
- [ ] `InsertClipAt` — wstawienie klipu na konkretną pozycję
- [ ] `SetClipDuration` — rozciąganie still frames
- [ ] Przejścia: dissolve, wipe, cut
- [ ] Audio track: import i synchronizacja
- [ ] Markery na timeline (sekcje muzyczne)
- [ ] `PrintSummary()` — tekstowy podgląd

### Warstwa 3: Iteracja
- [ ] `ReplaceClip` — podmiana klipu z zachowaniem pozycji
- [ ] Roundtrip: wczytanie projektu edytowanego w GUI, modyfikacja, zapis
- [ ] Batch import: `ImportMediaFromFolder(dir, pattern)`
- [ ] Kolorowanie klipów (color labels per sekcja)
- [ ] Eksport timeline do markdown/CSV

### Warstwa 4: Integracja z pipeline
- [ ] Skrypt `build_timeline.py` — czyta `script-scenes.md`, buduje kompletny projekt
- [ ] Skrypt `replace_scene.py <scene_num> <file>` — podmiana jednej sceny
- [ ] Skrypt `add_transitions.py` — aplikuje mapę przejść
- [ ] Skrypt `preview.py` — wypisuje stan timeline
- [ ] Dokumentacja API (docstrings + README)

## Ograniczenia techniczne

- Kdenlive nie ma runtime API — operujemy wyłącznie na plikach XML (.kdenlive format oparty na MLT)
- Zmiany widoczne po otwarciu/przeładowaniu projektu w GUI
- Format XML może się zmieniać między wersjami Kdenlive — targetujemy v25.x
- Przejścia w Kdenlive to XML elementy `<transition>` w MLT, wymagają precyzyjnego umiejscowienia
- Still frames (PNG) w Kdenlive wymagają jawnego ustawienia duration

## Stack technologiczny

- Python 3.10+
- `lxml` do parsowania/tworzenia XML
- Brak zależności od runtime Kdenlive
- Testy: `pytest` + sample .kdenlive files
