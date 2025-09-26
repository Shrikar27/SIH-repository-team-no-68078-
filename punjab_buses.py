#!/usr/bin/env python3
# punjab_buses.py — seeds 35 buses across Punjab small cities and two-tier towns
# Usage: python punjab_buses.py

import requests, time, random

BACKEND = "http://127.0.0.1:8000/update"

# anchor stops across Punjab small cities and two-tier towns
stops = {
    "Amritsar Railway Station": (31.6340, 74.8737),
    "Golden Temple": (31.6200, 74.8765),
    "Jalandhar Bus Stand": (31.3256, 75.5792),
    "Ludhiana Railway Station": (30.9010, 75.8573),
    "Patiala Bus Stand": (30.3398, 76.3869),
    "Bathinda Railway Station": (30.2110, 74.9455),
    "Chandigarh Bus Stand": (30.7333, 76.7794),
    "Mohali Bus Stand": (30.7041, 76.7177),
    "Ferozepur Railway Station": (30.9153, 74.6100),
    "Gurdaspur Bus Stand": (32.0417, 75.4017),
    "Pathankot Railway Station": (32.2748, 75.6522),
    "Batala Bus Stand": (31.8186, 75.2028),
    "Mansa Bus Stand": (29.9881, 75.4017),
    "Barnala Bus Stand": (30.3745, 75.5486),
    "Sangrur Railway Station": (30.2450, 75.8447),
    "Abohar Bus Stand": (30.1445, 74.1995),
    "Fazilka Bus Stand": (30.4017, 74.0283),
    "Muktsar Railway Station": (30.4745, 74.5169),
    "Dera Baba Nanak": (32.0333, 75.0333),
    "Punjab University": (30.7589, 76.7681),
    "Kharar Bus Stand": (30.7456, 76.6544),
    "Tarn Taran": (31.4500, 74.9333),
    "Patti": (31.2800, 74.8500),
    "Jagraon": (30.7833, 75.4833),
    "Moga": (30.8167, 75.1667),
    "Faridkot": (30.6667, 74.7500),
    "Malout": (30.1833, 74.5000),
    "Sunam": (30.1333, 75.8000),
    "Rajpura": (30.4833, 76.6000),
    "Nabha": (30.3667, 76.1500),
}

# sample route templates connecting Punjab small cities and two-tier towns
routes = [
    "Amritsar Railway Station → Golden Temple → Jalandhar Bus Stand → Ludhiana Railway Station → Patiala Bus Stand",
    "Bathinda Railway Station → Mansa Bus Stand → Barnala Bus Stand → Sangrur Railway Station",
    "Ferozepur Railway Station → Abohar Bus Stand → Fazilka Bus Stand → Muktsar Railway Station",
    "Gurdaspur Bus Stand → Pathankot Railway Station → Dera Baba Nanak → Batala Bus Stand",
    "Punjab University → Chandigarh Bus Stand → Mohali Bus Stand → Kharar Bus Stand",
    "Amritsar Railway Station → Tarn Taran → Patti → Ferozepur Railway Station",
    "Ludhiana Railway Station → Jagraon → Moga → Faridkot",
    "Bathinda Railway Station → Malout → Muktsar Railway Station → Fazilka Bus Stand",
    "Patiala Bus Stand → Rajpura → Nabha → Sangrur Railway Station",
    "Chandigarh Bus Stand → Kharar Bus Stand → Rajpura → Patiala Bus Stand",
    "Jalandhar Bus Stand → Ludhiana Railway Station → Moga → Faridkot",
    "Amritsar Railway Station → Batala Bus Stand → Gurdaspur Bus Stand → Pathankot Railway Station",
]

def jitter(lat, lon, max_delta=0.01):
    return (
        lat + random.uniform(-max_delta, max_delta),
        lon + random.uniform(-max_delta, max_delta)
    )

buses = []
for i in range(201, 236):  # PTC201 .. PTC235
    stop_name = random.choice(list(stops.keys()))
    lat, lon = jitter(*stops[stop_name], max_delta=0.005)
    occ = random.randint(5, 50)
    route = random.choice(routes)
    buses.append({
        "bus_id": f"PTC{i}",
        "latitude": lat,
        "longitude": lon,
        "occupancy": occ,
        "route": route
    })

print(f"Seeding {len(buses)} buses to {BACKEND} ...")
for bus in buses:
    try:
        r = requests.post(BACKEND, json=bus, timeout=5)
        print(f"Seeded {bus['bus_id']} -> {r.status_code} {r.text}")
        if r.status_code >= 400:
            try:
                print("Error detail (json):", r.json())
            except Exception:
                pass
    except Exception as e:
        print(f"Error seeding {bus['bus_id']}: {e}")
    time.sleep(0.1)
