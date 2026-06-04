from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models import Order, User, AdminReadStatus
from app.utils import admin_required, log_admin_action, send_notification
from app.admin import bp

@bp.route('/orders')
@login_required
@admin_required
def orders():
    # 标记订单已读
    record = AdminReadStatus.query.filter_by(admin_id=current_user.id, module='order').first()
    if record:
        record.last_read_time = datetime.utcnow()
    else:
        record = AdminReadStatus(admin_id=current_user.id, module='order', last_read_time=datetime.utcnow())
        db.session.add(record)
    db.session.commit()

    page = request.args.get('page', 1, type=int)
    per_page = 20
    status_filter = request.args.get('status', '')
    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    query = query.order_by(Order.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items
    return render_template('admin/orders.html', orders=orders, status_filter=status_filter, pagination=pagination)

@bp.route('/order/update/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def order_update(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    old_status = order.status
    if new_status == 'cancelled':
        order.item.quantity += 1
        if order.item.status == 'off_sale':
            order.item.status = 'on_sale'
        send_notification(order.buyer_id, '订单已取消', f'管理员取消了您的订单 {order.order_number}。')
    elif new_status in ['paid', 'completed'] and old_status == 'submitted':
        send_notification(order.buyer_id, '订单已确认', f'您的订单 {order.order_number} 已确认付款，等待发货。')
    elif new_status in ['paid', 'completed'] and old_status == 'pending':
        order.item.quantity -= 1
        if order.item.quantity <= 0:
            order.item.status = 'off_sale'
        send_notification(order.buyer_id, '订单已收款', f'您的订单 {order.order_number} 已收款成功。')
    order.status = new_status
    db.session.commit()
    log_admin_action('更新订单状态', 'order', order.id, f'订单号：{order.order_number}，从 {old_status} 改为 {new_status}')
    flash('订单状态已更新', 'success')
    return redirect(url_for('admin.orders'))

@bp.route('/order/delete/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    order_number = order.order_number
    if order.status == 'cancelled' or order.status == 'pending':
        if order.item.status == 'off_sale':
            order.item.status = 'on_sale'
    elif order.status in ['submitted', 'paid', 'shipped']:
        order.item.quantity += 1
        if order.item.status == 'off_sale':
            order.item.status = 'on_sale'
    db.session.delete(order)
    db.session.commit()
    log_admin_action('删除订单', 'order', order_id, f'订单号：{order_number}')
    flash('订单已永久删除，对应商品已重新上架', 'success')
    return redirect(url_for('admin.orders'))