#!/usr/bin/env python3
import threading
import time
import math
import random
import requests

# ---------------- CONFIG ----------------
BACKEND_UPDATE_URL = "http://127.0.0.1:8000/update" 
POST_INTERVAL = 5.0        
NUM_BUSES = None           
SIMULATION_JITTER = 0.000003  

# ---------------- Punjab routes (waypoints) ----------------
ROUTES = [
    {"name": "Amritsar → Jalandhar → Ludhiana → Patiala", "stops": [
        (31.6340, 74.8737),  # Amritsar Railway Station
        (31.6200, 74.8765),  # Golden Temple
        (31.3256, 75.5792),  # Jalandhar Bus Stand
        (30.9010, 75.8573),  # Ludhiana Railway Station
        (30.3398, 76.3869),  # Patiala Bus Stand
    ]},
    {"name": "Bathinda → Mansa → Barnala → Sangrur", "stops": [
        (30.2110, 74.9455),  # Bathinda Railway Station
        (29.9881, 75.4017),  # Mansa Bus Stand
        (30.3745, 75.5486),  # Barnala Bus Stand
        (30.2450, 75.8447),  # Sangrur Railway Station
    ]},
    {"name": "Ferozepur → Abohar → Fazilka → Muktsar", "stops": [
        (30.9153, 74.6100),  # Ferozepur Railway Station
        (30.1445, 74.1995),  # Abohar Bus Stand
        (30.4017, 74.0283),  # Fazilka Bus Stand
        (30.4745, 74.5169),  # Muktsar Railway Station
    ]},
    {"name": "Gurdaspur → Pathankot → Dera Baba Nanak → Batala", "stops": [
        (32.0417, 75.4017),  # Gurdaspur Bus Stand
        (32.2748, 75.6522),  # Pathankot Railway Station
        (32.0333, 75.0333),  # Dera Baba Nanak
        (31.8186, 75.2028),  # Batala Bus Stand
    ]},
    {"name": "Punjab University → Chandigarh → Mohali → Kharar", "stops": [
        (30.7589, 76.7681),  # Punjab University
        (30.7333, 76.7794),  # Chandigarh Bus Stand
        (30.7041, 76.7177),  # Mohali Bus Stand
        (30.7456, 76.6544),  # Kharar Bus Stand
    ]},
    {"name": "Amritsar → Tarn Taran → Patti → Ferozepur", "stops": [
        (31.6340, 74.8737),  # Amritsar Railway Station
        (31.4500, 74.9333),  # Tarn Taran
        (31.2800, 74.8500),  # Patti
        (30.9153, 74.6100),  # Ferozepur Railway Station
    ]},
    {"name": "Ludhiana → Jagraon → Moga → Faridkot", "stops": [
        (30.9010, 75.8573),  # Ludhiana Railway Station
        (30.7833, 75.4833),  # Jagraon
        (30.8167, 75.1667),  # Moga
        (30.6667, 74.7500),  # Faridkot
    ]},
    {"name": "Bathinda → Malout → Muktsar → Fazilka", "stops": [
        (30.2110, 74.9455),  # Bathinda Railway Station
        (30.1833, 74.5000),  # Malout
        (30.4745, 74.5169),  # Muktsar Railway Station
        (30.4017, 74.0283),  # Fazilka Bus Stand
    ]},
    {"name": "Patiala → Rajpura → Nabha → Sangrur", "stops": [
        (30.3398, 76.3869),  # Patiala Bus Stand
        (30.4833, 76.6000),  # Rajpura
        (30.3667, 76.1500),  # Nabha
        (30.2450, 75.8447),  # Sangrur Railway Station
    ]},
    {"name": "Chandigarh → Kharar → Rajpura → Patiala", "stops": [
        (30.7333, 76.7794),  # Chandigarh Bus Stand
        (30.7456, 76.6544),  # Kharar Bus Stand
        (30.4833, 76.6000),  # Rajpura
        (30.3398, 76.3869),  # Patiala Bus Stand
    ]},
]

if NUM_BUSES is None:
    NUM_BUSES = len(ROUTES)

# ---------------- helpers ----------------
def haversine_km(a_lat, a_lon, b_lat, b_lon):
    R = 6371.0
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def interp(a, b, frac):
    return a + (b - a) * frac

