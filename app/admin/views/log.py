from datetime import timedelta
from flask import render_template, request
from flask_login import login_required
from dateutil.parser import parse
from app import db
from app.models import AdminLog
from app.utils import admin_required, utc_to_local
from app.admin import bp

@bp.route('/logs')
@login_required
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    query = AdminLog.query
    admin_name = request.args.get('admin_name', '')
    action = request.args.get('action', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    if admin_name:
        # 转义 SQL LIKE 通配符
        safe_admin_name = admin_name.replace('%', '\\%').replace('_', '\\_')
        query = query.filter(AdminLog.admin_name.contains(safe_admin_name))
    if action:
        query = query.filter(AdminLog.action == action)
    if start_date:
        query = query.filter(AdminLog.created_at >= parse(start_date))
    if end_date:
        query = query.filter(AdminLog.created_at <= parse(end_date) + timedelta(days=1))
    pagination = query.order_by(AdminLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items
    for log in logs:
        log.local_time = utc_to_local(log.created_at)
    action_types = db.session.query(AdminLog.action).distinct().all()
    action_types = [a[0] for a in action_types]
    return render_template('admin/logs.html', logs=logs, pagination=pagination, action_types=action_types)

# 导出功能已移至 export.py 中，此处不再定义