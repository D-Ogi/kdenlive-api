# kdenlive_api -- Dokumentacja

Pythonowa biblioteka do skryptowego sterowania Kdenlive przez D-Bus.
API wzorowane na DaVinci Resolve Scripting API -- skrypty pisane pod Resolve
dzialaja z minimalnymi zmianami.

## Spis tresci

- [Architektura](#architektura)
- [Wymagania](#wymagania)
- [Szybki start](#szybki-start)
- [Hierarchia obiektow](#hierarchia-obiektow)
- [API Reference](#api-reference)
  - [Resolve](#resolve)
  - [ProjectManager](#projectmanager)
  - [Project](#project)
  - [MediaPool](#mediapool)
  - [MediaPoolItem](#mediapoolitem)
  - [Folder](#folder)
  - [MediaStorage](#mediastorage)
  - [Timeline](#timeline)
  - [TimelineItem](#timelineitem)
- [Narzedzia pomocnicze](#narzedzia-pomocnicze)
- [Skrypty CLI](#skrypty-cli)
- [Rozszerzenie C++ Kdenlive (D-Bus)](#rozszerzenie-c-kdenlive-d-bus)
- [Testy](#testy)
- [Ograniczenia](#ograniczenia)
- [Kompatybilnosc z DaVinci Resolve](#kompatybilnosc-z-davinci-resolve)

---

## Architektura

```
  Skrypt Python
       |
   Resolve (punkt wejscia)
       |
   ProjectManager / Project / MediaPool / Timeline  (OOP wrapper)
       |
   KdenliveDBus  (niskopoziomowy klient)
       |
   D-Bus (org.kde.kdenlive.scripting)
       |
   Kdenlive (zmodyfikowany build z Q_SCRIPTABLE metodami)
```

Biblioteka sklada sie z dwoch warstw:

1. **KdenliveDBus** (`dbus_client.py`) -- niskopoziomowy proxy wywolujacy metody
   D-Bus na interfejsie `org.kde.kdenlive.scripting`. Automatycznie wykrywa
   backend: `pydbus` (Linux), lub fallback na `qdbus`/`gdbus` przez subprocess.

2. **OOP API** (`resolve.py`, `project.py`, `timeline.py`, ...) -- obiekty
   o nazwach i sygnaturach zgodnych z DaVinci Resolve Scripting API.
   Kazdy obiekt wewnetrznie deleguje do `KdenliveDBus`.

---

## Wymagania

| Komponent | Wymaganie |
|-----------|-----------|
| Python | 3.10+ |
| Kdenlive | Zmodyfikowany build z interfejsem `org.kde.kdenlive.scripting` |
| D-Bus | `pydbus` (Linux) lub `qdbus`/`gdbus` w PATH |
| System | Linux (natywny D-Bus) lub Windows (wymaga konfiguracji) |

Instalacja zaleznosci:

```bash
pip install -r requirements.txt
```

```
pydbus>=0.6.0        # Linux only
PyGObject>=3.42.0    # Linux only
pytest>=7.0
```

---

## Szybki start

```python
from kdenlive_api import Resolve

# Polacz sie z dzialajacym Kdenlive
resolve = Resolve()
pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()

# Info o projekcie
print(project.GetName())          # "Moj Projekt"
print(project.GetFps())           # 25.0
print(project.GetResolution())    # (1536, 864)

# Import klipu do bina
pool = project.GetMediaPool()
clips = pool.ImportMedia(["/sciezka/do/klip.mp4"])
print(clips[0].GetName())         # "klip.mp4"

# Wstaw na timeline
timeline = project.GetCurrentTimeline()
item = timeline.InsertClip(clips[0].bin_id, track_id=0, position=0)
print(item.GetDuration())         # 125

# Dodaj przejscie miedzy dwoma klipami
items = timeline.GetItemListInTrack("video", 1)
timeline.AddTransition(items[0], items[1], duration=13)

# Dodaj marker
timeline.AddMarker(frame=0, color="Blue", name="Start")

# Seek i odtwarzanie
timeline.Seek(0)
timeline.Play()
```

---

## Hierarchia obiektow

```
Resolve
├── GetProjectManager() --> ProjectManager
│   ├── GetCurrentProject() --> Project
│   │   ├── GetMediaPool() --> MediaPool
│   │   │   ├── GetRootFolder() --> Folder
│   │   │   │   └── GetClipList() --> [MediaPoolItem, ...]
│   │   │   ├── ImportMedia(paths) --> [MediaPoolItem, ...]
│   │   │   └── AppendToTimeline(clips) --> bool | [int, ...]
│   │   └── GetCurrentTimeline() --> Timeline
│   │       ├── GetItemListInTrack(type, idx) --> [TimelineItem, ...]
│   │       ├── InsertClip(bin_id, track, pos) --> TimelineItem
│   │       ├── AddTransition(a, b, dur) --> bool
│   │       └── AddMarker(frame, color, name) --> bool
│   ├── CreateProject(name) --> Project
│   └── LoadProject(path) --> Project
└── GetMediaStorage() --> MediaStorage
    └── AddItemListToMediaPool(items) --> [MediaPoolItem, ...]
```

---

## API Reference

### Resolve

Punkt wejscia. Tworzy polaczenie D-Bus z Kdenlive.

```python
from kdenlive_api import Resolve
resolve = Resolve()
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetProjectManager()` | `ProjectManager` | Menedzer projektow |
| `GetMediaStorage()` | `MediaStorage` | Dostep do systemu plikow / import mediow |
| `OpenPage(page_name)` | `bool` | No-op (Kdenlive ma jedna strone) |
| `GetCurrentPage()` | `str` | Zawsze `"edit"` |
| `Fusion()` | `None` | Stub -- Kdenlive nie ma Fusion |
| `GetProductName()` | `str` | `"Kdenlive"` |
| `GetVersion()` | `list` | `[25, 0, 0, 0, ""]` |
| `GetVersionString()` | `str` | `"25.0.0"` |
| `GetCurrentLayoutPreset()` | `str` | Stub -- `""` |
| `LoadLayoutPreset(name)` | `bool` | Stub -- `True` |
| `SaveLayoutPreset(name)` | `bool` | Stub -- `True` |
| `UpdateLayoutPreset(name)` | `bool` | Stub -- `True` |
| `DeleteLayoutPreset(name)` | `bool` | Stub -- `True` |
| `ExportLayoutPreset(name, path)` | `bool` | Stub -- `True` |
| `ImportLayoutPreset(path, name)` | `bool` | Stub -- `True` |
| `Quit()` | `None` | Zamyka Kdenlive |

**Stale eksportu** (atrybuty klasy):

| Stala | Wartosc | Opis |
|-------|---------|------|
| `EXPORT_AAF` | 0 | Advanced Authoring Format |
| `EXPORT_DRT` | 1 | DaVinci Resolve Timeline |
| `EXPORT_EDL` | 2 | Edit Decision List |
| `EXPORT_FCP_7_XML` | 3 | Final Cut Pro 7 XML |
| `EXPORT_FCPXML_1_3` .. `1_10` | 4--11 | FCPXML wersje |
| `EXPORT_HDL` | 12 | HDL |
| `EXPORT_TEXT_CSV` | 13 | CSV |
| `EXPORT_TEXT_TAB` | 14 | Tab-separated |
| `EXPORT_DOLBY_VISION_VER_2_9` | 15 | Dolby Vision 2.9 |
| `EXPORT_DOLBY_VISION_VER_4_0` | 16 | Dolby Vision 4.0 |
| `EXPORT_OTIO` | 17 | OpenTimelineIO |

---

### ProjectManager

Zarzadzanie projektami Kdenlive.

```python
pm = resolve.GetProjectManager()
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `CreateProject(name)` | `Project \| None` | Nowy projekt |
| `LoadProject(file_path)` | `Project \| None` | Otworz plik `.kdenlive` |
| `SaveProject()` | `bool` | Zapisz biezacy projekt |
| `GetCurrentProject()` | `Project` | Aktualnie otwarty projekt |
| `GetProjectListInCurrentFolder()` | `list[str]` | Lista projektow (zwraca `[nazwa]`) |
| `GetFolderListInCurrentFolder()` | `list[str]` | Zawsze `[]` |
| `OpenFolder(name)` | `bool` | Stub -- `False` |
| `GotoParentFolder()` | `bool` | Stub -- `True` |
| `GotoRootFolder()` | `bool` | Stub -- `True` |
| `CloseProject(project)` | `bool` | Stub -- `True` |

> Kdenlive nie ma bazy danych projektow jak Resolve. Metody nawigacji po
> folderach to stuby zapewniajace kompatybilnosc API.

---

### Project

Reprezentuje otwarty projekt Kdenlive.

```python
project = pm.GetCurrentProject()
```

#### Podstawowe

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetName()` | `str` | Nazwa projektu |
| `SetName(name)` | `bool` | Ustaw nazwe |
| `GetMediaPool()` | `MediaPool` | Bin z mediami |
| `GetCurrentTimeline()` | `Timeline` | Aktywny timeline |
| `GetFps()` | `float` | Klatki na sekunde (np. `25.0`) |
| `GetResolution()` | `tuple[int, int]` | `(width, height)` np. `(1536, 864)` |

#### Ustawienia

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetSetting(key)` | `str` | Pobierz wlasciwosc projektu |
| `SetSetting(key, value)` | `bool` | Ustaw wlasciwosc |
| `GetProjectPath()` | `str` | Sciezka pliku `.kdenlive` |

`GetSetting()` mapuje klucze Resolve na Kdenlive:

| Klucz Resolve | Mapowanie |
|----------------|-----------|
| `timelineFrameRate` | `get_project_fps()` |
| `timelineResolutionWidth` | `get_project_resolution_width()` |
| `timelineResolutionHeight` | `get_project_resolution_height()` |

#### Zapis

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `Save()` | `bool` | Zapisz projekt |
| `SaveAs(file_path)` | `bool` | Zapisz jako |

#### Timeline management

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetTimelineCount()` | `int` | Zawsze `1` (Kdenlive = 1 timeline) |
| `GetTimelineByIndex(index)` | `Timeline \| None` | Index 1 zwraca timeline |
| `SetCurrentTimeline(tl)` | `bool` | No-op -- `True` |
| `GetCurrentVideoItem()` | `None` | Stub |

#### Render (stuby kompatybilnosci)

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `LoadRenderPreset(name)` | `bool` | Stub |
| `SetCurrentRenderFormatAndCodec(fmt, codec)` | `bool` | Stub |
| `SetRenderSettings(dict)` | `bool` | Stub |
| `GetRenderSettings()` | `dict` | Stub -- `{}` |
| `AddRenderJob()` | `str` | Stub -- `"job_1"` |
| `StartRendering(*job_ids)` | `bool` | Wywoluje `scriptRender` |
| `IsRenderingInProgress()` | `bool` | Stub -- `False` |
| `GetRenderJobList()` | `list[dict]` | Stub -- `[]` |
| `GetRenderJobStatus(job_id)` | `dict` | Stub -- `{"JobStatus": "Complete"}` |
| `DeleteAllRenderJobs()` | `bool` | Stub |
| `DeleteRenderJob(job_id)` | `bool` | Stub |

---

### MediaPool

Zarzadza binem (media pool) projektu.

```python
pool = project.GetMediaPool()
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetRootFolder()` | `Folder` | Folder glowny bina |
| `AddSubFolder(parent, name)` | `Folder \| None` | Nowy podfolder |
| `SetCurrentFolder(folder)` | `bool` | Ustaw biezacy folder |
| `GetCurrentFolder()` | `Folder` | Biezacy folder |
| `ImportMedia(paths, folder)` | `list[MediaPoolItem]` | Import plikow |
| `ImportMediaFromFolder(dir, pattern)` | `list[MediaPoolItem]` | Import z katalogu wg wzorca |
| `GetAllClips()` | `list[MediaPoolItem]` | Wszystkie klipy w binie |
| `GetClipById(bin_id)` | `MediaPoolItem` | Klip po ID |
| `CreateEmptyTimeline(name)` | `Timeline` | Zwraca biezacy timeline |
| `AppendToTimeline(clips, track_id, start_pos)` | `list[int] \| bool` | Wstaw klipy na timeline |
| `DeleteClips(clips)` | `bool` | Usun klipy z bina |
| `MoveClips(clips, target_folder)` | `bool` | Stub -- `True` |

#### AppendToTimeline -- konwencje wywolania

`AppendToTimeline` obsluguje wiele formatow (kompatybilnosc z Resolve):

```python
# 1. Pojedynczy klip --> bool
pool.AppendToTimeline(clip)

# 2. Lista klipow --> list[int] (timeline clip IDs)
pool.AppendToTimeline([clip1, clip2, clip3])

# 3. Lista subclip dicts --> list[int]
pool.AppendToTimeline([{
    "mediaPoolItem": clip,
    "startFrame": 0,
    "endFrame": 50
}])

# 4. Lista z kluczem "media" (sciezka) --> importuje i wstawia
pool.AppendToTimeline([{"media": "/path/to/file.mp4"}])

# 5. Opcjonalny track_id i start_position
pool.AppendToTimeline(clips, track_id=0, start_position=100)
```

---

### MediaPoolItem

Reprezentuje klip w binie.

```python
clips = pool.ImportMedia(["/path/to/video.mp4"])
clip = clips[0]
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetName()` | `str` | Nazwa klipu |
| `GetDuration()` | `int` | Dlugosc w klatkach |
| `GetMediaId()` | `str` | ID w binie (= `bin_id`) |
| `GetClipProperty(key)` | `str` | Wartosc wlasciwosci po kluczu |
| `GetClipProperty()` | `dict` | Bez argumentu: caly slownik wlasciwosci |
| `Delete()` | `bool` | Usun z bina |

Wlasciwosci zwracane przez `GetClipProperty()` (bez argumentu):

| Klucz | Opis |
|-------|------|
| `name` | Nazwa pliku |
| `path` / `url` | Sciezka do pliku |
| `duration` | Dlugosc |
| `type` | Typ klipu (0=video, 1=audio) |
| `File Name` | Alias Resolve dla `name` |
| `File Path` | Alias Resolve dla `path`/`url` |
| `Frames` | Alias Resolve dla `duration` |
| `Video Codec` | Resolve-style codec info |

#### Markery klipu

```python
clip.AddMarker(10, "Red", "Start", note="Intro starts", duration=1, custom_data="cd1")
markers = clip.GetMarkers()  # {10: {"color": "Red", "name": "Start", ...}}
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `AddMarker(frame, color, name, note, duration, custom_data)` | `bool` | Dodaj marker |
| `GetMarkers()` | `dict[int, dict]` | Wszystkie markery `{frame: {...}}` |
| `GetMarkerByCustomData(data)` | `dict` | Znajdz marker po custom data |
| `UpdateMarkerCustomData(frame, data)` | `bool` | Aktualizuj custom data |
| `GetMarkerCustomData(frame)` | `str` | Pobierz custom data |
| `DeleteMarkerAtFrame(frame)` | `bool` | Usun marker |
| `DeleteMarkersByColor(color)` | `bool` | Usun markery po kolorze |
| `DeleteMarkerByCustomData(data)` | `bool` | Usun marker po custom data |

#### Stuby (Resolve-only)

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetFusionCompCount()` | `0` | Fusion (brak w Kdenlive) |
| `AddFusionComp()` | `False` | Fusion |
| `GetFusionCompByIndex(idx)` | `None` | Fusion |
| `GetFusionCompNameList()` | `[]` | Fusion |
| `SetClipColor(color)` | `True` | Stub |
| `GetClipColor()` | `""` | Stub |

---

### Folder

Folder w binie.

```python
root = pool.GetRootFolder()
clips = root.GetClipList()
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetName()` | `str` | Nazwa folderu |
| `GetClipList()` | `list[MediaPoolItem]` | Klipy w folderze |
| `GetSubFolderList()` | `list[Folder]` | Podfoldery (zawsze `[]`) |
| `GetIsFolderStale()` | `bool` | Zawsze `False` |

Wlasciwosc: `folder_id` -- identyfikator folderu.

---

### MediaStorage

Dostep do systemu plikow i import mediow. Odpowiednik Resolve MediaStorage.

```python
storage = resolve.GetMediaStorage()
clips = storage.AddItemListToMediaPool("/path/to/folder/")
```

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetMountedVolumeList()` | `list[str]` | Zamontowane woluminy |
| `GetSubFolderList(path)` | `list[str]` | Podkatalogi |
| `GetFileList(path)` | `list[str]` | Pliki w katalogu |
| `AddItemListToMediaPool(items)` | `list[MediaPoolItem]` | Import do bina |
| `RevealInStorage(path)` | `bool` | Stub -- `True` |

`AddItemListToMediaPool` przyjmuje:

| Format | Przyklad |
|--------|----------|
| Sciezka do katalogu | `"/media/clips/"` -- importuje wszystkie pliki medialne |
| Sciezka do pliku | `"/media/clip.mp4"` |
| Lista sciezek | `["/a.mp4", "/b.mp4"]` |
| Lista subclip dicts | `[{"media": "/a.mp4", "startFrame": 0, "endFrame": 50}]` |

Rozpoznawane rozszerzenia: `.mp4`, `.mov`, `.avi`, `.mkv`, `.mxf`, `.webm`,
`.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.png`, `.jpg`, `.jpeg`, `.tiff`,
`.bmp`, `.exr`.

---

### Timeline

Aktywny timeline Kdenlive.

```python
timeline = project.GetCurrentTimeline()
```

#### Informacje

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetName()` | `str` | Nazwa timeline (= nazwa projektu) |
| `SetName(name)` | `bool` | Stub -- `True` |
| `GetTrackCount(track_type)` | `int` | Liczba trackow danego typu |
| `GetTrackInfo(index)` | `dict` | Info o tracku |
| `GetAllTracksInfo()` | `list[dict]` | Info o wszystkich trackach |
| `GetTotalDuration()` | `int` | Calkowita dlugosc w klatkach |
| `GetStartFrame()` | `int` | Zawsze `0` |
| `GetEndFrame()` | `int` | = `GetTotalDuration()` |
| `PrintSummary()` | `None` | Wypisz podsumowanie na stdout |

`track_type`: `"video"`, `"audio"`, lub `"subtitle"` (subtitle zawsze zwraca 0).

#### Zarzadzanie trackami

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `AddTrack(name, audio)` | `int` | Dodaj track, zwraca track ID |
| `GetItemListInTrack(type, idx)` | `list[TimelineItem]` | Klipy na tracku |

`GetItemListInTrack` przyjmuje **1-based** indeks (konwencja Resolve):

```python
# Track 1 (pierwszy video track)
clips = timeline.GetItemListInTrack("video", 1)

# Index 0 tez dziala (traktowany jako 0-based)
clips = timeline.GetItemListInTrack("video", 0)
```

#### Wstawianie klipow

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `InsertClip(bin_id, track_id, position)` | `TimelineItem \| None` | Wstaw klip |
| `InsertClipAt(type, idx, item, pos)` | `TimelineItem \| None` | Wstaw po typie tracku i indeksie |
| `InsertClipsSequentially(ids, track_id, start)` | `list[TimelineItem]` | Wstaw wiele sekwencyjnie |

```python
# Wstaw klip na pozycji 0
item = timeline.InsertClip(clip.bin_id, track_id=0, position=0)

# Wstaw po typie tracku (Resolve-style)
item = timeline.InsertClipAt("video", 1, media_pool_item, position=100)

# Wstaw wiele klipow po sobie
items = timeline.InsertClipsSequentially(
    ["bin_id_1", "bin_id_2", "bin_id_3"],
    track_id=0,
    start_position=0
)
```

#### Przejscia (transitions)

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `AddTransition(item_a, item_b, duration)` | `bool` | Mix miedzy sasiednimi klipami |
| `AddComposition(id, track_id, pos, dur)` | `int` | Kompozycja miedzy trackami |
| `RemoveMix(item)` | `bool` | Usun mix z klipu |

```python
# Standardowy cross-dissolve miedzy klipami
timeline.AddTransition(items[0], items[1], duration=13)  # 13 klatek = 0.5s

# Kompozycja (cross-track)
comp_id = timeline.AddComposition("luma", track_id=0, position=100, duration=25)
```

Domyslna dlugosc przejscia: `DEFAULT_MIX_DURATION = 13` klatek (0.52s przy 25fps).

#### Markery / Guides

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `AddMarker(frame, color, name, note, duration)` | `bool` | Dodaj marker/guide |
| `GetMarkers()` | `dict[int, dict]` | Wszystkie markery |
| `DeleteMarker(frame)` | `bool` | Usun marker |
| `DeleteMarkerAtFrame(frame)` | `bool` | Alias |
| `DeleteMarkersByColor(color)` | `bool` | Usun po kolorze |

`color` moze byc:
- **String** (Resolve-style): `"Red"`, `"Blue"`, `"Green"`, `"Yellow"`, `"Orange"`, `"Purple"`
- **Int** (Kdenlive category): `0`=Purple, `1`=Blue, `2`=Green, `3`=Yellow, `4`=Orange, `5`=Red

Mapowanie dodatkowych kolorow Resolve:

| Nazwa Resolve | Kategoria Kdenlive |
|---------------|-------------------|
| Fuchsia, Lavender | Purple (0) |
| Cyan, Sky | Blue (1) |
| Mint | Green (2) |
| Lemon, Cream | Yellow (3) |
| Sand, Cocoa | Orange (4) |
| Rose | Red (5) |

```python
# Dodaj marker z kolorem string (Resolve-style)
timeline.AddMarker(0, "Blue", "Intro", note="Poczatek intro")

# Dodaj marker z kategoria int (Kdenlive-native)
timeline.AddMarker(125, 2, "Scene 2")  # 2 = Green

# Pobierz markery -- format Resolve-kompatybilny
markers = timeline.GetMarkers()
# {0: {"color": "Blue", "duration": 1, "note": "...", "name": "...",
#       "customData": "", "comment": "...", "category": 1}}
```

#### Odtwarzanie

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `Seek(frame)` | `None` | Przesun glowice |
| `GetPosition()` | `int` | Biezaca pozycja |
| `Play()` | `None` | Odtwarzaj |
| `Pause()` | `None` | Pauza |

#### Stuby (Resolve-only)

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `ApplyGradeFromDRX(path, mode, clips)` | `True` | DRX color grading (brak w Kdenlive) |
| `GetCurrentClipThumbnailImage()` | `None` | Miniaturka klipu |
| `Export(path, type, subtype)` | `True` | Export timeline |

---

### TimelineItem

Klip na timeline.

```python
item = timeline.InsertClip(clip.bin_id, 0, 0)
```

#### Informacje

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `GetName()` | `str` | Nazwa klipu |
| `GetDuration()` | `int` | Dlugosc w klatkach |
| `GetStart()` | `int` | Pozycja startowa (klatka) |
| `GetEnd()` | `int` | Pozycja koncowa (start + duration) |
| `GetTrackId()` | `int` | ID tracku |
| `GetMediaPoolItem()` | `MediaPoolItem \| None` | Klip zrodlowy z bina |
| `GetLeftOffset()` | `int` | In-point klipu |
| `GetRightOffset()` | `int` | Zawsze `0` |

#### Operacje

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `SetDuration(frames, from_right)` | `int` | Zmien dlugosc, zwraca faktyczna |
| `Move(track_id, position)` | `bool` | Przesun klip |
| `Delete()` | `bool` | Usun z timeline |
| `Cut(position)` | `bool` | Przytnij w punkcie |

```python
# Zmien dlugosc klipu na 100 klatek
actual = item.SetDuration(100, from_right=True)

# Przesun klip na inny track
item.Move(track_id=1, position=200)

# Przytnij klip w pozycji 50
item.Cut(position=50)
```

#### Stuby

| Metoda | Zwraca | Opis |
|--------|--------|------|
| `SetClipColor(color)` | `True` | Stub |
| `GetClipColor()` | `""` | Stub |
| `GetFusionCompCount()` | `0` | Fusion |
| `AddFusionComp()` | `False` | Fusion |
| `GetFusionCompByIndex(idx)` | `None` | Fusion |
| `GetFusionCompNameList()` | `[]` | Fusion |

Wlasciwosc: `clip_id` -- identyfikator klipu na timeline.

---

## Narzedzia pomocnicze

Modul `kdenlive_api.utils` zawiera helpery:

### Timecode

```python
from kdenlive_api.utils import frames_to_timecode, timecode_to_frames

frames_to_timecode(125, fps=25.0)     # "00:00:05:00"
frames_to_timecode(3813, fps=25.0)    # "00:02:32:13"

timecode_to_frames("00:00:05:00", fps=25.0)   # 125
timecode_to_frames("00:02:32:13", fps=25.0)   # 3813
```

| Funkcja | Opis |
|---------|------|
| `frames_to_timecode(frames, fps)` | Klatki --> `HH:MM:SS:FF` |
| `timecode_to_frames(timecode, fps)` | `HH:MM:SS:FF` --> klatki |
| `seconds_to_frames(seconds, fps)` | Sekundy --> klatki |
| `frames_to_seconds(frames, fps)` | Klatki --> sekundy |

### Parser scenariusza

```python
from kdenlive_api.utils import parse_script_scenes

scenes = parse_script_scenes("script-scenes.md")
# [{"number": 1, "title": "Pustka poranna", "section": "INTRO",
#   "kadr": "...", "poza": "...", "nastroj": "...", "ambient": "...", "kamera": "..."}, ...]
```

| Funkcja | Opis |
|---------|------|
| `parse_script_scenes(path)` | Parsuj `script-scenes.md` na liste scen |
| `find_scene_video(dir, num, variant)` | Znajdz plik video per scena (np. `scene05-A.mp4`) |
| `collect_scene_videos(dir, num_scenes, variant)` | Lista sciezek dla 38 scen |

---

## Skrypty CLI

Cztery gotowe skrypty w `scripts/`:

### build_timeline.py

Buduje kompletny timeline 38-scenowy z muzyka, przejsciami i markerami.

```bash
python scripts/build_timeline.py \
    --video-dir output/video \
    --audio audio/chory-swiat.mp3 \
    --variant A \
    --transition-frames 13 \
    --script script-scenes.md
```

| Argument | Domyslny | Opis |
|----------|----------|------|
| `--video-dir` | `output/video` | Katalog z klipami scen |
| `--audio` | brak | Sciezka do pliku audio |
| `--variant` | `A` | Wariant sceny (`A` lub `B`) |
| `--transition-frames` | `13` | Dlugosc przejscia (0 = bez) |
| `--script` | `script-scenes.md` | Scenariusz do parsowania |

Pipeline:
1. Polacz z Kdenlive
2. Parsuj scenariusz
3. Znajdz pliki video (`scene01-A*.mp4` ... `scene38-A*.mp4`)
4. Utworz folder w binie, importuj klipy
5. Importuj audio
6. Wstaw klipy sekwencyjnie na video track
7. Wstaw audio na audio track
8. Dodaj cross-dissolve miedzy klipami
9. Dodaj guide markery per scena (kolor wg sekcji: Blue=Intro, Green=Verse, Purple=Drop)
10. Wypisz podsumowanie

### replace_scene.py

Podmien pojedyncza scene na timeline.

```bash
python scripts/replace_scene.py --scene 5 --file output/video/scene05-B-seed3.mp4
```

| Argument | Opis |
|----------|------|
| `--scene` | Numer sceny (1-38) -- wymagany |
| `--file` | Sciezka do nowego pliku -- wymagany |
| `--track` | Indeks video tracku (domyslnie 0) |

Pipeline: znajdz klip --> zapamietaj pozycje/dlugosc --> importuj nowy --> usun stary --> wstaw nowy w tym samym miejscu --> dopasuj dlugosc.

### add_transitions.py

Dodaj (lub ponownie zastosuj) przejscia miedzy wszystkimi klipami na tracku.

```bash
python scripts/add_transitions.py --duration 13 --track 0
```

| Argument | Domyslny | Opis |
|----------|----------|------|
| `--duration` | `13` | Dlugosc przejscia w klatkach |
| `--track` | `0` | Indeks video tracku |

### preview.py

Podglad -- przeskocz do sceny i odtwarzaj.

```bash
python scripts/preview.py --scene 12
python scripts/preview.py --frame 500
python scripts/preview.py --no-play
```

| Argument | Opis |
|----------|------|
| `--scene` | Numer sceny (1-38) |
| `--frame` | Numer klatki |
| `--track` | Indeks video tracku (domyslnie 0) |
| `--no-play` | Nie rozpoczynaj odtwarzania |

Bez argumentow: wypisz biezaca pozycje glowicy.

---

## Rozszerzenie C++ Kdenlive (D-Bus)

Zrodla w `reference/kdenlive/src/`. Trzy zmodyfikowane pliki:

### org.kdenlive.MainWindow.xml

Nowy interfejs D-Bus `org.kde.kdenlive.scripting` z 44 metodami.
Obok istniejacego `org.kde.kdenlive.rendering`.

### mainwindow.h

~40 nowych deklaracji `Q_SCRIPTABLE` w sekcji `public Q_SLOTS`:

```cpp
// Przyklad deklaracji
Q_SCRIPTABLE QStringList scriptImportMedia(const QStringList &filePaths,
                                           const QString &folderId);
Q_SCRIPTABLE int scriptInsertClip(const QString &binClipId,
                                  int trackId, int position);
Q_SCRIPTABLE QVariantMap scriptGetClipInfo(int clipId);
```

### mainwindow.cpp

Implementacja ~400 linii nowego kodu C++. Kazda metoda deleguje do
wewnetrznych klas Kdenlive:

| Operacja | Klasa wewnetrzna |
|----------|-----------------|
| Import mediow | `ClipCreator::createClipFromFile()`, `pCore->projectItemModel()` |
| Wstawianie na timeline | `timeline->requestClipInsertion()` |
| Przesuwanie klipow | `timeline->requestClipMove()` |
| Zmiana rozmiaru | `timeline->requestItemResize()` |
| Usuwanie | `timeline->requestItemDeletion()` |
| Mixy (przejscia) | `timeline->requestClipMix()` |
| Markery | `getGuideModel()->addMarker()` / `removeMarker()` |
| Odtwarzanie | `m_projectMonitor->slotSeek()`, `pCore->monitorManager()` |

### Weryfikacja D-Bus

Po zbudowaniu zmodyfikowanego Kdenlive, smoke test:

```bash
# Sprawdz czy interfejs jest widoczny
qdbus org.kde.kdenlive /MainWindow org.kde.kdenlive.scripting.scriptGetProjectName

# Lista wszystkich metod
qdbus org.kde.kdenlive /MainWindow | grep script
```

---

## Testy

81 testow (78 unit + 3 integration skipped).

```bash
# Uruchom wszystkie testy
python -m pytest tests/ -v

# Tylko testy kompatybilnosci Resolve
python -m pytest tests/test_resolve_compat.py -v

# Testy integracyjne (wymaga uruchomionego Kdenlive)
python -m pytest tests/ --run-live
```

| Plik | Testow | Zakres |
|------|--------|--------|
| `test_dbus_client.py` | 2 | Stale, detekcja backendu |
| `test_project.py` | 9 | Project, ProjectManager |
| `test_media_pool.py` | 7 | MediaPool, Folder, MediaPoolItem |
| `test_timeline.py` | 9 | Timeline, TimelineItem, tracki |
| `test_transitions.py` | 3 | Mix, composition, remove |
| `test_markers.py` | 4 | Guides: add/get/delete |
| `test_resolve_compat.py` | 47 | Pelna kompatybilnosc z Resolve API |
| `test_integration.py` | 3 | Live testy (skipped domyslnie) |

Testy uzywaja `MockDBus` (`conftest.py`) -- pelna symulacja D-Bus bez
uruchomionego Kdenlive.

---

## Ograniczenia

| Ograniczenie | Opis |
|-------------|------|
| **Runtime only** | Kdenlive musi byc uruchomione (nie ma trybu offline/headless) |
| **Linux D-Bus** | Natywne wsparcie na Linux; Windows wymaga dodatkowej konfiguracji |
| **Single timeline** | Kdenlive ma jeden aktywny timeline (nie wiele jak Resolve) |
| **Synchroniczne** | Wywolania D-Bus sa blokujace |
| **Brak Fusion** | Fusion/compositing niedostepne (Resolve-only) |
| **Brak clip color** | `SetClipColor`/`GetClipColor` to stuby |
| **Brak subfolder enumeration** | D-Bus nie eksponuje hierarchii folderow bina |
| **Brak render pipeline** | Metody renderowania to stuby (poza `StartRendering`) |
| **Markery klipu** | Markery na `MediaPoolItem` sa in-memory; nie persistuja w projekcie |

---

## Kompatybilnosc z DaVinci Resolve

Biblioteka pokrywa API z 11 oficjalnych przykladow Resolve:

| Przyklad Resolve | Status |
|-----------------|--------|
| `python_get_resolve.py` | Zaimplementowany -- `from kdenlive_api import Resolve` |
| `1_sorted_timeline.py` | Dziala -- `GetItemListInTrack`, `GetMediaPoolItem`, `GetClipProperty` |
| `2_compositions.py` | Dziala -- `AddComposition`, stale exportu |
| `3_grade_and_export.py` | Stuby -- `ApplyGradeFromDRX`, `Export` zwracaja `True` |
| `4_project_setup.py` | Dziala -- `CreateProject`, `SetSetting`, `ImportMedia` |
| `5_markers.py` | Dziala -- `AddMarker`, `GetMarkers`, `DeleteMarkersByColor` |
| `6_media_management.py` | Dziala -- `GetMediaStorage`, `AddItemListToMediaPool` |
| `7_render_settings.py` | Stuby -- `SetRenderSettings`, `AddRenderJob`, `StartRendering` |
| `8_timeline_items.py` | Dziala -- `GetItemListInTrack`, `GetStart/End/Duration` |
| `9_project_manager.py` | Dziala -- `GetProjectListInCurrentFolder`, `GotoRootFolder` |
| `10_fusion.py` | Stuby -- `Fusion()` zwraca `None`, `GetFusionComp*` zwracaja `0`/`[]` |

### Wzorzec migracji skryptu z Resolve

```python
# Resolve:
import DaVinciResolveScript as dvr
resolve = dvr.scriptapp("Resolve")

# Kdenlive (zamiennik):
from kdenlive_api import Resolve
resolve = Resolve()

# Reszta kodu jest identyczna:
pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()
timeline = project.GetCurrentTimeline()
# ...
```

Jedyne roznice to import i brak featury Fusion/DRX/ColorGrading.
Caly lancuch `Resolve -> ProjectManager -> Project -> MediaPool -> Timeline`
dziala identycznie.