# ---------------- Bus simulator class ----------------
class BusThread(threading.Thread):
    def __init__(self, bus_id: str, route_def: dict, post_interval: float = POST_INTERVAL):
        super().__init__(daemon=True)
        self.bus_id = bus_id
        self.route_name = route_def["name"]
        self.waypoints = route_def["stops"]
        self.post_interval = post_interval
        self.current_segment = 0
        self.frac = 0.0
        # occupancy baseline + noise
        self.occupancy = random.randint(8, 35)
        # fixed speed per bus for smoother, consistent motion
        self.speed_kmph = random.uniform(22, 28)
        # precompute distances and segment lengths
        self.segments = []
        for i in range(len(self.waypoints) - 1):
            a = self.waypoints[i]
            b = self.waypoints[i + 1]
            d_km = haversine_km(a[0], a[1], b[0], b[1])
            self.segments.append({"a": a, "b": b, "dist_km": d_km})
        
        if not self.segments:
            self.segments.append({"a": self.waypoints[0], "b": self.waypoints[0], "dist_km": 0.1})

    def get_current_latlon(self):
        seg = self.segments[self.current_segment]
        lat = interp(seg["a"][0], seg["b"][0], self.frac)
        lon = interp(seg["a"][1], seg["b"][1], self.frac)
        
        lat += random.uniform(-SIMULATION_JITTER, SIMULATION_JITTER)
        lon += random.uniform(-SIMULATION_JITTER, SIMULATION_JITTER)
        return lat, lon

    def step(self, dt_sec):
        """Advance position based on speed and current segment distance"""
        seg = self.segments[self.current_segment]
        if seg["dist_km"] <= 0:
            
            self.frac = 1.0
        else:
            
            v_km_s = (self.speed_kmph / 3600.0)
            
            self.frac += (v_km_s * dt_sec) / max(1e-6, seg["dist_km"])
        if self.frac >= 1.0:
            # Bus reached a stop - simulate passengers getting off
            if random.random() < 0.3:  # 30% chance of passengers alighting
                alighting_passengers = random.randint(0, min(3, self.occupancy))
                self.occupancy = max(0, self.occupancy - alighting_passengers)
            
            self.current_segment = (self.current_segment + 1) % len(self.segments)
            self.frac = 0.0
            
            # Simulate passengers boarding (less frequent than alighting)
            if random.random() < 0.2:  # 20% chance of passengers boarding
                boarding_passengers = random.randint(0, min(2, 50 - self.occupancy))
                self.occupancy = min(50, self.occupancy + boarding_passengers)
            
            # Ensure realistic passenger distribution (max 40 seated, rest standing)
            if self.occupancy > 50:
                self.occupancy = 50  # Cap at 50 total passengers

    def make_payload(self):
        lat, lon = self.get_current_latlon()
        payload = {
            "bus_id": self.bus_id,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "occupancy": int(self.occupancy),
            "route": self.route_name
        }
        return payload

    def run(self):
        last_time = time.time()
        while True:
            
            now = time.time()
            dt = now - last_time
            last_time = now
            self.step(dt)
            payload = self.make_payload()
        
            try:
                r = requests.post(BACKEND_UPDATE_URL, json=payload, timeout=4)
                if r.status_code >= 400:
                    print(f"[{self.bus_id}] POST error {r.status_code} {r.text}")
                else:
                    print(f"[{self.bus_id}] POST ok occ={payload['occupancy']} @ ({payload['latitude']},{payload['longitude']})")
            except Exception as e:
                print(f"[{self.bus_id}] POST exception: {e}")
            # wait
            time.sleep(self.post_interval)

# ---------------- spawn N buses ----------------
def start_sim(num_buses=NUM_BUSES):
    threads = []
    for i in range(num_buses):
        route = ROUTES[i % len(ROUTES)]
        bus_id = f"PTC{101 + i}"
        t = BusThread(bus_id=bus_id, route_def=route)
        t.start()
        threads.append(t)
        time.sleep(0.2)
    print(f"Started {len(threads)} simulated buses. Posting to {BACKEND_UPDATE_URL} every {POST_INTERVAL}s each.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping simulator (ctrl-c)")

if __name__ == "__main__":
    start_sim()
