from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, desc
from models.db import db
from models.equipment import Equipment
from models.equipment_reservation import EquipmentReservation
from models.presence import Presence

gym_bp = Blueprint('gym', __name__)


def get_equipment_calorie_rate(equipment_name):

    if not equipment_name:
        return 5.0

    equipment_name_lower = equipment_name.lower().strip()

    equipment_keywords = {
        'treadmill': 9.0,
        'running': 9.0,

        'elliptical': 10.0,
        'cross': 10.0,

        'bike': 6.4,
        'spinning': 6.4,
        'cycle': 6.4,

        'leg press': 5.3,

        'pulldown': 4.0,
        'lat': 4.0,

        'chest fly': 4.1,
        'pec': 4.1,

        'cable': 4.3,
    }

    for keyword, rate in equipment_keywords.items():
        if keyword in equipment_name_lower:
            return rate

    return 5.0


def calculate_calories_for_reservation(equipment_name, duration_minutes):

    if not equipment_name or duration_minutes <= 0:
        return 0

    calorie_rate = get_equipment_calorie_rate(equipment_name)
    total_calories = calorie_rate * duration_minutes

    return round(total_calories)


def calculate_total_calories_for_reservations(reservations, equipment_map):

    total_calories = 0

    for reservation in reservations:
        if reservation.equipment_id in equipment_map:
            equipment_name = equipment_map[reservation.equipment_id].name
            calories = calculate_calories_for_reservation(
                equipment_name,
                reservation.duration_minutes
            )
            total_calories += calories

    return total_calories


@gym_bp.route('/enter', methods=['GET'])
@login_required
def gym_entry_qr():
    occupancy = Presence.get_occupancy_percentage(max_capacity=20)
    return render_template('gym/entry_qr.html', occupancy=occupancy)


@gym_bp.route('/exit', methods=['GET'])
@login_required
def gym_exit_qr():
    return render_template('gym/exit_qr.html')


@gym_bp.route('/check-in/<qr_code>', methods=['POST'])
@login_required
def check_in(qr_code):
    if qr_code != 'gym_entry_qrcode':
        flash('Invalid QR code', 'danger')
        return redirect(url_for('gym.gym_entry_qr'))

    active_presence = Presence.query.filter_by(user_id=current_user.id, is_present=True).first()
    if active_presence:
        flash('You are already checked in to the gym', 'warning')
        return redirect(url_for('gym.equipment_list'))

    new_presence = Presence(user_id=current_user.id)
    db.session.add(new_presence)
    db.session.commit()

    flash('Successfully checked in to the gym', 'success')
    return redirect(url_for('gym.equipment_list'))


@gym_bp.route('/check-out/<qr_code>', methods=['POST'])
@login_required
def check_out(qr_code):
    if qr_code != 'gym_exit_qrcode':
        flash('Invalid QR code', 'danger')
        return redirect(url_for('gym.gym_exit_qr'))

    active_presence = Presence.query.filter_by(user_id=current_user.id, is_present=True).first()
    if not active_presence:
        flash('You are not currently checked in to the gym', 'warning')
        return redirect(url_for('main.dashboard'))

    active_presence.check_out()
    db.session.commit()

    active_reservations = EquipmentReservation.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).all()

    for reservation in active_reservations:
        reservation.status = 'completed'
        equipment = Equipment.query.get(reservation.equipment_id)
        if equipment:
            equipment.is_available = True

    db.session.commit()

    flash('Successfully checked out from the gym', 'success')
    return redirect(url_for('main.dashboard'))


@gym_bp.route('/equipment', methods=['GET'])
@login_required
def equipment_list():
    active_presence = Presence.query.filter_by(user_id=current_user.id, is_present=True).first()
    if not active_presence:
        flash('You need to check in to the gym first', 'warning')
        return redirect(url_for('gym.gym_entry_qr'))

    check_and_update_reservations()

    equipment_list = Equipment.query.all()

    reservations = {}
    for equipment in equipment_list:
        current_reservation = EquipmentReservation.query.filter_by(
            equipment_id=equipment.id,
            status='active',
            queue_position=0
        ).first()

        queue = EquipmentReservation.query.filter_by(
            equipment_id=equipment.id,
            status='active'
        ).filter(EquipmentReservation.queue_position > 0).order_by(EquipmentReservation.queue_position).all()

        reservations[equipment.id] = {
            'current': current_reservation,
            'queue': queue
        }

    now = datetime.now()

    return render_template('gym/equipment_list.html', equipment_list=equipment_list, reservations=reservations, now=now)


