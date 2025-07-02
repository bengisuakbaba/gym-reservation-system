from datetime import datetime
from models.db import db


class Presence(db.Model):
    __tablename__ = 'presences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    check_out_time = db.Column(db.DateTime, nullable=True)
    is_present = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='presences')

    def __init__(self, user_id, check_in_time=None):
        self.user_id = user_id
        self.check_in_time = check_in_time or datetime.utcnow()
        self.is_present = True

    def check_out(self):
        self.check_out_time = datetime.utcnow()
        self.is_present = False

    def __repr__(self):
        return f'<Presence {self.id} - User: {self.user_id} - Present: {self.is_present}>'

    @classmethod
    def get_current_count(cls):
        return cls.query.filter_by(is_present=True).count()

    @classmethod
    def get_occupancy_percentage(cls, max_capacity=20):
        current_count = cls.get_current_count()
        return int((current_count / max_capacity) * 100)