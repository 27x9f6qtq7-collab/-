from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.models import Announcement
from app.utils import admin_required, log_admin_action
from app.admin import bp

@bp.route('/announcements')
@login_required
@admin_required
def announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', announcements=announcements)

@bp.route('/announcement/add', methods=['GET', 'POST'])
@login_required
@admin_required
def announcement_add():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        is_active = request.form.get('is_active') == 'on'
        if title and content:
            ann = Announcement(title=title, content=content, is_active=is_active)
            db.session.add(ann)
            db.session.commit()
            log_admin_action('添加公告', 'announcement', ann.id, f'标题：{title}')
            flash('公告添加成功', 'success')
        else:
            flash('标题和内容不能为空', 'danger')
        return redirect(url_for('admin.announcements'))
    return render_template('admin/announcement_form.html')

@bp.route('/announcement/edit/<int:ann_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def announcement_edit(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    if request.method == 'POST':
        old_title = ann.title
        ann.title = request.form.get('title')
        ann.content = request.form.get('content')
        ann.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        log_admin_action('编辑公告', 'announcement', ann.id, f'原标题：{old_title} -> {ann.title}')
        flash('公告修改成功', 'success')
        return redirect(url_for('admin.announcements'))
    return render_template('admin/announcement_form.html', announcement=ann)

@bp.route('/announcement/delete/<int:ann_id>')
@login_required
@admin_required
def announcement_delete(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    title = ann.title
    db.session.delete(ann)
    db.session.commit()
    log_admin_action('删除公告', 'announcement', ann.id, f'标题：{title}')
    flash('公告已删除', 'success')
    return redirect(url_for('admin.announcements'))


@bp.route('/announcement/toggle/<int:ann_id>')
@login_required
@admin_required
def announcement_toggle(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    ann.is_active = not ann.is_active
    db.session.commit()
    status_text = '显示' if ann.is_active else '隐藏'
    log_admin_action('切换公告状态', 'announcement', ann.id, f'标题：{ann.title} -> {status_text}')
    flash(f'公告已{status_text}', 'success')
    return redirect(url_for('admin.announcements'))