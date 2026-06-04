import json
from datetime import datetime, timedelta
from flask import render_template, request, flash, redirect, url_for, abort, jsonify
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Item, Order, Bargain, Setting
from app.utils import generate_order_number, utc_to_local, send_notification
from app.main import bp

# 直接购买
@bp.route('/buy/<int:item_id>', methods=['POST'])
@login_required
def buy_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.status != 'on_sale':
        flash('该商品已下架，无法购买', 'danger')
        return redirect(url_for('main.index'))
    if item.seller_id == current_user.id:
        flash('不能购买自己寄售的物品', 'warning')
        return redirect(url_for('main.item_detail', item_id=item_id))

    snapshot_data = {
        'title': item.title,
        'description': item.description,
        'price': item.price,
        'image_url': item.image_url,
        'seller_id': item.seller_id,
        'seller_name': item.seller.student_id
    }
    snapshot = json.dumps(snapshot_data, ensure_ascii=False)

    order_number = generate_order_number()
    while Order.query.filter_by(order_number=order_number).first():
        order_number = generate_order_number()
    order = Order(
        order_number=order_number,
        buyer_id=current_user.id,
        item_id=item.id,
        total_price=item.price,
        status='pending',
        snapshot=snapshot,
        buyer_note=request.form.get('buyer_note', '').strip()[:200] or None
    )
    db.session.add(order)
    buy_quantity = request.form.get('quantity', 1, type=int)
    if buy_quantity < 1 or buy_quantity > item.quantity:
        flash('购买数量无效', 'danger')
        return redirect(url_for('main.item_detail', item_id=item_id))
    item.quantity -= buy_quantity
    if item.quantity <= 0:
        item.status = 'off_sale'
    db.session.commit()
    flash(f'订单创建成功，订单号：{order_number}，请尽快付款（10分钟内未支付将自动取消）', 'success')
    return redirect(url_for('main.my_orders'))

# 按砍价价购买
@bp.route('/buy-with-bargain/<int:bargain_id>', methods=['POST'])
@login_required
def buy_with_bargain(bargain_id):
    bargain = Bargain.query.get_or_404(bargain_id)
    if bargain.buyer_id != current_user.id:
        abort(403)
    if bargain.status != 'agreed':
        flash('砍价已失效', 'danger')
        return redirect(url_for('main.item_detail', item_id=bargain.item_id))
    item = bargain.item
    if item.status != 'on_sale':
        flash('商品已下架', 'danger')
        return redirect(url_for('main.index'))

    snapshot_data = {
        'title': item.title,
        'description': item.description,
        'price': bargain.offered_price,
        'image_url': item.image_url,
        'seller_id': item.seller_id,
        'seller_name': item.seller.student_id,
        'bargain': True
    }
    snapshot = json.dumps(snapshot_data, ensure_ascii=False)

    order_number = generate_order_number()
    while Order.query.filter_by(order_number=order_number).first():
        order_number = generate_order_number()
    order = Order(
        order_number=order_number,
        buyer_id=current_user.id,
        item_id=item.id,
        total_price=bargain.offered_price,
        status='pending',
        snapshot=snapshot,
        buyer_note=request.form.get('buyer_note', '').strip()[:200] or None
    )
    db.session.add(order)
    buy_quantity = request.form.get('quantity', 1, type=int)
    if buy_quantity < 1 or buy_quantity > item.quantity:
        flash('购买数量无效', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    item.quantity -= buy_quantity
    if item.quantity <= 0:
        item.status = 'off_sale'
    db.session.commit()
    flash(f'订单创建成功，订单号：{order_number}，请尽快付款（10分钟内未支付将自动取消）', 'success')
    return redirect(url_for('main.my_orders'))

# 我的订单列表
@bp.route('/my-orders')
@login_required
def my_orders():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    query = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items
    # 转换为北京时间
    for order in orders:
        order.local_time = utc_to_local(order.created_at)
    admin_contact = Setting.get('admin_contact', 'admin@example.com')
    timeout_contact = Setting.get('timeout_contact', '订单超时未处理，请联系管理员：admin@example.com (请备注订单号)')
    now = datetime.utcnow()
    for order in orders:
        if order.status == 'submitted':
            time_diff = now - order.created_at
            order.is_timeout = time_diff > timedelta(hours=24)
        else:
            order.is_timeout = False
    return render_template('my_orders.html', orders=orders, admin_contact=admin_contact,
                           timeout_contact=timeout_contact, pagination=pagination)

# 订单详情
@bp.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id and not current_user.is_admin:
        abort(403)
    if order.snapshot:
        snapshot = json.loads(order.snapshot)
    else:
        item = order.item
        if item:
            snapshot = {
                'title': item.title,
                'description': item.description,
                'price': order.total_price,
                'image_url': item.image_url,
                'seller_name': item.seller.student_id
            }
        else:
            snapshot = {
                'title': '商品已删除',
                'description': '',
                'price': order.total_price,
                'image_url': '/static/images/default.png',
                'seller_name': '未知'
            }
    # 转换为北京时间
    order.local_time = utc_to_local(order.created_at)
    return render_template('order_detail.html', order=order, snapshot=snapshot)

# 取消订单
@bp.route('/cancel-order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id or order.status != 'pending':
        flash('无法取消该订单', 'danger')
        return redirect(url_for('main.profile'))
    item = order.item
    item.quantity += 1
    if item.status == 'off_sale':
        item.status = 'on_sale'
    order.status = 'cancelled'
    db.session.commit()
    send_notification(order.buyer_id, '订单已取消', f'您已取消订单 {order.order_number}，商品已重新上架。')
    flash('订单已取消，商品已重新上架', 'info')
    return redirect(url_for('main.profile'))

# 用户标记已支付（AJAX JSON 端点）
@bp.route('/mark-as-paid', methods=['POST'])
@login_required
def mark_as_paid():
    data = request.get_json()
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'success': False, 'message': '订单ID不能为空'})
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        return jsonify({'success': False, 'message': '无权操作此订单'})
    if order.status != 'pending':
        return jsonify({'success': False, 'message': '订单状态不是待付款，无法标记支付'})
    order.status = 'submitted'
    db.session.commit()
    send_notification(order.buyer_id, '支付请求已提交', f'您的订单 {order.order_number} 已提交支付请求，请等待管理员确认。')
    return jsonify({'success': True, 'message': '已提交支付请求，请等待管理员确认'})