@gym_bp.route('/equipment/<qr_code>', methods=['GET'])
@login_required
def equipment_detail(qr_code):
    active_presence = Presence.query.filter_by(user_id=current_user.id, is_present=True).first()
    if not active_presence:
        flash('You need to check in to the gym first', 'warning')
        return redirect(url_for('gym.gym_entry_qr'))

    equipment = Equipment.query.filter_by(qr_code=qr_code).first()
    if not equipment:
        flash('Equipment not found', 'danger')
        return redirect(url_for('gym.equipment_list'))

    current_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment.id,
        status='active',
        queue_position=0
    ).first()

    if not current_reservation:
        if not equipment.is_available:
            equipment.is_available = True
            db.session.commit()

        next_in_queue = EquipmentReservation.query.filter_by(
            equipment_id=equipment.id,
            status='active',
            queue_position=1
        ).first()

        if next_in_queue and datetime.now() >= next_in_queue.start_time:
            next_in_queue.queue_position = 0
            next_in_queue.start_time = datetime.now()
            next_in_queue.end_time = datetime.now() + timedelta(minutes=next_in_queue.duration_minutes)
            equipment.is_available = False

            queued_reservations = EquipmentReservation.query.filter(
                EquipmentReservation.equipment_id == equipment.id,
                EquipmentReservation.status == 'active',
                EquipmentReservation.queue_position > 1
            ).all()

            for queued in queued_reservations:
                queued.queue_position -= 1

            update_queue_times(equipment.id, 1)
            db.session.commit()

            if next_in_queue.user_id == current_user.id:
                flash('Your reservation is now active!', 'success')

    current_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment.id,
        status='active',
        queue_position=0
    ).first()

    queue = EquipmentReservation.query.filter_by(
        equipment_id=equipment.id,
        status='active'
    ).filter(EquipmentReservation.queue_position > 0).order_by(EquipmentReservation.queue_position).all()

    user_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment.id,
        user_id=current_user.id,
        status='active'
    ).first()

    now = datetime.now()

    return render_template(
        'gym/equipment_detail.html',
        equipment=equipment,
        current_reservation=current_reservation,
        queue=queue,
        user_reservation=user_reservation,
        now=now
    )


