from flask import Flask, render_template, Blueprint, redirect, url_for, jsonify
from flask_login import LoginManager, current_user
from config import Config
from models.db import db, bcrypt
from controllers.auth_controller import create_admin_user
from datetime import datetime

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from models.user import User
    from models.reservation import Reservation
    from models.equipment import Equipment
    from models.equipment_reservation import EquipmentReservation
    from models.presence import Presence

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    @app.context_processor
    def inject_user_reservations():
        if current_user.is_authenticated:
            user_reservations = EquipmentReservation.query.filter_by(
                user_id=current_user.id,
                status='active'
            ).all()

            reservations_data = []
            for reservation in user_reservations:
                equipment = Equipment.query.get(reservation.equipment_id)
                if equipment:
                    reservations_data.append({
                        'id': reservation.id,
                        'equipment_name': equipment.name,
                        'end_time': reservation.end_time.isoformat(),
                        'start_time': reservation.start_time.isoformat(),
                        'queue_position': reservation.queue_position
                    })

            return {'global_user_reservations': reservations_data}
        return {'global_user_reservations': []}

    from controllers.auth_controller import auth_bp
    from controllers.gym_controller import gym_bp
    from controllers.admin_controller import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(gym_bp, url_prefix='/gym')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    main_bp = Blueprint('main', __name__)

    @main_bp.route('/dashboard')
    def dashboard():
        gym_occupancy = Presence.get_occupancy_percentage()
        return render_template('dashboard.html', gym_occupancy=gym_occupancy)

    @main_bp.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @main_bp.route('/api/user-reservations')
    def get_user_reservations():
        if not current_user.is_authenticated:
            return jsonify([])

        user_reservations = EquipmentReservation.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).all()

        reservations_data = []
        for reservation in user_reservations:
            equipment = Equipment.query.get(reservation.equipment_id)
            if equipment:
                reservations_data.append({
                    'id': reservation.id,
                    'equipment_name': equipment.name,
                    'end_time': reservation.end_time.isoformat(),
                    'start_time': reservation.start_time.isoformat(),
                    'queue_position': reservation.queue_position
                })

        return jsonify(reservations_data)

    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        create_admin_user()
        create_default_equipment(app)

    return app


def create_default_equipment(app):
    from models.equipment import Equipment

    with app.app_context():
        if Equipment.query.count() == 0:
            print("Creating default equipment...")

            default_equipment = [
                {
                    'name': 'Treadmill 1',
                    'description': '',
                    'location': '',
                    'qr_code': 'treadmill_1'
                },
                {
                    'name': 'Bench Press 1',
                    'description': '',
                    'location': '',
                    'qr_code': 'bench_press_1'
                },
                {
                    'name': 'Squat Rack 1',
                    'description': '',
                    'location': '',
                    'qr_code': 'squat_rack_1'
                },
                {
                    'name': 'Elliptical Trainer 1',
                    'description': '',
                    'location': '',
                    'qr_code': 'elliptical_1'
                },
                {
                    'name': 'Rowing Machine 1',
                    'description': '',
                    'location': '',
                    'qr_code': 'rowing_1'
                }
            ]

            for item in default_equipment:
                equipment = Equipment(
                    name=item['name'],
                    description=item['description'],
                    location=item['location'],
                    qr_code=item['qr_code']
                )
                db.session.add(equipment)

            db.session.commit()
            print("Default equipment created!")

            try:
                from controllers.admin_controller import generate_qr_code
                for item in default_equipment:
                    generate_qr_code(item['qr_code'])
                print("QR codes generated!")
            except Exception as e:
                print(f"Error generating QR codes: {e}")


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)