import json
import os
import uuid
from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import Draft, Category, Item, User
from app.utils import admin_required, log_admin_action, allowed_file, validate_file_content
from app.admin import bp   # 使用 admin 蓝图

@bp.route('/drafts')
@login_required
@admin_required
def drafts():
    drafts = Draft.query.order_by(Draft.updated_at.desc()).all()
    return render_template('admin/drafts.html', drafts=drafts)

@bp.route('/draft/add', methods=['GET', 'POST'])
@login_required
@admin_required
def draft_add():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category_id')
        seller_id = request.form.get('seller_id')
        allow_bargain = 'allow_bargain' in request.form
        
        # 处理主图
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            original_name = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
            image_url = f"/static/uploads/{unique_name}"
        else:
            image_url = ''
        
        # 处理细节图
        detail_files = request.files.getlist('detail_images')
        detail_urls = []
        for f in detail_files:
            if f and allowed_file(f.filename):
                original_name = secure_filename(f.filename)
                unique_name = f"{uuid.uuid4().hex}_{original_name}"
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
                detail_urls.append(f"/static/uploads/{unique_name}")
        detail_images_json = json.dumps(detail_urls) if detail_urls else ''
        
        if not title or not price:
            flash('标题和价格不能为空', 'danger')
            return redirect(url_for('admin.draft_add'))
        try:
            price = float(price)
        except:
            flash('价格必须是数字', 'danger')
            return redirect(url_for('admin.draft_add'))
        
        seller = User.query.get(int(seller_id)) if seller_id else current_user
        draft = Draft(
            user_id=seller.id,
            title=title,
            description=description,
            price=price,
            category_id=int(category_id) if category_id else None,
            image_url=image_url,
            detail_images=detail_images_json,
            allow_bargain=allow_bargain
        )
        db.session.add(draft)
        db.session.commit()
        log_admin_action('添加商品草稿', 'draft', draft.id, f'标题: {title}')
        flash('草稿添加成功', 'success')
        return redirect(url_for('admin.drafts'))
    
    categories = Category.query.order_by(Category.sort_order).all()
    users = User.query.all()
    return render_template('admin/draft_form.html', categories=categories, users=users)

@bp.route('/draft/edit/<int:draft_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def draft_edit(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    if request.method == 'POST':
        draft.title = request.form.get('title')
        draft.description = request.form.get('description')
        try:
            draft.price = float(request.form.get('price'))
        except:
            flash('价格必须是数字', 'danger')
            return redirect(url_for('admin.draft_edit', draft_id=draft.id))
        draft.category_id = int(request.form.get('category_id')) if request.form.get('category_id') else None
        draft.allow_bargain = 'allow_bargain' in request.form
        
        seller_id = request.form.get('seller_id')
        if seller_id:
            seller = User.query.get(int(seller_id))
            if seller:
                draft.user_id = seller.id
        
        # 处理主图替换
        file = request.files.get('image')
        if file and allowed_file(file.filename) and validate_file_content(file):
            if draft.image_url and draft.image_url.startswith('/static/uploads/'):
                old_path = os.path.join(current_app.root_path, draft.image_url.lstrip('/'))
                if os.path.exists(old_path):
                    os.remove(old_path)
            original_name = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
            draft.image_url = f"/static/uploads/{unique_name}"
        
        # 细节图处理
        keep_images = request.form.getlist('keep_images')
        old_detail = json.loads(draft.detail_images) if draft.detail_images else []
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
        draft.detail_images = json.dumps(final_detail) if final_detail else ''
        
        db.session.commit()
        log_admin_action('编辑商品草稿', 'draft', draft.id, f'标题: {draft.title}')
        flash('草稿已更新', 'success')
        return redirect(url_for('admin.drafts'))
    
    categories = Category.query.order_by(Category.sort_order).all()
    users = User.query.all()
    detail_images = json.loads(draft.detail_images) if draft.detail_images else []
    return render_template('admin/draft_form.html', draft=draft, categories=categories, users=users, detail_images=detail_images)

@bp.route('/draft/delete/<int:draft_id>')
@login_required
@admin_required
def draft_delete(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    # 删除关联图片
    if draft.image_url and draft.image_url.startswith('/static/uploads/'):
        img_path = os.path.join(current_app.root_path, draft.image_url.lstrip('/'))
        if os.path.exists(img_path):
            os.remove(img_path)
    if draft.detail_images:
        detail_urls = json.loads(draft.detail_images)
        for url in detail_urls:
            file_path = os.path.join(current_app.root_path, url.lstrip('/'))
            if os.path.exists(file_path):
                os.remove(file_path)
    db.session.delete(draft)
    db.session.commit()
    log_admin_action('删除商品草稿', 'draft', draft.id)
    flash('草稿已删除', 'success')
    return redirect(url_for('admin.drafts'))

@bp.route('/draft/publish/<int:draft_id>')
@login_required
@admin_required
def draft_publish(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    item = Item(
        title=draft.title,
        description=draft.description,
        price=draft.price,
        category_id=draft.category_id,
        image_url=draft.image_url or 'https://via.placeholder.com/300x200?text=No+Image',
        detail_images=draft.detail_images,
        allow_bargain=draft.allow_bargain,
        seller_id=draft.user_id,
        status='on_sale'
    )
    db.session.add(item)
    db.session.delete(draft)
    db.session.commit()
    log_admin_action('从草稿发布商品', 'item', item.id, f'标题: {item.title}')
    flash('商品已发布', 'success')
    return redirect(url_for('admin.drafts'))