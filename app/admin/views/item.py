import json
import os
import uuid
from flask import render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import Item, Category, User, Order
from app.utils import admin_required, log_admin_action, allowed_file, validate_file_content
from app.admin import bp

@bp.route('/items')
@login_required
@admin_required
def items():
    status_filter = request.args.get('status', '')
    query = Item.query
    if status_filter in ['on_sale', 'off_sale', 'pending_review']:
        query = query.filter_by(status=status_filter)
    items = query.order_by(Item.created_at.desc()).all()
    return render_template('admin/items.html', items=items, status_filter=status_filter)

@bp.route('/item/add', methods=['GET', 'POST'])
@login_required
@admin_required
def item_add():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        seller_id = request.form.get('seller_id')
        category_id = request.form.get('category_id')
        allow_bargain = request.form.get('allow_bargain') == 'on'
        file = request.files.get('image')
        
        # 主图处理
        if file and allowed_file(file.filename):
            original_name = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
            image_url = f"/static/uploads/{unique_name}"
        else:
            image_url = 'https://via.placeholder.com/300x200?text=No+Image'
        
        # 细节图处理
        detail_files = request.files.getlist('detail_images')
        detail_urls = []
        for f in detail_files:
            if f and allowed_file(f.filename) and validate_file_content(f):
                original_name = secure_filename(f.filename)
                unique_name = f"{uuid.uuid4().hex}_{original_name}"
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
                detail_urls.append(f"/static/uploads/{unique_name}")
        detail_images_json = json.dumps(detail_urls) if detail_urls else ''
        
        # 校验
        if not title or not price:
            flash('标题和价格不能为空', 'danger')
            return redirect(url_for('admin.item_add'))
        try:
            price = float(price)
        except:
            flash('价格必须是数字', 'danger')
            return redirect(url_for('admin.item_add'))
        
        seller = User.query.get(int(seller_id)) if seller_id else current_user
        if seller_id and not seller:
            flash('卖家不存在', 'danger')
            return redirect(url_for('admin.item_add'))
        
        quantity = request.form.get('quantity', 1)
        try:
            quantity = max(1, int(quantity))
        except:
            quantity = 1

        condition = request.form.get('condition', '').strip()
        # 未选成色 → pending_review，选了成色 → on_sale
        item_status = 'on_sale' if condition else 'pending_review'
        
        item = Item(title=title, description=description, price=price,
                    image_url=image_url, detail_images=detail_images_json,
                    seller_id=seller.id, status=item_status,
                    category_id=int(category_id) if category_id else None,
                    allow_bargain=allow_bargain,
                    quantity=quantity,
                    condition=condition if condition else None)
        db.session.add(item)
        db.session.commit()
        log_admin_action('添加商品', 'item', item.id, f'商品标题：{title}')
        flash('物品添加成功', 'success')
        return redirect(url_for('admin.items'))
    
    # GET 请求
    users = User.query.all()
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template('admin/item_form.html', item=None, users=users, detail_images=[], categories=categories)

