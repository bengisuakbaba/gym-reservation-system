from datetime import datetime
from models.db import db


class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user_id, date, start_time, end_time, status='pending'):
        self.user_id = user_id
        self.date = date
        self.start_time = start_time
        self.end_time = end_time
        self.status = status

    def __repr__(self):
        return f'<Reservation {self.id} - User: {self.user_id} - Date: {self.date} - Time: {self.start_time}-{self.end_time}>'