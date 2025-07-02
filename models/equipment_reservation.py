from datetime import datetime, timedelta
from models.db import db


class EquipmentReservation(db.Model):
    __tablename__ = 'equipment_reservations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active')
    queue_position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user_id, equipment_id, start_time, duration_minutes, queue_position=0, status='active'):
        self.user_id = user_id
        self.equipment_id = equipment_id
        self.start_time = start_time
        self.duration_minutes = duration_minutes
        self.end_time = start_time + timedelta(minutes=duration_minutes)
        self.queue_position = queue_position
        self.status = status

    def get_remaining_time(self):
        now = datetime.utcnow()
        if now > self.end_time:
            return 0
        delta = self.end_time - now
        return int(delta.total_seconds() / 60)

    def update_duration(self, new_duration_minutes):
        if new_duration_minutes < self.duration_minutes and new_duration_minutes >= 5:
            self.end_time = self.start_time + timedelta(minutes=new_duration_minutes)
            self.duration_minutes = new_duration_minutes
            return True
        return False

    def __repr__(self):
        return f'<EquipmentReservation {self.id} - User: {self.user_id} - Equipment: {self.equipment_id}>'