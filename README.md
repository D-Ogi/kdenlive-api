# kdenlive-api

DaVinci Resolve-compatible Python scripting API for Kdenlive via D-Bus.

Scripts written for the Resolve API work with minimal changes. The library communicates with a [modified Kdenlive build](https://github.com/D-Ogi/kdenlive) that exposes `Q_SCRIPTABLE` methods over D-Bus (`org.kde.kdenlive.scripting`).

## Quick start

```bash
pip install -r requirements.txt
```

```python
from kdenlive_api import Resolve

resolve = Resolve()
pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()
timeline = project.GetCurrentTimeline()

# Import media and build a timeline
pool = project.GetMediaPool()
clips = pool.ImportMedia(["scene01.mp4", "scene02.mp4"])
pool.AppendToTimeline(clips)
```

## API hierarchy

```
Resolve
└── ProjectManager
    └── Project
        ├── MediaPool
        │   ├── Folder
        │   └── MediaPoolItem
        ├── MediaStorage
        └── Timeline
            └── TimelineItem
```

All class and method names follow the DaVinci Resolve Scripting API naming conventions. Kdenlive-specific extensions (transitions, clip insertion, audio track) are added on top.

## CLI scripts

| Script | Description |
|--------|-------------|
| `scripts/build_timeline.py` | Reads a scene script and builds a complete Kdenlive project |
| `scripts/replace_scene.py` | Swaps a single scene clip on the timeline |
| `scripts/add_transitions.py` | Applies a transition map (dissolve, wipe, cut) between scenes |
| `scripts/preview.py` | Prints a text summary of the current timeline |

## Requirements

- Python 3.10+
- Linux (D-Bus transport requires `pydbus` and `PyGObject`)
- [Modified Kdenlive build](https://github.com/D-Ogi/kdenlive) with D-Bus scripting support

## Documentation

See the source code and docstrings for API documentation.

## Tests

```bash
pytest tests/
```

81 unit tests using a MockDBus backend — no running Kdenlive instance needed.

## License

MIT
