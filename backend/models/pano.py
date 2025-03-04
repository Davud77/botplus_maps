# ./backend/models/pano.py

class Pano:
    def __init__(
        self,
        pano_id=None,
        filename=None,
        latitude=None,
        longitude=None,
        user_id=None,
        file_type=None,
        file_size=None,
        width=None,
        height=None,
        first_photo_date=None,
        model=None,
        altitude=None,
        focal_length=None,
        tags=None
    ):
        self.id = pano_id
        self.filename = filename
        self.latitude = latitude
        self.longitude = longitude
        self.user_id = user_id
        self.file_type = file_type
        self.file_size = file_size
        self.width = width
        self.height = height
        self.first_photo_date = first_photo_date
        self.model = model
        self.altitude = altitude
        self.focal_length = focal_length
        self.tags = tags