from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.db import db
from models.user import User
from models.equipment import Equipment
from models.equipment_reservation import EquipmentReservation
from models.presence import Presence
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import uuid
import os
import qrcode

admin_bp = Blueprint('admin', __name__)


def admin_required(func):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page', 'danger')
            return redirect(url_for('main.dashboard'))
        return func(*args, **kwargs)

    decorated_function.__name__ = func.__name__
    return decorated_function


@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    user_count = User.query.filter_by(is_admin=False).count()
    equipment_count = Equipment.query.count()
    active_reservations = EquipmentReservation.query.filter_by(status='active').count()
    current_occupancy = Presence.get_occupancy_percentage()
    return render_template(
        'admin/dashboard.html',
        user_count=user_count,
        equipment_count=equipment_count,
        active_reservations=active_reservations,
        current_occupancy=current_occupancy,
        gym_occupancy=current_occupancy
    )


@admin_bp.route('/equipment')
@login_required
@admin_required
def manage_equipment():
    equipment_list = Equipment.query.all()
    return render_template('admin/equipment.html', equipment_list=equipment_list)


@admin_bp.route('/equipment/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_equipment():
    if request.method == 'POST':
        name = request.form.get('name')
        qr_code = f"equipment_{uuid.uuid4().hex[:10]}"
        new_equipment = Equipment(
            name=name,
            description='',
            location='',
            qr_code=qr_code
        )
        db.session.add(new_equipment)
        db.session.commit()
        generate_qr_code(qr_code)
        flash('Equipment created successfully', 'success')
        return redirect(url_for('admin.manage_equipment'))
    return render_template('admin/create_equipment.html')


@admin_bp.route('/equipment/<int:equipment_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_equipment(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    if request.method == 'POST':
        equipment.name = request.form.get('name')
        equipment.description = ''
        equipment.location = ''
        db.session.commit()
        flash('Equipment updated successfully', 'success')
        return redirect(url_for('admin.manage_equipment'))
    return render_template('admin/edit_equipment.html', equipment=equipment)


@admin_bp.route('/equipment/<int:equipment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_equipment(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    active_reservations = EquipmentReservation.query.filter_by(
        equipment_id=equipment_id,
        status='active'
    ).count()
    if active_reservations > 0:
        flash('Cannot delete equipment with active reservations', 'danger')
        return redirect(url_for('admin.manage_equipment'))
    db.session.delete(equipment)
    db.session.commit()
    flash('Equipment deleted successfully', 'success')
    return redirect(url_for('admin.manage_equipment'))


@admin_bp.route('/equipment/<int:equipment_id>/qr', methods=['GET'])
@login_required
@admin_required
def view_equipment_qr(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    qr_filename = f"{equipment.qr_code}.png"
    qr_path = os.path.join('static', 'qrcodes', qr_filename)
    if not os.path.exists(qr_path):
        generate_qr_code(equipment.qr_code)
    return render_template('admin/view_qr.html', equipment=equipment, qr_filename=qr_filename)


@admin_bp.route('/reservations')
@login_required
@admin_required
def manage_reservations():
    status = request.args.get('status', 'all')
    date_filter = request.args.get('date_filter', 'all')
    custom_date = request.args.get('custom_date', '')

    query = EquipmentReservation.query

    if status == 'active':
        query = query.filter_by(status='active')
    elif status == 'completed':
        query = query.filter_by(status='completed')
    elif status == 'cancelled':
        query = query.filter_by(status='cancelled')

    now = datetime.utcnow()

    if date_filter == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        query = query.filter(EquipmentReservation.created_at >= start_date,
                             EquipmentReservation.created_at < end_date)

    elif date_filter == 'week':
        days_since_monday = now.weekday()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=7)
        query = query.filter(EquipmentReservation.created_at >= start_date,
                             EquipmentReservation.created_at < end_date)

    elif date_filter == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end_date = start_date.replace(year=now.year + 1, month=1)
        else:
            end_date = start_date.replace(month=now.month + 1)
        query = query.filter(EquipmentReservation.created_at >= start_date,
                             EquipmentReservation.created_at < end_date)

    elif date_filter == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(year=now.year + 1)
        query = query.filter(EquipmentReservation.created_at >= start_date,
                             EquipmentReservation.created_at < end_date)

    elif date_filter == 'custom' and custom_date:
        try:
            selected_date = datetime.strptime(custom_date, '%Y-%m-%d')
            start_date = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            query = query.filter(EquipmentReservation.created_at >= start_date,
                                 EquipmentReservation.created_at < end_date)
        except ValueError:
            pass

    reservations = query.order_by(EquipmentReservation.created_at.desc()).all()

    users = {user.id: user for user in User.query.all()}
    equipment = {eq.id: eq for eq in Equipment.query.all()}

    total_reservations = len(reservations)
    active_count = sum(1 for r in reservations if r.status == 'active')
    completed_count = sum(1 for r in reservations if r.status == 'completed')
    cancelled_count = sum(1 for r in reservations if r.status == 'cancelled')

    return render_template(
        'admin/reservations.html',
        reservations=reservations,
        users=users,
        equipment=equipment,
        status=status,
        date_filter=date_filter,
        custom_date=custom_date,
        total_reservations=total_reservations,
        active_count=active_count,
        completed_count=completed_count,
        cancelled_count=cancelled_count
    )


@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/presence')
@login_required
@admin_required
def view_presence():
    active_presences = Presence.query.filter_by(is_present=True).all()
    users = {user.id: user for user in User.query.all()}
    return render_template('admin/presence.html', presences=active_presences, users=users)


@admin_bp.route('/generate-qr-codes', methods=['GET'])
@login_required
@admin_required
def generate_qr_codes():
    entry_qr = 'gym_entry_qrcode'
    exit_qr = 'gym_exit_qrcode'
    generate_qr_code(entry_qr)
    generate_qr_code(exit_qr)
    return render_template('admin/gym_qr_codes.html', entry_qr=entry_qr, exit_qr=exit_qr)


@admin_bp.route('/equipment-analytics')
@login_required
@admin_required
def equipment_analytics():
    period = request.args.get('period', 'weekly')
    sort_by = request.args.get('sort_by', 'hours')

    equipment_list = Equipment.query.all()
    now = datetime.utcnow()

    if period == 'weekly':
        start_date = now - timedelta(days=7)
        period_name = "Last 7 Days"
    elif period == 'monthly':
        start_date = now - timedelta(days=30)
        period_name = "Last 30 Days"
    elif period == 'yearly':
        start_date = now - timedelta(days=365)
        period_name = "Last 365 Days"
    else:
        start_date = now - timedelta(days=7)
        period_name = "Last 7 Days"
        period = 'weekly'

    equipment_stats = []

    for equipment in equipment_list:
        reservations = EquipmentReservation.query.filter(
            EquipmentReservation.equipment_id == equipment.id,
            EquipmentReservation.status == 'completed',
            EquipmentReservation.end_time >= start_date
        ).all()

        total_sessions = len(reservations)
        total_hours = sum(res.duration_minutes for res in reservations) / 60.0

        avg_duration = (sum(res.duration_minutes for res in reservations) / len(reservations)) if reservations else 0

        equipment_stats.append({
            'equipment': equipment,
            'total_sessions': total_sessions,
            'total_hours': round(total_hours, 1),
            'avg_duration': round(avg_duration, 1)
        })

    if sort_by == 'sessions':
        equipment_stats.sort(key=lambda x: x['total_sessions'], reverse=True)
    elif sort_by == 'duration':
        equipment_stats.sort(key=lambda x: x['avg_duration'], reverse=True)
    else:
        equipment_stats.sort(key=lambda x: x['total_hours'], reverse=True)

    total_sessions_all = sum(stat['total_sessions'] for stat in equipment_stats)
    total_hours_all = sum(stat['total_hours'] for stat in equipment_stats)

    return render_template('admin/equipment_analytics.html',
                           equipment_stats=equipment_stats,
                           period=period,
                           period_name=period_name,
                           sort_by=sort_by,
                           total_sessions_all=total_sessions_all,
                           total_hours_all=round(total_hours_all, 1))


def generate_qr_code(data):
    qr_dir = os.path.join('static', 'qrcodes')
    if not os.path.exists(qr_dir):
        os.makedirs(qr_dir)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    filename = f"{data}.png"
    filepath = os.path.join(qr_dir, filename)
    img.save(filepath)