@bp.route('/item/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def item_edit(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == 'POST':
        old_title = item.title
        item.title = request.form.get('title')
        item.description = request.form.get('description')
        try:
            item.price = float(request.form.get('price'))
        except:
            flash('价格必须是数字', 'danger')
            return redirect(url_for('admin.item_edit', item_id=item_id))
        item.allow_bargain = request.form.get('allow_bargain') == 'on'
        
        # 成色处理
        condition = request.form.get('condition', '').strip()
        item.condition = condition if condition else None
        
        # 库存
        quantity = request.form.get('quantity', 1)
        try:
            item.quantity = max(1, int(quantity))
        except:
            item.quantity = 1
        
        # 主图处理
        file = request.files.get('image')
        if file and allowed_file(file.filename) and validate_file_content(file):
            if item.image_url and not item.image_url.startswith('https://'):
                old_path = os.path.join(current_app.root_path, item.image_url.lstrip('/'))
                if os.path.exists(old_path):
                    os.remove(old_path)
            original_name = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
            item.image_url = f"/static/uploads/{unique_name}"
        
        # 细节图处理
        keep_images = request.form.getlist('keep_images')
        old_detail = []
        if item.detail_images:
            try:
                old_detail = json.loads(item.detail_images)
                # 确保 old_detail 是列表且元素都是字符串
                if not isinstance(old_detail, list):
                    old_detail = []
                else:
                    old_detail = [url for url in old_detail if isinstance(url, str) and url]
            except (json.JSONDecodeError, TypeError):
                old_detail = []
        
        for url in old_detail:
            if url not in keep_images:
                file_path = os.path.join(current_app.root_path, url.lstrip('/'))
                if os.path.exists(file_path):
                    os.remove(file_path)
        new_files = request.files.getlist('detail_images')
        new_urls = []
        for f in new_files:
            if f and allowed_file(f.filename) and validate_file_content(f):
                original_name = secure_filename(f.filename)
                unique_name = f"{uuid.uuid4().hex}_{original_name}"
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
                new_urls.append(f"/static/uploads/{unique_name}")
        final_detail = keep_images + new_urls
        item.detail_images = json.dumps(final_detail) if final_detail else ''
        
        # 其他字段
        seller_id = request.form.get('seller_id')
        if seller_id:
            seller = User.query.get(int(seller_id))
            if seller:
                item.seller_id = seller.id
        category_id = request.form.get('category_id')
        item.category_id = int(category_id) if category_id else None
        status = request.form.get('status')
        item.status = status if status else 'on_sale'
        db.session.commit()
        log_admin_action('编辑商品', 'item', item.id, f'原标题：{old_title} -> {item.title}')
        flash('物品信息已更新', 'success')
        return redirect(url_for('admin.items'))
    
    users = User.query.all()
    detail_images = json.loads(item.detail_images) if item.detail_images else []
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template('admin/item_form.html', item=item, users=users, detail_images=detail_images, categories=categories)

@bp.route('/item/toggle/<int:item_id>')
@login_required
@admin_required
def item_toggle(item_id):
    item = Item.query.get_or_404(item_id)
    old_status = item.status
    item.status = 'off_sale' if item.status == 'on_sale' else 'on_sale'
    db.session.commit()
    log_admin_action('切换商品状态', 'item', item.id, f'从 {old_status} 改为 {item.status}')
    flash(f'物品已{"下架" if item.status == "off_sale" else "上架"}', 'success')
    return redirect(url_for('admin.items'))

@bp.route('/item/feature/<int:item_id>')
@login_required
@admin_required
def item_feature(item_id):
    item = Item.query.get_or_404(item_id)
    item.is_featured = not item.is_featured
    db.session.commit()
    action = '推荐' if item.is_featured else '取消推荐'
    log_admin_action(f'{action}商品', 'item', item.id, f'商品标题：{item.title}')
    flash(f'已{action}该商品', 'success')
    return redirect(url_for('admin.items'))

@bp.route('/item/delete/<int:item_id>')
@login_required
@admin_required
def item_delete(item_id):
    item = Item.query.get_or_404(item_id)
    active_orders = Order.query.filter_by(item_id=item_id).filter(Order.status.in_(['pending', 'submitted', 'paid', 'shipped'])).first()
    if active_orders:
        flash('该物品有未完成的订单，无法删除', 'danger')
    else:
        title = item.title
        if item.image_url and not item.image_url.startswith('https://'):
            file_path = os.path.join(current_app.root_path, item.image_url.lstrip('/'))
            if os.path.exists(file_path):
                os.remove(file_path)
        if item.detail_images:
            detail_urls = json.loads(item.detail_images)
            for url in detail_urls:
                file_path = os.path.join(current_app.root_path, url.lstrip('/'))
                if os.path.exists(file_path):
                    os.remove(file_path)
        db.session.delete(item)
        db.session.commit()
        log_admin_action('删除商品', 'item', item.id, f'商品标题：{title}')
        flash('物品已删除', 'success')
    return redirect(url_for('admin.items'))


@bp.route('/approve-item/<int:item_id>', methods=['POST'])
@login_required
def approve_item(item_id):
    """超级管理员审核通过商品（pending_review → on_sale）"""
    if current_user.role != 'super_admin':
        flash('仅超级管理员可审核商品', 'danger')
        return redirect(url_for('admin.items'))
    item = Item.query.get_or_404(item_id)
    if item.status != 'pending_review':
        flash('该商品无需审核', 'warning')
        return redirect(url_for('admin.items'))
    item.status = 'on_sale'
    db.session.commit()
    log_admin_action('审核通过商品', 'item', item.id, f'商品标题：{item.title}，status: pending_review → on_sale')
    flash(f'商品"{item.title}"已审核通过，已上架', 'success')
    return redirect(url_for('admin.items'))