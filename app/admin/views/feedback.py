from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models import Feedback
from app.utils import admin_required, log_admin_action
from app.admin import bp

@bp.route('/feedbacks')
@login_required
@admin_required
def feedbacks():
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template('admin/feedbacks.html', feedbacks=feedbacks)

@bp.route('/feedback/reply/<int:feedback_id>', methods=['POST'])
@login_required
@admin_required
def feedback_reply(feedback_id):
    fb = Feedback.query.get_or_404(feedback_id)
    reply = request.form.get('reply')
    if reply:
        fb.reply = reply
        fb.status = 'replied'
        fb.replied_by = current_user.id
        fb.replied_at = datetime.utcnow()
        db.session.commit()
        log_admin_action('回复用户反馈', 'feedback', fb.id, f'回复内容: {reply}')
        flash('回复已提交', 'success')
    else:
        flash('回复内容不能为空', 'danger')
    return redirect(url_for('admin.feedbacks'))

@bp.route('/feedback/close/<int:feedback_id>')
@login_required
@admin_required
def feedback_close(feedback_id):
    fb = Feedback.query.get_or_404(feedback_id)
    fb.status = 'closed'
    db.session.commit()
    log_admin_action('关闭反馈', 'feedback', fb.id)
    flash('反馈已关闭', 'success')
    return redirect(url_for('admin.feedbacks'))