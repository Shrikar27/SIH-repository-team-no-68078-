
import argparse
import requests
import time
import random
import sys
import threading

# ---------- Argument parsing ----------
parser = argparse.ArgumentParser(description="Ticket machine simulator (interactive or auto)")
parser.add_argument("--backend", "-b", default="http://127.0.0.1:8000/update", help="Backend /update URL")
parser.add_argument("--bus", "-u", default="BUS101", help="Bus ID to simulate")
parser.add_argument("--mode", "-m", choices=("interactive", "auto"), default="interactive", help="Mode")
parser.add_argument("--interval", "-t", type=float, default=5.0, help="Auto mode interval seconds")
parser.add_argument("--lat", type=float, default=13.0827, help="Start latitude")
parser.add_argument("--lon", type=float, default=80.2707, help="Start longitude")
parser.add_argument("--route", "-r", default="Demo Route", help="Route name")
parser.add_argument("--start-occupancy", type=int, default=5, help="Initial occupancy")
args = parser.parse_args()

BACKEND = args.backend
BUS_ID = args.bus
MODE = args.mode
INTERVAL = args.interval
ROUTE = args.route

# state
state = {
    "lat": args.lat,
    "lon": args.lon,
    "occupancy": max(0, args.start_occupancy)
}

stop_event = threading.Event()

# ---------- Helpers ----------
def jitter_location(lat, lon, meters=10):
    """
    Add tiny jitter (meters) to lat/lon to simulate movement.
    1 deg lat ~= 110574 m
    1 deg lon ~= 111320 * cos(lat) m
    """
    # meters -> degrees
    dlat = (random.uniform(-1, 1) * meters) / 110574.0
    dlon = (random.uniform(-1, 1) * meters) / (111320.0 * max(0.0001, abs(lat)))
    return lat + dlat, lon + dlon

def send_update():
    payload = {
        "bus_id": BUS_ID,
        "latitude": state["lat"],
        "longitude": state["lon"],
        "occupancy": state["occupancy"],
        "route": ROUTE
    }
    try:
        r = requests.post(BACKEND, json=payload, timeout=4)
        print(f"[{time.strftime('%H:%M:%S')}] POST -> {BACKEND} | status={r.status_code} | occ={state['occupancy']} | ({state['lat']:.6f},{state['lon']:.6f})")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ERROR sending update: {e}")

def auto_worker():
    """Auto mode: periodically jitter location, randomly issue/alight small numbers"""
    while not stop_event.is_set():
        # small movement
        state["lat"], state["lon"] = jitter_location(state["lat"], state["lon"], meters=20)
        # random boarding/alighting
        delta = random.choices([-2, -1, 0, 0, 1, 2], weights=[5,10,60,10,10,5])[0]
        state["occupancy"] = max(0, state["occupancy"] + delta)
        send_update()
        # wait for next tick or exit
        stop_event.wait(INTERVAL)

# ---------- Main ----------
def interactive_loop():
    print("Ticket machine INTERACTIVE mode. Commands: i=issue, o=alight, s=send, q=quit")
    print(f"Bus ID: {BUS_ID}  Route: {ROUTE}  Backend: {BACKEND}")
    send_update()  
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "i":
                state["occupancy"] += 1
                
                state["lat"], state["lon"] = jitter_location(state["lat"], state["lon"], meters=5)
                send_update()
            elif cmd == "o":
                state["occupancy"] = max(0, state["occupancy"] - 1)
                state["lat"], state["lon"] = jitter_location(state["lat"], state["lon"], meters=5)
                send_update()
            elif cmd == "s":
                state["lat"], state["lon"] = jitter_location(state["lat"], state["lon"], meters=3)
                send_update()
            elif cmd == "q":
                print("Quitting interactive simulator.")
                break
            elif cmd == "":
                
                state["lat"], state["lon"] = jitter_location(state["lat"], state["lon"], meters=3)
                send_update()
            else:
                print("Unknown command. Use i/o/s/q")
    except (KeyboardInterrupt, EOFError):
        print("\nStopped by user.")

def main():
    print("Starting ticketsim.py")
    print(f"Mode: {MODE} | Bus: {BUS_ID} | Backend: {BACKEND}")
    if MODE == "auto":
        t = threading.Thread(target=auto_worker, daemon=True)
        t.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping auto mode...")
            stop_event.set()
            t.join(timeout=2)
    else:
        interactive_loop()

if __name__ == "__main__":
    main()
