from pydantic import BaseModel

class BusUpdate(BaseModel):
    bus_id: str
    latitude: float
    longitude: float
    occupancy: int
    route: str | None = None

class BusOut(BaseModel):
    bus_id: str
    latitude: float
    longitude: float
    occupancy: int
    route: str | None
    class Config:
        orm_mode = True
