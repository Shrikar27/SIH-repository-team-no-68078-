
import time
import traceback
import logging
from typing import Optional, Generator, List, Dict
from fastapi import FastAPI, HTTPException, Query
import threading
import importlib
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from math import radians, sin, cos, atan2, sqrt

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- Database ----------
DATABASE_URL = "sqlite:///./buses.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Bus(Base):
    __tablename__ = "buses"
    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(String, unique=True, index=True, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    occupancy = Column(Integer, nullable=True)
    route = Column(String, nullable=True)
    last_update = Column(Integer, nullable=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)   
    token = Column(String, nullable=True)       
    phone = Column(String, nullable=True)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(String, index=True)
    username = Column(String, index=True)
    phone = Column(String, index=True)
    bus_number = Column(String)
    route = Column(String)
    seat = Column(Integer)
    fare = Column(Integer)
    created_at = Column(Integer)


Base.metadata.create_all(bind=engine)

class BusUpdate(BaseModel):
    bus_id: str
    latitude: float
    longitude: float
    occupancy: int
    route: Optional[str] = None

class BusOut(BaseModel):
    bus_id: str
    latitude: Optional[float]
    longitude: Optional[float]
    occupancy: Optional[int]
    route: Optional[str]

class UserCreate(BaseModel):
    username: str
    password: str
    phone: str | None = None

class UserOut(BaseModel):
    id: int
    username: str

app = FastAPI(title="Chennai Live Bus Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def bus_to_dict(bus: Bus) -> dict:
    return {
        "bus_id": bus.bus_id,
        "latitude": float(bus.latitude) if bus.latitude is not None else None,
        "longitude": float(bus.longitude) if bus.longitude is not None else None,
        "occupancy": int(bus.occupancy) if bus.occupancy is not None else None,
        "route": bus.route,
        "last_update": int(bus.last_update) if bus.last_update is not None else None
    }

@app.post("/update")
def update_bus(payload: BusUpdate):
    """
    Create or update a bus record. Expects:
    {"bus_id":"MTC101","latitude":13.08,"longitude":80.27,"occupancy":12,"route":"Route A"}
    """
    db = SessionLocal()
    try:
        bus = db.query(Bus).filter(Bus.bus_id == payload.bus_id).first()
        now_ts = int(time.time())
        if bus:
            bus.latitude = payload.latitude
            bus.longitude = payload.longitude
            bus.occupancy = payload.occupancy
            bus.route = payload.route
            bus.last_update = now_ts
        else:
            bus = Bus(
                bus_id=payload.bus_id,
                latitude=payload.latitude,
                longitude=payload.longitude,
                occupancy=payload.occupancy,
                route=payload.route,
                last_update=now_ts
            )
            db.add(bus)
        db.commit()
        db.refresh(bus)
        logging.info(f"Updated bus {bus.bus_id} -> lat={bus.latitude:.6f} lon={bus.longitude:.6f} occ={bus.occupancy}")
        return {"status":"ok","bus_id":bus.bus_id}
    except Exception as e:
        db.rollback()
        logging.error("Error in /update handler", exc_info=True)
        
        raise HTTPException(status_code=500, detail=f"Internal server error (update): {str(e)}")
    finally:
        db.close()

@app.get("/bus/{bus_id}")
def get_bus(bus_id: str):
    try:
        db = next(get_db())
        bus = db.query(Bus).filter(Bus.bus_id == bus_id).first()
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found")
        return bus_to_dict(bus)
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error in /bus/{bus_id}:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error (get bus)")

@app.get("/buses")
def get_all_buses(as_map: Optional[bool] = Query(False, description="Return object map keyed by bus_id if true"),
                  min_lat: Optional[float] = None, max_lat: Optional[float] = None,
                  min_lon: Optional[float] = None, max_lon: Optional[float] = None):
    """
    Returns list of all buses. Optional query params to filter by bounding box:
      /buses?min_lat=12.9&max_lat=13.2&min_lon=80.1&max_lon=80.3

    If as_map=true it returns an object keyed by bus_id, otherwise returns an array.
    """
    try:
        db = next(get_db())
        q = db.query(Bus)
        if min_lat is not None:
            q = q.filter(Bus.latitude >= min_lat)
        if max_lat is not None:
            q = q.filter(Bus.latitude <= max_lat)
        if min_lon is not None:
            q = q.filter(Bus.longitude >= min_lon)
        if max_lon is not None:
            q = q.filter(Bus.longitude <= max_lon)
        buses = q.all()
        out = [bus_to_dict(b) for b in buses]
        if as_map:
            return {b["bus_id"]: b for b in out}
        return out
    except Exception as e:
        logging.error("Error in /buses:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error (get buses)")

@app.get("/ping")
def ping():
    return {"status":"ok", "time": int(time.time())}
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


MASTER_STOPS = [
    {"name":"Amritsar Railway Station","lat":31.6340,"lon":74.8737},
    {"name":"Golden Temple","lat":31.6200,"lon":74.8765},
    {"name":"Jalandhar Bus Stand","lat":31.3256,"lon":75.5792},
    {"name":"Ludhiana Railway Station","lat":30.9010,"lon":75.8573},
    {"name":"Patiala Bus Stand","lat":30.3398,"lon":76.3869},
    {"name":"Bathinda Railway Station","lat":30.2110,"lon":74.9455},
    {"name":"Chandigarh Bus Stand","lat":30.7333,"lon":76.7794},
    {"name":"Mohali Bus Stand","lat":30.7041,"lon":76.7177},
    {"name":"Ferozepur Railway Station","lat":30.9153,"lon":74.6100},
    {"name":"Gurdaspur Bus Stand","lat":32.0417,"lon":75.4017},
    {"name":"Pathankot Railway Station","lat":32.2748,"lon":75.6522},
    {"name":"Batala Bus Stand","lat":31.8186,"lon":75.2028},
    {"name":"Mansa Bus Stand","lat":29.9881,"lon":75.4017},
    {"name":"Barnala Bus Stand","lat":30.3745,"lon":75.5486},
    {"name":"Sangrur Railway Station","lat":30.2450,"lon":75.8447},
    {"name":"Abohar Bus Stand","lat":30.1445,"lon":74.1995},
    {"name":"Fazilka Bus Stand","lat":30.4017,"lon":74.0283},
    {"name":"Muktsar Railway Station","lat":30.4745,"lon":74.5169},
    {"name":"Dera Baba Nanak","lat":32.0333,"lon":75.0333},
    {"name":"Punjab University","lat":30.7589,"lon":76.7681},
    {"name":"Kharar Bus Stand","lat":30.7456,"lon":76.6544},
    # ... more Punjab stops
]

from fastapi import Header
from uuid import uuid4

_DEMO_USERS = {"demo": "demo"}  
_ACTIVE_TOKENS = {}  

class LoginReq(BaseModel):
    username: str
    password: str
    
@app.post("/register")
def register(user: UserCreate):
    db = SessionLocal()
    try:
        
        existing = db.query(User).filter(User.username == user.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")

        new_user = User(username=user.username, password=user.password, phone=user.phone)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"status": "ok", "id": new_user.id, "username": new_user.username}
    finally:
        db.close()

class LoginReq(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(req: LoginReq):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or user.password != req.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = uuid4().hex
        user.token = token
        db.commit()
        return {"status": "ok", "token": token, "username": user.username, "phone": user.phone}
    finally:
        db.close()
class BookingIn(BaseModel):
    booking_id: str
    username: str
    phone: str
    bus_number: str
    route: str
    seat: int
    fare: int

@app.post("/bookings")
def create_booking(payload: BookingIn):
    db = SessionLocal()
    try:
        bk = Booking(
            booking_id=payload.booking_id,
            username=payload.username,
            phone=payload.phone,
            bus_number=payload.bus_number,
            route=payload.route,
            seat=payload.seat,
            fare=payload.fare,
            created_at=int(time.time()),
        )
        db.add(bk)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()

@app.get("/bookings")
def list_bookings(phone: str | None = None, username: str | None = None):
    db = SessionLocal()
    try:
        q = db.query(Booking)
        if phone:
            q = q.filter(Booking.phone == phone)
        if username:
            q = q.filter(Booking.username == username)
        out = []
        for b in q.order_by(Booking.created_at.desc()).limit(100).all():
            out.append({
                "booking_id": b.booking_id,
                "username": b.username,
                "phone": b.phone,
                "bus_number": b.bus_number,
                "route": b.route,
                "seat": b.seat,
                "fare": b.fare,
                "created_at": b.created_at,
            })
        return out
    finally:
        db.close()

@app.get("/user/last4")
def get_user_last4(username: str):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == username).first()
        if not u or not u.phone:
            raise HTTPException(status_code=404, detail="User not found")
        return {"last4": u.phone[-4:]}
    finally:
        db.close()
        
app.get("/nearest")
def nearest(lat: float, lon: float, max_results: int = 5):
    # nearest stops
    stops = []
    for s in MASTER_STOPS:
        d = haversine_m(lat, lon, s["lat"], s["lon"])
        stops.append({"stop": s, "dist_m": int(d)})
    stops.sort(key=lambda x: x["dist_m"])
    # nearest buses (query DB)
    db = SessionLocal()
    buses = db.query(Bus).filter(Bus.latitude.isnot(None), Bus.longitude.isnot(None)).all()
    bus_list = []
    for b in buses:
        d = haversine_m(lat, lon, b.latitude, b.longitude)
        bus_list.append({"bus_id": b.bus_id, "lat": b.latitude, "lon": b.longitude, "occupancy": b.occupancy, "dist_m": int(d)})
    bus_list.sort(key=lambda x: x["dist_m"])
    return {"nearest_stops": stops[:max_results], "nearest_buses": bus_list[:max_results]}

# moving_sim.py
_sim_thread: Optional[threading.Thread] = None

def _start_simulator_background():
    global _sim_thread
    if _sim_thread and _sim_thread.is_alive():
        return False
    try:
        moving_sim = importlib.import_module("moving_sim")
    except Exception:
        logging.error("Could not import moving_sim.py", exc_info=True)
        raise HTTPException(status_code=500, detail="moving_sim.py not found or import failed")

    def runner():
        try:
            moving_sim.start_sim()
        except Exception:
            logging.error("moving_sim.start_sim crashed", exc_info=True)

    _sim_thread = threading.Thread(target=runner, name="bus-sim-thread", daemon=True)
    _sim_thread.start()
    return True

@app.post("/start-sim")
def start_sim():
    """Start the background bus simulation if not already running."""
    try:
        started = _start_simulator_background()
        return {"status": "ok", "started": bool(started)}
    except HTTPException:
        raise
    except Exception:
        logging.error("/start-sim failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start simulator")

class SosReq(BaseModel):
    message: str
    user: Optional[str] = None

@app.post("/sos")
def sos(req: SosReq):
    try:
        logging.warning(f"SOS from {req.user or 'unknown'}: {req.message}")
        return {"status": "ok"}
    except Exception:
        logging.error("/sos failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to log SOS")

BUS_CATALOG = {
    "PTC101": {"number": "18C", "name": "Amritsar → Jalandhar → Ludhiana → Patiala", "stops": ["Amritsar Railway Station", "Golden Temple", "Jalandhar Bus Stand", "Ludhiana Railway Station", "Patiala Bus Stand"], "rating": 4.2, "reserved_disabled": 2, "ramp": True},
    "PTC102": {"number": "21G", "name": "Bathinda → Mansa → Barnala → Sangrur", "stops": ["Bathinda Railway Station", "Mansa Bus Stand", "Barnala Bus Stand", "Sangrur Railway Station"], "rating": 4.0, "reserved_disabled": 1, "ramp": True},
    "PTC103": {"number": "70", "name": "Ferozepur → Abohar → Fazilka → Muktsar", "stops": ["Ferozepur Railway Station", "Abohar Bus Stand", "Fazilka Bus Stand", "Muktsar Railway Station"], "rating": 4.5, "reserved_disabled": 0, "ramp": False},
    "PTC104": {"number": "105", "name": "Gurdaspur → Pathankot → Dera Baba Nanak → Batala", "stops": ["Gurdaspur Bus Stand", "Pathankot Railway Station", "Dera Baba Nanak", "Batala Bus Stand"], "rating": 4.1, "reserved_disabled": 1, "ramp": False},
    "PTC105": {"number": "PU", "name": "Punjab University → Chandigarh → Mohali → Kharar", "stops": ["Punjab University", "Chandigarh Bus Stand", "Mohali Bus Stand", "Kharar Bus Stand"], "rating": 4.3, "reserved_disabled": 2, "ramp": True},
    # additional sample buses
    "PTC106": {"number": "12B", "name": "Amritsar → Tarn Taran → Patti → Ferozepur", "stops": ["Amritsar Railway Station", "Tarn Taran", "Patti", "Ferozepur Railway Station"], "rating": 4.0, "reserved_disabled": 1, "ramp": True},
    "PTC107": {"number": "47A", "name": "Ludhiana → Jagraon → Moga → Faridkot", "stops": ["Ludhiana Railway Station", "Jagraon", "Moga", "Faridkot"], "rating": 3.9, "reserved_disabled": 1, "ramp": False},
}

def _merge_bus(b: Bus) -> dict:
    data = bus_to_dict(b)
    meta = BUS_CATALOG.get(b.bus_id, {})
    data.update({
        "number": meta.get("number"),
        "name": meta.get("name"),
        "stops": meta.get("stops", []),
        "rating": meta.get("rating"),
        "reserved_disabled": meta.get("reserved_disabled", 0),
        "ramp": meta.get("ramp", False),
    })
    
    try:
        spin = int(time.time() // 300)
        h = abs(hash(b.bus_id))
        pick = (h + spin) % 3
        data["status"] = ["on-time", "delayed", "early"][pick]
    except Exception:
        data["status"] = "on-time"

    occ = data.get("occupancy")
    if occ is None:
        
        seed = (abs(hash(b.bus_id)) + int(time.time() // 600) * 5) % 50
        occ = 10 + seed  # 10..79
        data["occupancy"] = occ
    occ = int(occ)
    if occ >= 80:
        data["occupancy_label"] = "crowded"
    elif occ >= 60:
        data["occupancy_label"] = "moderate"
    else:
        data["occupancy_label"] = "available"
    return data

@app.get("/buses_enriched")
def get_buses_enriched():
    try:
        db = next(get_db())
        
        ids = list(BUS_CATALOG.keys())
        buses = db.query(Bus).filter(Bus.bus_id.in_(ids)).all()
        merged = {b.bus_id: _merge_bus(b) for b in buses}
        
        out = []
        for bid in ids:
            if bid in merged:
                out.append(merged[bid])
            else:
                meta = BUS_CATALOG[bid]
                out.append({
                    "bus_id": bid,
                    "latitude": None,
                    "longitude": None,
                    "occupancy": 0,
                    "route": meta["name"],
                    "number": meta["number"],
                    "name": meta["name"],
                    "stops": meta["stops"],
                    "rating": meta["rating"],
                    "status": "on-time",
                    "occupancy_label": "available",
                })
        return out
    except Exception:
        logging.error("/buses_enriched failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch enriched buses")

class PassengerCountUpdate(BaseModel):
    bus_id: str
    action: str  # "increment" or "decrement"

@app.post("/update_passenger_count")
def update_passenger_count(payload: PassengerCountUpdate):
    try:
        db = next(get_db())
        bus = db.query(Bus).filter(Bus.bus_id == payload.bus_id).first()
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found")
        
        if payload.action == "increment":
            bus.occupancy = min(50, bus.occupancy + 1)  # Max 50 passengers (40 seated + 10 standing)
        elif payload.action == "decrement":
            bus.occupancy = max(0, bus.occupancy - 1)  # Min 0 passengers
        
        db.commit()
        return {"status": "ok", "new_count": bus.occupancy}
    except Exception as e:
        logging.error("/update_passenger_count failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update passenger count")
