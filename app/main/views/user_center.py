from flask import render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Setting, User, Order, Bargain, Blacklist, Feedback, PrivateMessage, Message, Item, Category, SearchHistory, BrowseHistory
from app.utils import utc_to_local, validate_file_content
from app.main import bp


@bp.route('/profile')
@login_required
def profile():
    # 我的订单
    orders = Order.query.filter_by(buyer_id=current_user.id)\
        .order_by(Order.created_at.desc()).all()
    for o in orders:
        o.local_time = utc_to_local(o.created_at)

    # 私信（收件箱）
    received_messages = PrivateMessage.query.filter_by(receiver_id=current_user.id)\
        .order_by(PrivateMessage.created_at.desc()).all()
    for msg in received_messages:
        msg.local_time = utc_to_local(msg.created_at)

    # 私信（发件箱）
    sent_messages = PrivateMessage.query.filter_by(sender_id=current_user.id)\
        .order_by(PrivateMessage.created_at.desc()).all()
    for msg in sent_messages:
        msg.local_time = utc_to_local(msg.created_at)

    # 我的砍价
    my_bargains = Bargain.query.filter_by(buyer_id=current_user.id)\
        .order_by(Bargain.created_at.desc()).all()
    for b in my_bargains:
        b.local_time = utc_to_local(b.created_at)

    # 黑名单
    blacklist = Blacklist.query.filter_by(user_id=current_user.id).all()
    for blk in blacklist:
        blk.local_time = utc_to_local(blk.created_at)

    # 我的反馈
    feedbacks = Feedback.query.filter_by(user_id=current_user.id)\
        .order_by(Feedback.created_at.desc()).all()

    # 系统消息
    sys_messages = Message.query.filter_by(receiver_id=current_user.id)\
        .order_by(Message.created_at.desc()).all()
    for msg in sys_messages:
        msg.local_time = utc_to_local(msg.created_at)

    # 搜索历史
    search_history = SearchHistory.query.filter_by(user_id=current_user.id)\
        .order_by(SearchHistory.searched_at.desc()).limit(50).all()
    for sh in search_history:
        sh.local_time = utc_to_local(sh.searched_at)

    # 浏览记录
    browse_history = BrowseHistory.query.filter_by(user_id=current_user.id)\
        .order_by(BrowseHistory.browsed_at.desc()).limit(30).all()
    for bh in browse_history:
        bh.local_time = utc_to_local(bh.browsed_at)

    # 售出统计（仅管理员可见，当前用户作为卖家的已完成订单）
    sales_stats = {
        'total_count': 0,
        'total_amount': 0,
        'avg_amount': 0,
        'cat_stats': [],
        'recent': []
    }
    if current_user.is_admin:
        from sqlalchemy import func
        completed_orders = Order.query.join(Item, Order.item_id == Item.id)\
            .filter(Item.seller_id == current_user.id, Order.status == 'completed')\
            .order_by(Order.created_at.desc()).all()

        total_sold = len(completed_orders)
        total_sold_amount = sum(o.total_price for o in completed_orders)
        avg_sold_amount = round(total_sold_amount / total_sold, 2) if total_sold > 0 else 0

        cat_stats = db.session.query(
            Category.name,
            func.count(Order.id).label('cnt'),
            func.sum(Order.total_price).label('amount')
        ).join(Item, Order.item_id == Item.id)\
         .join(Category, Item.category_id == Category.id)\
         .filter(Item.seller_id == current_user.id, Order.status == 'completed')\
         .group_by(Category.name).all()

        recent_sold = completed_orders[:5]
        for o in recent_sold:
            o.local_time = utc_to_local(o.created_at)

        sales_stats = {
            'total_count': total_sold,
            'total_amount': total_sold_amount,
            'avg_amount': avg_sold_amount,
            'cat_stats': cat_stats,
            'recent': recent_sold
        }

    admin_contact = Setting.get('admin_contact', 'admin@example.com')

    return render_template('user_center.html',
        orders=orders,
        received_messages=received_messages,
        sent_messages=sent_messages,
        my_bargains=my_bargains,
        blacklist=blacklist,
        feedbacks=feedbacks,
        sys_messages=sys_messages,
        search_history=search_history,
        browse_history=browse_history,
        sales_stats=sales_stats,
        admin_contact=admin_contact)


