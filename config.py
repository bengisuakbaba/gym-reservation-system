import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///gym_management.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALLOWED_EMAIL_DOMAIN = 'isik.edu.tr'

    ADMIN_EMAIL = 'admin@isik.edu.tr'
    ADMIN_PASSWORD = 'admin123'