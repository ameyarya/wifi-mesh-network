# Wi-Fi sensing with ESP32: what to expect

**Works well**: presence and motion per room or zone, once you add more links crossing the space.
**Works with training**: which room / half of a room. Record labelled CSI over several days in your own apartment and train a small classifier; keep nodes and the Wi-Fi channel fixed, and label doors and rolling chairs as states.
**Doesn't work well**: precise x/y position, several people at once, and a person sitting still (breathing is detectable only in quiet, short-range setups). For still presence add a mmWave radar aimed at the bed, sofa or desk.

## Setup

- Boards: ESP32-S3 (C3/C6 also support CSI). Prefer a u.FL connector with an external antenna. Use one model throughout.
- One node (or the router) transmits at 20-100 packets/s; the others record CSI and stream it to a hub over UDP/MQTT. Nodes can take turns transmitting so every pair becomes a link.
- A stock router does not expose CSI: it can only be a transmitter for the nodes.
- Mount nodes at about 1.2-1.5 m, each within reach of a USB power adapter. Lock the router's channel.
- Count: about one node per room, plus one for rooms larger than ~4x4 m. A small 1-bedroom is typically 5-7 nodes.

## Why breathing detection doesn't imply precise location

Breathing is a 5 mm chest movement at 0.2-0.4 Hz: one periodic disturbance on one link. Location needs the whole multipath pattern mapped to a position, which depends on exact geometry and breaks when furniture or nodes move. A handful of nodes give far fewer links than there are positions to tell apart, so expect zones, not coordinates.

## Related

- Espressif `esp-csi`, ESP32-CSI-Tool, ESPectre (Home Assistant) for CSI capture and motion detection.
- Seeed XIAO 24 GHz mmWave module: https://wiki.seeedstudio.com/mmwave_for_xiao/
