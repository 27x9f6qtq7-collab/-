from flask import render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import User
from app.utils import admin_required, log_admin_action
from app.admin import bp
from app import csrf
import json
import re

@bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@bp.route('/user/toggle-admin/<int:user_id>')
@login_required
@admin_required
def toggle_admin(user_id):
    if not current_user.is_super_admin():
        abort(403)
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash('不能修改自己的权限', 'danger')
        return redirect(url_for('admin.users'))
    if target.role == 'super_admin':
        flash('不能修改超级管理员的权限', 'danger')
        return redirect(url_for('admin.users'))
    if target.role == 'admin':
        # 撤销管理员
        target.role = 'user'
        target.admin_permissions = ''
        flash(f'已撤销 {target.student_id} 的管理员权限', 'success')
    else:
        # 设为管理员，默认授予商品管理和订单管理权限
        target.role = 'admin'
        target.admin_permissions = json.dumps(['item_manage', 'order_manage'])
        flash(f'已将 {target.student_id} 设为管理员', 'success')
    db.session.commit()
    log_admin_action('修改管理员权限', 'user', target.id, f'用户 {target.student_id} role={target.role}')
    return redirect(url_for('admin.users'))

@bp.route('/user/edit-permissions/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_permissions(user_id):
    if not current_user.is_super_admin():
        abort(403)
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash('不能修改自己的权限', 'danger')
        return redirect(url_for('admin.users'))
    if target.role == 'super_admin':
        flash('超级管理员无需设置权限', 'warning')
        return redirect(url_for('admin.users'))
    if target.role != 'admin':
        flash('该用户不是管理员', 'warning')
        return redirect(url_for('admin.users'))

    ALL_PERMISSIONS = {
        'item_manage': '商品管理（上下架、编辑、删除商品）',
        'order_manage': '订单管理',
        'category_manage': '分类管理',
        'user_manage': '用户管理',
        'announcement_manage': '公告管理',
    }

    if request.method == 'POST':
        selected = request.form.getlist('permissions')
        # 确保只保存合法的权限项
        valid = [p for p in selected if p in ALL_PERMISSIONS]
        target.admin_permissions = json.dumps(valid)
        db.session.commit()
        log_admin_action('编辑管理员权限', 'user', target.id, f'用户 {target.student_id} 权限={valid}')
        flash(f'已更新 {target.student_id} 的权限', 'success')
        return redirect(url_for('admin.users'))

    current_perms = []
    try:
        current_perms = json.loads(target.admin_permissions) if target.admin_permissions else []
    except (json.JSONDecodeError, TypeError):
        current_perms = []

    return render_template('admin/user_role.html', user=target,
                           all_permissions=ALL_PERMISSIONS,
                           current_perms=current_perms)

@bp.route('/user/delete/<int:user_id>')
@login_required
@admin_required
def user_delete(user_id):
    if not current_user.is_super_admin():
        abort(403)
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash('不能删除自己', 'danger')
        return redirect(url_for('admin.users'))
    if target.is_admin and target.id != current_user.id:
        flash('不能删除其他管理员', 'danger')
        return redirect(url_for('admin.users'))
    if target.items or target.buy_orders:
        flash('该用户有关联物品或订单，无法删除', 'danger')
        return redirect(url_for('admin.users'))
    db.session.delete(target)
    db.session.commit()
    log_admin_action('删除用户', 'user', target.id, f'学号：{target.student_id}')
    flash('用户已删除', 'success')
    return redirect(url_for('admin.users'))

@bp.route('/reset-password', methods=['POST'])
@csrf.exempt
def reset_password():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '无权限'}), 403
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据无效'})
    user_id = data.get('user_id')
    new_password = data.get('new_password')
    if not user_id or not new_password:
        return jsonify({'success': False, 'message': '参数不完整'})
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': '密码至少8位'})
    if not re.search(r'[A-Z]', new_password):
        return jsonify({'success': False, 'message': '密码需包含大写字母'})
    if not re.search(r'[a-z]', new_password):
        return jsonify({'success': False, 'message': '密码需包含小写字母'})
    if not re.search(r'\d', new_password):
        return jsonify({'success': False, 'message': '密码需包含数字'})
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({'success': False, 'message': '用户不存在'})
    if target_user.id == current_user.id:
        return jsonify({'success': False, 'message': '不能重置自己的密码'})
    target_user.set_password(new_password)
    db.session.commit()
    log_admin_action('重置密码', 'user', target_user.id, f'重置用户 {target_user.student_id} 的密码')
    return jsonify({'success': True, 'message': '密码已重置'})