@gym_bp.route('/equipment/<int:equipment_id>/reserve', methods=['POST'])
@login_required
def reserve_equipment(equipment_id):
    active_presence = Presence.query.filter_by(user_id=current_user.id, is_present=True).first()
    if not active_presence:
        flash('You need to check in to the gym first', 'warning')
        return redirect(url_for('gym.gym_entry_qr'))

    equipment = Equipment.query.get_or_404(equipment_id)

    duration_minutes = int(request.form.get('duration', 30))
    if duration_minutes < 5 or duration_minutes > 120:
        flash('Duration must be between 5 and 120 minutes', 'danger')
        return redirect(url_for('gym.equipment_detail', qr_code=equipment.qr_code))

    active_user_reservation = EquipmentReservation.query.filter_by(
        user_id=current_user.id,
        status='active',
        queue_position=0
    ).first()

    if active_user_reservation:
        current_equipment_end_time = active_user_reservation.end_time

        target_equipment_available_time = calculate_equipment_available_time(equipment_id)

        if current_equipment_end_time > target_equipment_available_time:
            active_equipment = Equipment.query.get(active_user_reservation.equipment_id)
            if active_equipment:
                flash(
                    f'You are currently using {active_equipment.name} until {current_equipment_end_time.strftime("%H:%M")}. You can only reserve {equipment.name} if it becomes available at or after {current_equipment_end_time.strftime("%H:%M")}.',
                    'warning')
                return redirect(url_for('gym.equipment_detail', qr_code=equipment.qr_code))

    existing_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment_id,
        user_id=current_user.id,
        status='active'
    ).first()

    if existing_reservation:
        flash('You already have a reservation for this equipment', 'warning')
        return redirect(url_for('gym.equipment_detail', qr_code=equipment.qr_code))

    queued_reservations_count = EquipmentReservation.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).filter(EquipmentReservation.queue_position > 0).count()

    if queued_reservations_count >= 2:
        flash('You can only have maximum 2 equipment reservations in queue at the same time', 'warning')
        return redirect(url_for('gym.equipment_detail', qr_code=equipment.qr_code))

    current_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment_id,
        status='active',
        queue_position=0
    ).first()

    queue_position = 0
    start_time = datetime.now()

    if current_reservation:
        last_in_queue = EquipmentReservation.query.filter_by(
            equipment_id=equipment_id,
            status='active'
        ).order_by(desc(EquipmentReservation.queue_position)).first()

        if last_in_queue:
            queue_position = last_in_queue.queue_position + 1
            start_time = last_in_queue.end_time + timedelta(minutes=1)
        else:
            queue_position = 1
            start_time = current_reservation.end_time + timedelta(minutes=1)
    else:
        equipment.is_available = False

    new_reservation = EquipmentReservation(
        user_id=current_user.id,
        equipment_id=equipment_id,
        start_time=start_time,
        duration_minutes=duration_minutes,
        queue_position=queue_position
    )

    db.session.add(new_reservation)
    db.session.commit()

    if queue_position == 0:
        flash('Equipment reserved! You can use it now.', 'success')
    else:
        flash(f'You are in queue position {queue_position}. Estimated start time: {start_time.strftime("%H:%M")}',
              'success')

    return redirect(url_for('gym.my_reservations'))


def calculate_equipment_available_time(equipment_id):
    current_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment_id,
        status='active',
        queue_position=0
    ).first()

    if not current_reservation:
        return datetime.now()

    last_in_queue = EquipmentReservation.query.filter_by(
        equipment_id=equipment_id,
        status='active'
    ).order_by(desc(EquipmentReservation.queue_position)).first()

    if last_in_queue:
        return last_in_queue.end_time + timedelta(minutes=1)
    else:
        return current_reservation.end_time + timedelta(minutes=1)


@gym_bp.route('/reservations', methods=['GET'])
@login_required
def my_reservations():
    check_and_update_reservations()

    active_reservations = EquipmentReservation.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).order_by(EquipmentReservation.queue_position).all()

    equipment_map = {}
    for reservation in active_reservations:
        equipment = Equipment.query.get(reservation.equipment_id)
        equipment_map[reservation.equipment_id] = equipment

    now = datetime.now()

    return render_template(
        'gym/my_reservations.html',
        reservations=active_reservations,
        equipment_map=equipment_map,
        now=now
    )


