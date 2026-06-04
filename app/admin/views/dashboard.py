import json
import os
from flask import render_template, jsonify, request, abort, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import User, Item, Order, Category, Feedback, AdminReadStatus
from app.utils import admin_required, log_admin_action, validate_file_content
from .. import bp

@bp.route('/')
@login_required
@admin_required
def dashboard():
    total_items = Item.query.count()
    on_sale_items = Item.query.filter_by(status='on_sale').count()
    total_orders = Order.query.count()
    pending_submitted_orders = Order.query.filter(Order.status.in_(['pending', 'submitted'])).count()
    shipped_orders = Order.query.filter_by(status='paid').count()
    completed_orders = Order.query.filter_by(status='completed').count()

    # 获取管理员最后查看订单的时间
    last_order_read = AdminReadStatus.query.filter_by(admin_id=current_user.id, module='order').first()
    last_order_time = last_order_read.last_read_time if last_order_read else datetime(1970, 1, 1)
    # 新订单数量（创建时间 > 最后查看时间）
    new_orders_count = Order.query.filter(Order.created_at > last_order_time).count()

    # 新反馈数量
    last_feedback_read = AdminReadStatus.query.filter_by(admin_id=current_user.id, module='feedback').first()
    last_feedback_time = last_feedback_read.last_read_time if last_feedback_read else datetime(1970, 1, 1)
    new_feedback_count = Feedback.query.filter(Feedback.created_at > last_feedback_time).count()

    # 订单各状态数量（用于下拉菜单显示）
    order_counts = {
        'all': total_orders,
        'pending': Order.query.filter_by(status='pending').count(),
        'submitted': Order.query.filter_by(status='submitted').count(),
        'paid': Order.query.filter_by(status='paid').count(),
        'shipped': Order.query.filter_by(status='shipped').count(),
        'completed': Order.query.filter_by(status='completed').count(),
    }

    return render_template('admin/dashboard.html',
                           total_items=total_items,
                           on_sale_items=on_sale_items,
                           total_orders=total_orders,
                           pending_submitted_orders=pending_submitted_orders,
                           shipped_orders=shipped_orders,
                           completed_orders=completed_orders,
                           order_counts=order_counts,
                           new_orders_count=new_orders_count,
                           pending_feedback_count=new_feedback_count)

@bp.route('/stats')
@login_required
@admin_required
def stats():
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)
    order_stats = db.session.query(db.func.date(Order.created_at).label('date'),
                                   db.func.count(Order.id).label('count'),
                                   db.func.sum(Order.total_price).label('amount')
                                  ).filter(Order.created_at >= start_date).group_by(db.func.date(Order.created_at)).all()
    hot_items = db.session.query(Item.id, Item.title, db.func.count(Order.id).label('sale_count')
                                ).join(Order, Order.item_id == Item.id).group_by(Item.id).order_by(db.desc(db.func.count(Order.id))).limit(10).all()
    category_stats = db.session.query(Category.name, db.func.count(Item.id).label('item_count')
                                     ).outerjoin(Item, Item.category_id == Category.id).group_by(Category.name).all()
    return jsonify({
        'order_trend': [{'date': str(row.date), 'count': row.count, 'amount': float(row.amount or 0)} for row in order_stats],
        'hot_items': [{'id': row.id, 'title': row.title, 'sale_count': row.sale_count} for row in hot_items],
        'category_stats': [{'name': row.name or '未分类', 'item_count': row.item_count} for row in category_stats]
    })

@bp.route('/mark-orders-read', methods=['POST'])
@login_required
@admin_required
def mark_orders_read():
    record = AdminReadStatus.query.filter_by(admin_id=current_user.id, module='order').first()
    if record:
        record.last_read_time = datetime.utcnow()
    else:
        record = AdminReadStatus(admin_id=current_user.id, module='order', last_read_time=datetime.utcnow())
        db.session.add(record)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/mark-feedback-read', methods=['POST'])
@login_required
@admin_required
def mark_feedback_read():
    record = AdminReadStatus.query.filter_by(admin_id=current_user.id, module='feedback').first()
    if record:
        record.last_read_time = datetime.utcnow()
    else:
        record = AdminReadStatus(admin_id=current_user.id, module='feedback', last_read_time=datetime.utcnow())
        db.session.add(record)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/dashboard')
