from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Item, Bargain, Order
from app.utils import generate_order_number, utc_to_local, send_notification

@bp.route('/bargain/<int:item_id>', methods=['POST'])
@login_required
def bargain(item_id):
    item = Item.query.get_or_404(item_id)
    if not item.allow_bargain:
        flash('该商品不允许砍价', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    if item.seller_id == current_user.id:
        flash('不能对自己的商品砍价', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    offered_price = request.form.get('offered_price', type=float)
    if not offered_price or offered_price <= 0:
        flash('请输入有效价格', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    if offered_price >= item.price:
        flash('砍价金额不能大于等于商品原价', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    existing = Bargain.query.filter_by(item_id=item.id, buyer_id=current_user.id, status='pending').first()
    if existing:
        flash('您已提交过砍价请求，请等待卖家回复', 'danger')
        return redirect(url_for('main.item_detail', item_id=item.id))
    
    bargain = Bargain(item_id=item.id, buyer_id=current_user.id, offered_price=offered_price)
    db.session.add(bargain)
    db.session.commit()
    send_notification(item.seller_id, '新的砍价请求', f'用户 {current_user.student_id} 对您的商品 "{item.title}" 出价 ¥{offered_price}，请及时处理。')
    flash('砍价请求已发送，请等待卖家回复', 'success')
    return redirect(url_for('main.item_detail', item_id=item.id))

@bp.route('/bargain/respond/<int:bargain_id>', methods=['POST'])
@login_required
def respond_bargain(bargain_id):
    bargain = Bargain.query.get_or_404(bargain_id)
    item = bargain.item
    if item.seller_id != current_user.id:
        abort(403)
    action = request.form.get('action')
    if action == 'agree':
        if bargain.status != 'pending':
            flash('该砍价请求已经处理过了', 'danger')
            return redirect(url_for('main.seller_bargains'))
        existing_order = Order.query.filter_by(buyer_id=bargain.buyer_id, item_id=item.id, status='pending').first()
        if existing_order:
            flash('买家已有针对该商品的未完成订单，请勿重复创建', 'danger')
            return redirect(url_for('main.seller_bargains'))
        order_number = generate_order_number()
        while Order.query.filter_by(order_number=order_number).first():
            order_number = generate_order_number()
        order = Order(
            order_number=order_number,
            buyer_id=bargain.buyer_id,
            item_id=item.id,
            total_price=bargain.offered_price,
            status='pending'
        )
        db.session.add(order)
        bargain.status = 'agreed'
        db.session.commit()
        send_notification(bargain.buyer_id, '砍价成功订单已创建', f'卖家同意了您的砍价，已自动为您创建订单 {order_number}，请及时付款。')
        flash('已同意砍价，订单已自动创建', 'success')
    elif action == 'reject':
        if bargain.status != 'pending':
            flash('该砍价请求已经处理过了', 'danger')
            return redirect(url_for('main.seller_bargains'))
        bargain.status = 'rejected'
        db.session.commit()
        send_notification(bargain.buyer_id, '砍价被拒绝', f'卖家拒绝了您的出价 ¥{bargain.offered_price}。')
        flash('已拒绝砍价', 'success')
    else:
        flash('无效操作', 'danger')
    return redirect(url_for('main.seller_bargains'))

@bp.route('/bargain/reply/<int:bargain_id>', methods=['POST'])
@login_required
def bargain_reply(bargain_id):
    bargain = Bargain.query.get_or_404(bargain_id)
    item = bargain.item
    if item.seller_id != current_user.id:
        abort(403)
    reply_content = request.form.get('reply_content', '').strip()
    if reply_content:
        send_notification(bargain.buyer_id, '卖家回复了您的砍价', f'卖家对商品 "{item.title}" 的回复：{reply_content}')
        flash('回复已发送', 'success')
    else:
        flash('回复内容不能为空', 'danger')
    return redirect(url_for('main.seller_bargains'))

@bp.route('/my-bargains')
@login_required
def my_bargains():
    bargains = Bargain.query.filter_by(buyer_id=current_user.id).order_by(Bargain.created_at.desc()).all()
    for b in bargains:
        b.local_time = utc_to_local(b.created_at)
    return render_template('my_bargains.html', bargains=bargains)

@bp.route('/seller-bargains')
@login_required
def seller_bargains():
    bargains = Bargain.query.join(Item).filter(Item.seller_id == current_user.id).order_by(Bargain.created_at.desc()).all()
    for b in bargains:
        b.local_time = utc_to_local(b.created_at)
    return render_template('seller_bargains.html', bargains=bargains)