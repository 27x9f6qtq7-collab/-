from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.models import Category
from app.utils import admin_required, log_admin_action
from app.admin import bp


def get_descendant_ids(category):
    """递归收集分类的所有后代 ID"""
    ids = []
    for child in category.children:
        ids.append(child.id)
        ids.extend(get_descendant_ids(child))
    return ids


@bp.route('/categories')
@login_required
@admin_required
def categories():
    categories = Category.query.filter_by(parent_id=None).order_by(Category.sort_order).all()
    return render_template('admin/categories.html', categories=categories)


@bp.route('/category/add', methods=['GET', 'POST'])
@login_required
@admin_required
def category_add():
    if request.method == 'POST':
        name = request.form.get('name')
        sort_order = request.form.get('sort_order', 0)
        parent_id = request.form.get('parent_id')
        if name:
            cat = Category(
                name=name,
                sort_order=int(sort_order),
                parent_id=int(parent_id) if parent_id else None
            )
            db.session.add(cat)
            db.session.commit()
            log_admin_action('添加分类', 'category', cat.id, f'分类名称：{name}')
            flash('分类添加成功', 'success')
        else:
            flash('分类名称不能为空', 'danger')
        return redirect(url_for('admin.categories'))
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template('admin/category_form.html', categories=categories)


@bp.route('/category/edit/<int:cat_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def category_edit(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if request.method == 'POST':
        old_name = cat.name
        cat.name = request.form.get('name')
        cat.sort_order = int(request.form.get('sort_order', 0))
        parent_id = request.form.get('parent_id')
        cat.parent_id = int(parent_id) if parent_id else None
        db.session.commit()
        log_admin_action('编辑分类', 'category', cat.id, f'原名称：{old_name} -> {cat.name}')
        flash('分类修改成功', 'success')
        return redirect(url_for('admin.categories'))
    descendant_ids = get_descendant_ids(cat)
    exclude_ids = [cat.id] + descendant_ids
    categories = Category.query.filter(~Category.id.in_(exclude_ids)).order_by(Category.sort_order).all()
    return render_template('admin/category_form.html', category=cat, categories=categories, exclude_ids=set(exclude_ids))


@bp.route('/category/delete/<int:cat_id>')
@login_required
@admin_required
def category_delete(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.children:
        flash('该分类下存在子分类，请先删除子分类', 'danger')
    elif cat.items:
        flash('该分类下还有商品，无法删除', 'danger')
    else:
        name = cat.name
        db.session.delete(cat)
        db.session.commit()
        log_admin_action('删除分类', 'category', cat_id, f'分类名称：{name}')
        flash('分类已删除', 'success')
    return redirect(url_for('admin.categories'))