@gym_bp.route('/reservation-history')
@login_required
def reservation_history():
    history_reservations = EquipmentReservation.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).order_by(EquipmentReservation.end_time.desc()).all()

    equipment_map = {}
    for reservation in history_reservations:
        equipment = Equipment.query.get(reservation.equipment_id)
        equipment_map[reservation.equipment_id] = equipment

    total_time = sum(res.duration_minutes for res in history_reservations)
    total_sessions = len(history_reservations)

    total_calories = calculate_total_calories_for_reservations(history_reservations, equipment_map)

    reservation_calorie_breakdown = {}
    for reservation in history_reservations:
        if reservation.equipment_id in equipment_map:
            equipment_name = equipment_map[reservation.equipment_id].name
            calories = calculate_calories_for_reservation(equipment_name, reservation.duration_minutes)
            reservation_calorie_breakdown[reservation.id] = calories

    day_calorie_breakdown = {}
    for reservation in history_reservations:
        date_key = reservation.end_time.date()
        if reservation.equipment_id in equipment_map:
            equipment_name = equipment_map[reservation.equipment_id].name
            calories = calculate_calories_for_reservation(equipment_name, reservation.duration_minutes)

            if date_key in day_calorie_breakdown:
                day_calorie_breakdown[date_key] += calories
            else:
                day_calorie_breakdown[date_key] = calories

    equipment_usage = {}
    for reservation in history_reservations:
        equipment_name = equipment_map[reservation.equipment_id].name
        if equipment_name in equipment_usage:
            equipment_usage[equipment_name] += reservation.duration_minutes
        else:
            equipment_usage[equipment_name] = reservation.duration_minutes

    most_used_equipment = max(equipment_usage.items(), key=lambda x: x[1])[0] if equipment_usage else None

    grouped_reservations = {}
    for reservation in history_reservations:
        date_key = reservation.end_time.date()
        if date_key not in grouped_reservations:
            grouped_reservations[date_key] = []
        grouped_reservations[date_key].append(reservation)

    sorted_dates = sorted(grouped_reservations.keys(), reverse=True)

    return render_template(
        'gym/reservation_history.html',
        history_reservations=history_reservations,
        equipment_map=equipment_map,
        total_time=total_time,
        total_sessions=total_sessions,
        total_calories=total_calories,
        reservation_calorie_breakdown=reservation_calorie_breakdown,
        day_calorie_breakdown=day_calorie_breakdown,
        most_used_equipment=most_used_equipment,
        grouped_reservations=grouped_reservations,
        sorted_dates=sorted_dates
    )


