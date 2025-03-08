from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from ..database import get_db
from sqlalchemy.orm import Session
from ..models import Panorama
from fastapi import Depends

router = APIRouter()

class PanoramaMarker(BaseModel):
    id: str
    latitude: float
    longitude: float

@router.get("/panoramas", response_model=List[PanoramaMarker])
async def get_panoramas(
    north: float = Query(..., description="Северная граница"),
    south: float = Query(..., description="Южная граница"),
    east: float = Query(..., description="Восточная граница"),
    west: float = Query(..., description="Западная граница"),
    db: Session = Depends(get_db)
):
    """
    Получает маркеры панорам в пределах указанного экстента карты
    """
    try:
        panoramas = db.query(Panorama).filter(
            Panorama.latitude <= north,
            Panorama.latitude >= south,
            Panorama.longitude <= east,
            Panorama.longitude >= west
        ).all()

        return [
            PanoramaMarker(
                id=p.id,
                latitude=p.latitude,
                longitude=p.longitude
            )
            for p in panoramas
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 