@bp.route('/profile/sales-stats')
@login_required
def sales_stats():
    from sqlalchemy import func
    # 所有售出订单（status='completed' 且 seller 是当前用户）
    completed_orders = Order.query.join(Item, Order.item_id == Item.id)\
        .filter(Item.seller_id == current_user.id, Order.status == 'completed')\
        .order_by(Order.created_at.desc()).all()

    total_count = len(completed_orders)
    total_amount = sum(o.total_price for o in completed_orders)
    avg_amount = round(total_amount / total_count, 2) if total_count > 0 else 0

    # 各分类售出数量
    cat_stats = db.session.query(
        Category.name,
        func.count(Order.id).label('cnt'),
        func.sum(Order.total_price).label('amount')
    ).join(Item, Order.item_id == Item.id)\
     .join(Category, Item.category_id == Category.id)\
     .filter(Item.seller_id == current_user.id, Order.status == 'completed')\
     .group_by(Category.name).all()

    # 最近5笔售出
    recent = completed_orders[:5]
    for o in recent:
        o.local_time = utc_to_local(o.created_at)

    stats = {
        'total_count': total_count,
        'total_amount': total_amount,
        'avg_amount': avg_amount,
        'cat_stats': cat_stats,
        'recent': recent
    }
    return render_template('sales_stats.html', stats=stats)


@bp.route('/profile/update-email', methods=['POST'])
@login_required
def update_email():
    new_email = request.form.get('email', '').strip()
    if not new_email:
        flash('邮箱不能为空', 'danger')
        return redirect(url_for('main.profile'))
    if '@' not in new_email or '.' not in new_email:
        flash('邮箱格式不正确', 'danger')
        return redirect(url_for('main.profile'))
    existing_user = User.query.filter(User.email == new_email, User.id != current_user.id).first()
    if existing_user:
        flash('该邮箱已被其他账号使用', 'danger')
        return redirect(url_for('main.profile'))
    current_user.email = new_email
    db.session.commit()
    flash('邮箱修改成功', 'success')
    return redirect(url_for('main.profile'))


@bp.route('/profile/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    import os
    from PIL import Image

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        return jsonify({'success': False, 'message': '仅支持 jpg/png/gif/webp'}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    if size > 16 * 1024 * 1024:
        return jsonify({'success': False, 'message': '文件不能超过 16MB'}), 400
    file.seek(0)

    avatars_dir = os.path.join(current_app.static_folder, 'avatars')
    os.makedirs(avatars_dir, exist_ok=True)

    img = Image.open(file)
    w, h = img.size
    size_sq = min(w, h)
    left = (w - size_sq) // 2
    top = (h - size_sq) // 2
    img = img.crop((left, top, left + size_sq, top + size_sq))
    img = img.resize((200, 200), Image.LANCZOS)

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    save_path = os.path.join(avatars_dir, f'user_{current_user.id}.jpg')
    img.save(save_path, 'JPEG', quality=70, optimize=True)

    for q in (50, 30, 10):
        if os.path.getsize(save_path) <= 16 * 1024 * 1024:
            break
        img.save(save_path, 'JPEG', quality=q, optimize=True)

    current_user.avatar = f'avatars/user_{current_user.id}.jpg'
    db.session.commit()

    return jsonify({
        'success': True,
        'avatar_url': url_for('static', filename=f'avatars/user_{current_user.id}.jpg')
    })


@bp.route('/privacy')
def privacy_policy():
    content = Setting.get('privacy_policy', '隐私政策内容未设置')
    return render_template('privacy.html', content=content)


@bp.route('/terms')
def service_terms():
    content = Setting.get('service_terms', '服务条款内容未设置')
    return render_template('terms.html', content=content)


@bp.route('/disclaimer')
def disclaimer():
    content = Setting.get('disclaimer', '免责声明内容未设置')
    return render_template('disclaimer.html', content=content)


@bp.route('/profile/clear-search-history', methods=['POST'])
@login_required
def clear_search_history():
    SearchHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('搜索历史已清除', 'success')
    return redirect(url_for('main.profile'))


@bp.route('/profile/clear-browse-history', methods=['POST'])
@login_required
def clear_browse_history():
    BrowseHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('浏览记录已清除', 'success')
    return redirect(url_for('main.profile'))