@gym_bp.route('/reservations/<int:reservation_id>/cancel', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    reservation = EquipmentReservation.query.get_or_404(reservation_id)

    if reservation.user_id != current_user.id:
        flash('You do not have permission to cancel this reservation', 'danger')
        return redirect(url_for('gym.my_reservations'))

    reservation.status = 'cancelled'

    if reservation.queue_position == 0:
        equipment = Equipment.query.get(reservation.equipment_id)
        equipment.is_available = True

        next_reservation = EquipmentReservation.query.filter_by(
            equipment_id=reservation.equipment_id,
            status='active',
            queue_position=1
        ).first()

        if next_reservation:
            next_reservation.queue_position = 0
            next_reservation.start_time = datetime.now()
            next_reservation.end_time = datetime.now() + timedelta(minutes=next_reservation.duration_minutes)
            equipment.is_available = False

            update_queue_after_cancellation(reservation.equipment_id, next_reservation)
    else:
        update_queue_after_cancellation(reservation.equipment_id, None, reservation.queue_position)

    db.session.commit()
    flash('Reservation cancelled successfully', 'success')
    return redirect(url_for('gym.my_reservations'))


def update_queue_after_cancellation(equipment_id, new_active_reservation, cancelled_position=None):

    if new_active_reservation:
        queued_reservations = EquipmentReservation.query.filter(
            EquipmentReservation.equipment_id == equipment_id,
            EquipmentReservation.status == 'active',
            EquipmentReservation.queue_position > 1
        ).order_by(EquipmentReservation.queue_position).all()

        for queued in queued_reservations:
            queued.queue_position -= 1

        recalculate_queue_times(equipment_id)

    elif cancelled_position:
        queued_reservations = EquipmentReservation.query.filter(
            EquipmentReservation.equipment_id == equipment_id,
            EquipmentReservation.status == 'active',
            EquipmentReservation.queue_position > cancelled_position
        ).order_by(EquipmentReservation.queue_position).all()

        for queued in queued_reservations:
            queued.queue_position -= 1

        recalculate_queue_times(equipment_id)


def recalculate_queue_times(equipment_id):

    current_reservation = EquipmentReservation.query.filter_by(
        equipment_id=equipment_id,
        status='active',
        queue_position=0
    ).first()

    if not current_reservation:
        return

    queued_reservations = EquipmentReservation.query.filter(
        EquipmentReservation.equipment_id == equipment_id,
        EquipmentReservation.status == 'active',
        EquipmentReservation.queue_position > 0
    ).order_by(EquipmentReservation.queue_position).all()

    previous_end_time = current_reservation.end_time

    for reservation in queued_reservations:
        reservation.start_time = previous_end_time + timedelta(minutes=1)
        reservation.end_time = reservation.start_time + timedelta(minutes=reservation.duration_minutes)
        previous_end_time = reservation.end_time


@gym_bp.route('/reservations/<int:reservation_id>/update', methods=['POST'])
@login_required
def update_reservation(reservation_id):
    reservation = EquipmentReservation.query.get_or_404(reservation_id)

    if reservation.user_id != current_user.id:
        flash('You do not have permission to update this reservation', 'danger')
        return redirect(url_for('gym.my_reservations'))

    new_duration = int(request.form.get('duration', reservation.duration_minutes))

    if reservation.update_duration(new_duration):
        if reservation.queue_position == 0:
            recalculate_queue_times(reservation.equipment_id)

        db.session.commit()
        flash('Reservation updated successfully', 'success')
    else:
        flash('You can only decrease the duration of your reservation', 'warning')

    return redirect(url_for('gym.my_reservations'))


def update_queue_times(equipment_id, starting_position=1):
    queued_reservations = EquipmentReservation.query.filter(
        EquipmentReservation.equipment_id == equipment_id,
        EquipmentReservation.status == 'active',
        EquipmentReservation.queue_position >= starting_position
    ).order_by(EquipmentReservation.queue_position).all()

    for i, reservation in enumerate(queued_reservations):
        if i == 0 and starting_position == 1:
            current = EquipmentReservation.query.filter_by(
                equipment_id=equipment_id,
                status='active',
                queue_position=0
            ).first()
            if current:
                reservation.start_time = current.end_time + timedelta(minutes=1)
        elif i > 0:
            reservation.start_time = queued_reservations[i - 1].end_time + timedelta(minutes=1)

        reservation.end_time = reservation.start_time + timedelta(minutes=reservation.duration_minutes)


def check_and_update_reservations():
    now = datetime.now()

    expired_reservations = EquipmentReservation.query.filter(
        EquipmentReservation.status == 'active',
        EquipmentReservation.queue_position == 0,
        EquipmentReservation.end_time < now
    ).all()

    for reservation in expired_reservations:
        reservation.status = 'completed'

        equipment = Equipment.query.get(reservation.equipment_id)
        if equipment:
            equipment.is_available = True

        next_reservation = EquipmentReservation.query.filter_by(
            equipment_id=reservation.equipment_id,
            status='active',
            queue_position=1
        ).first()

        if next_reservation:
            next_reservation.queue_position = 0
            next_reservation.start_time = now
            next_reservation.end_time = now + timedelta(minutes=next_reservation.duration_minutes)

            if equipment:
                equipment.is_available = False

            queued_reservations = EquipmentReservation.query.filter(
                EquipmentReservation.equipment_id == reservation.equipment_id,
                EquipmentReservation.status == 'active',
                EquipmentReservation.queue_position > 1
            ).order_by(EquipmentReservation.queue_position).all()

            for queued in queued_reservations:
                queued.queue_position -= 1

            recalculate_queue_times(reservation.equipment_id)

    equipments = Equipment.query.filter_by(is_available=False).all()
    for equipment in equipments:
        active_reservation = EquipmentReservation.query.filter_by(
            equipment_id=equipment.id,
            status='active',
            queue_position=0
        ).first()

        if not active_reservation:
            equipment.is_available = True

            next_in_queue = EquipmentReservation.query.filter_by(
                equipment_id=equipment.id,
                status='active',
                queue_position=1
            ).first()

            if next_in_queue and now >= next_in_queue.start_time:
                next_in_queue.queue_position = 0
                next_in_queue.start_time = now
                next_in_queue.end_time = now + timedelta(minutes=next_in_queue.duration_minutes)
                equipment.is_available = False

                queued_reservations = EquipmentReservation.query.filter(
                    EquipmentReservation.equipment_id == equipment.id,
                    EquipmentReservation.status == 'active',
                    EquipmentReservation.queue_position > 1
                ).all()

                for queued in queued_reservations:
                    queued.queue_position -= 1

                recalculate_queue_times(equipment.id)

    db.session.commit()


@gym_bp.route('/equipment/scan', methods=['GET'])
@login_required
def scan_equipment_qr():
    return render_template('gym/equipment_scan.html')