@login_required
@admin_required
def data_panel():
    """数据面板：仅超级管理员可见"""
    # 总览卡片
    total_users = User.query.count()
    total_items = Item.query.count()
    total_orders = Order.query.count()
    total_amount = db.session.query(func.coalesce(func.sum(Order.total_price), 0)).scalar()

    # 近30天数据范围
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=29)

    # 近30天每日新增订单数
    daily_orders = db.session.query(
        func.date(Order.created_at).label('date'),
        func.count(Order.id).label('count')
    ).filter(Order.created_at >= start_date).group_by(
        func.date(Order.created_at)
    ).order_by(func.date(Order.created_at)).all()

    date_map_orders = {str(row.date): row.count for row in daily_orders}
    daily_order_labels = []
    daily_order_data = []
    for i in range(30):
        d = start_date + timedelta(days=i)
        ds = d.strftime('%Y-%m-%d')
        daily_order_labels.append(ds)
        daily_order_data.append(date_map_orders.get(ds, 0))

    # 近30天每日交易额
    daily_amount = db.session.query(
        func.date(Order.created_at).label('date'),
        func.sum(Order.total_price).label('amount')
    ).filter(Order.created_at >= start_date).group_by(
        func.date(Order.created_at)
    ).order_by(func.date(Order.created_at)).all()

    amount_map = {str(row.date): float(row.amount or 0) for row in daily_amount}
    daily_amount_data = [amount_map.get(ds, 0) for ds in daily_order_labels]

    # 各分类商品数量占比
    category_stats = db.session.query(
        Category.name,
        func.count(Item.id).label('item_count')
    ).outerjoin(Item, Item.category_id == Category.id).group_by(Category.name).all()

    category_labels = [row.name or '未分类' for row in category_stats]
    category_data = [row.item_count for row in category_stats]

    # 订单状态分布
    statuses = ['cancelled', 'pending', 'submitted', 'paid', 'shipped', 'completed']
    status_labels = ['已取消', '待付款', '已提交', '已付款', '已发货', '已完成']
    status_colors = ['#6c757d', '#ffc107', '#17a2b8', '#007bff', '#6f42c1', '#28a745']
    status_data = [Order.query.filter_by(status=s).count() for s in statuses]

    chart_data = json.dumps({
        'daily_order_labels': daily_order_labels,
        'daily_order_data': daily_order_data,
        'daily_amount_data': daily_amount_data,
        'category_labels': category_labels,
        'category_data': category_data,
        'status_labels': status_labels,
        'status_data': status_data,
        'status_colors': status_colors,
    })

    return render_template('admin/data_panel.html',
                           total_users=total_users,
                           total_items=total_items,
                           total_orders=total_orders,
                           total_amount=total_amount,
                           chart_data=chart_data)


@bp.route('/upload-background', methods=['POST'])
@login_required
@admin_required
def upload_background():
    if not current_user.is_super_admin():
        abort(403)
    file = request.files.get('background')
    if not file or file.filename == '':
        return jsonify({'success': False, 'msg': '未选择文件'})
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        return jsonify({'success': False, 'msg': '仅支持 jpg/png/gif/webp 格式'})
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > 5 * 1024 * 1024:
        return jsonify({'success': False, 'msg': '文件大小不能超过 5MB'})
    bg_dir = os.path.join(current_app.static_folder, 'backgrounds')
    os.makedirs(bg_dir, exist_ok=True)
    bg_path = os.path.join(bg_dir, 'bg.jpg')
    file.save(bg_path)
    log_admin_action('上传背景图')
    return jsonify({'success': True, 'msg': '背景图上传成功，请刷新页面查看效果'})


@bp.route('/remove-background', methods=['POST'])
@login_required
@admin_required
def remove_background():
    if not current_user.is_super_admin():
        abort(403)
    bg_path = os.path.join(current_app.static_folder, 'backgrounds', 'bg.jpg')
    if os.path.exists(bg_path):
        os.remove(bg_path)
    log_admin_action('清除背景图')
    return jsonify({'success': True, 'msg': '背景图已清除，请刷新页面查看效果'})