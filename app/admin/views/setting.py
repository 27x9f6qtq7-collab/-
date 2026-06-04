import os
import uuid
from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from app import db
from app.models import Setting
from app.utils import admin_required, allowed_file
from app.admin import bp

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        bg_type = request.form.get('bg_type')
        bg_value = request.form.get('bg_value')
        file = request.files.get('bg_image')
        admin_contact = request.form.get('admin_contact')
        timeout_contact = request.form.get('timeout_contact')
        show_contact_btn = request.form.get('show_contact_btn') == 'on'
        contact_btn_text = request.form.get('contact_btn_text')
        contact_info = request.form.get('contact_info')
        if bg_type == 'color':
            Setting.set('background_type', 'color')
            Setting.set('background_value', bg_value or '#f8f9fa')
            flash('背景设置已更新', 'success')
        else:
            if file and allowed_file(file.filename) and validate_file_content(file):
                old_bg = Setting.get('background_value', '')
                if old_bg and old_bg.startswith('/static/uploads/') and old_bg != '/static/images/default_bg.jpg':
                    old_path = os.path.join(current_app.root_path, old_bg.lstrip('/'))
                    if os.path.exists(old_path):
                        os.remove(old_path)
                original_name = secure_filename(file.filename)
                unique_name = f"bg_{uuid.uuid4().hex}_{original_name}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
                bg_url = f"/static/uploads/{unique_name}"
                Setting.set('background_type', 'image')
                Setting.set('background_value', bg_url)
                flash('背景图片已更新', 'success')
            else:
                flash('请选择有效的图片文件', 'danger')
                return redirect(url_for('admin.settings'))
        if admin_contact:
            Setting.set('admin_contact', admin_contact)
            flash('管理员联系方式已更新', 'success')
        if timeout_contact:
            Setting.set('timeout_contact', timeout_contact)
            flash('超时联系信息已更新', 'success')
        Setting.set('show_contact_btn', 'true' if show_contact_btn else 'false')
        if contact_btn_text:
            Setting.set('contact_btn_text', contact_btn_text)
        if contact_info:
            Setting.set('contact_info', contact_info)
        flash('前台联系按钮设置已更新', 'success')
        return redirect(url_for('admin.settings'))
    bg_type = Setting.get('background_type', 'color')
    bg_value = Setting.get('background_value', '#f8f9fa')
    admin_contact = Setting.get('admin_contact', 'admin@example.com')
    timeout_contact = Setting.get('timeout_contact', '订单超时未处理，请联系管理员：admin@example.com (请备注订单号)')
    show_contact_btn = Setting.get('show_contact_btn', 'true') == 'true'
    contact_btn_text = Setting.get('contact_btn_text', '联系管理人员')
    contact_info = Setting.get('contact_info', '请通过邮箱联系管理员：admin@example.com')
    return render_template('admin/settings.html',
                           bg_type=bg_type,
                           bg_value=bg_value,
                           admin_contact=admin_contact,
                           timeout_contact=timeout_contact,
                           show_contact_btn=show_contact_btn,
                           contact_btn_text=contact_btn_text,
                           contact_info=contact_info)

@bp.route('/clear-background')
@login_required
@admin_required
def clear_background():
    old_bg = Setting.get('background_value', '')
    if old_bg and old_bg.startswith('/static/uploads/'):
        old_path = os.path.join(current_app.root_path, old_bg.lstrip('/'))
        if os.path.exists(old_path):
            os.remove(old_path)
    Setting.set('background_type', 'color')
    Setting.set('background_value', '#f8f9fa')
    flash('已清除背景图片', 'success')
    return redirect(url_for('admin.settings'))