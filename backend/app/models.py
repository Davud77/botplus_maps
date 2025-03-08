from sqlalchemy import Column, String, Float, DateTime, Integer, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Panorama(Base):
    __tablename__ = "panoramas"

    id = Column(String, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    filename = Column(String, nullable=False)
    upload_date = Column(DateTime, nullable=False)
    user_id = Column(String, nullable=False)
    file_size = Column(Float, nullable=False)
    file_type = Column(String, nullable=False)
    full_pano_width_pixels = Column(Integer)
    full_pano_height_pixels = Column(Integer)
    first_photo_date = Column(DateTime)
    model = Column(String)
    gps_altitude = Column(Float)
    fov = Column(Float)
    tags = Column(String)

    # Добавляем составной индекс для оптимизации запросов по координатам
    __table_args__ = (
        Index('idx_panorama_coordinates', 'latitude', 'longitude'),
    ) 