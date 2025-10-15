# ./backend/models/ortho.py

class Ortho:
    def __init__(self, ortho_id=None, filename=None, bounds=None):
        self.id = ortho_id
        self.filename = filename
        self.bounds = bounds