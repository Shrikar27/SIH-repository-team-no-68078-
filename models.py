from sqlalchemy import Column, Integer, String, Float
from database import Base

class Bus(Base):
    __tablename__ = "buses"

    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(String, unique=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    occupancy = Column(Integer)  
    route = Column(String, nullable=True)
