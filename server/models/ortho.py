# ./backend/models/ortho.py

class Ortho:
    def __init__(self, filename, bounds=None, url=None, ortho_id=None, upload_date=None, crs=None, is_visible=False):
        self.id = ortho_id
        self.filename = filename
        self.bounds = bounds
        self.url = url
        self.upload_date = upload_date
        self.crs = crs
        self.is_visible = is_visible

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
            "upload_date": str(self.upload_date) if self.upload_date else None
        }