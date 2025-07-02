from datetime import datetime
from models.db import db


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=False)
    qr_code = db.Column(db.String(100), unique=True, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reservations = db.relationship('EquipmentReservation', backref='equipment', lazy=True)

    def __init__(self, name, description, location, qr_code):
        self.name = name
        self.description = description
        self.location = location
        self.qr_code = qr_code
        self.is_available = True

    def __repr__(self):
        return f'<Equipment {self.id} - {self.name} - Location: {self.location}>'