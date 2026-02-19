# ./backend/models/ortho.py

class Ortho:
    def __init__(self, filename, bounds=None, url=None, ortho_id=None, upload_date=None, crs=None, is_visible=False, is_cog=False, geometry_wkt=None):
        self.id = ortho_id
        self.filename = filename
        self.bounds = bounds
        self.url = url
        self.upload_date = upload_date
        self.crs = crs
        self.is_visible = is_visible
        
        # Новые поля
        self.is_cog = is_cog
        self.geometry_wkt = geometry_wkt  # Используется для передачи WKT в менеджер при вставке

    def to_dict(self):
        """
        Преобразует объект в словарь для JSON-ответа
        """
        return {
            "id": self.id,
            "filename": self.filename,
            "url": self.url,
            "bounds": self.bounds,
            "crs": self.crs,
            "is_visible": self.is_visible,
            "is_cog": self.is_cog,  # Добавляем флаг COG в ответ API
            "upload_date": str(self.upload_date) if self.upload_date else None
        }