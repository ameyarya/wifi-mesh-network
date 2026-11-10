# wifi-mesh-network

Plan a Wi-Fi sensing mesh for an apartment before you buy hardware: place ESP32 nodes, sockets and mmWave modules on a top-down plan, and see which parts of the floor are covered and which are blind spots.

Why: Wi-Fi CSI (channel state information) from a few ESP32-S3 boards can detect presence and motion, and with training roughly which room or zone someone is in. How well it works depends on where the nodes go, which walls the links cross, and where a still person is only seen by a mmWave radar. This editor makes that visible.

## Run it

Python 3.9+, no dependencies.

```sh
python3 editor/sim_editor.py                       # your own layout in sim/apartment if you have one, else the example
python3 editor/sim_editor.py --dir examples/apartment --port 8020
```

Open http://localhost:8020/. The server listens on 127.0.0.1 only.

## What the editor does

- Drag furniture, sockets, a router and ESP32 nodes on the plan; every change autosaves.
- **Nodes**: tick *mmWave module* (adds a field-of-view cone) and *Transmitter*. With no transmitter ticked it shows every node pair, as if the nodes took turns.
- **Links** are coloured by how many walls they cross (green 0, amber 1, red 2+).
- **Coverage** (10 cm grid): mmWave moving range, mmWave still range, Wi-Fi sensing zones, and a red overlay on the blind spots, with percentages.
- Warns about nodes with no socket within 0.6 m and about a missing transmitter.

The mmWave defaults come from Seeed's wiki for the XIAO 24 GHz mmWave module: 0.75-6 m detection distance and ±60° ([wiki](https://wiki.seeedstudio.com/mmwave_for_xiao/)). Seeed publishes no separate range for a still person, so the 3 m still range is an assumption: change it to what you measure. Cones are stopped by walls but not by furniture, and vertical angle is not modelled. A Wi-Fi zone is drawn as a band about one first Fresnel zone wide at 2.4 GHz.

## Layout files

They live in the layout folder (`--dir`), are plain JSON, and are never sent anywhere.

| File | What |
|---|---|
| `apartment.json` | size and walls (from `sim/apartment/build_apartment.py` + a floor plan image, or by hand) |
| `furniture.json` | boxes, round things, rugs, carpet, virtual doors |
| `wifi.json` | sockets, router, nodes (`mmwave`, `tx`, `aim` in degrees: 0 = east, 90 = north) |
| `floorplan.png` | optional background image |

`examples/apartment/` is an invented flat to try it on. Your own floor plan, photos and layout files under `sim/apartment/` are gitignored so they cannot be committed by accident; check `git status` before you push.

## The rover simulator

`sim/` is a copy of the MuJoCo apartment/rover simulator from [autonomous-home-rover](https://github.com/ameyarya/autonomous-home-rover/tree/main/sim). Its rover side needs code from that repo (`drive/`, `mac/`), so it does not run on its own here; `sim/apartment/build_apartment.py` is the part that turns a floor plan into `apartment.json`.

## Tests

```sh
cd editor && python3 -m unittest discover
```

More notes on what CSI sensing can and can't do: [docs/wifi-sensing-notes.md](docs/wifi-sensing-notes.md).
