from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Feedback
from app.main import bp

@bp.route('/feedbacks')
@login_required
def my_feedbacks():
    feedbacks = Feedback.query.filter_by(user_id=current_user.id).order_by(Feedback.created_at.desc()).all()
    return render_template('my_feedbacks.html', feedbacks=feedbacks)

@bp.route('/feedback/submit', methods=['GET', 'POST'])
@login_required
def submit_feedback():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if not title or not content:
            flash('标题和内容不能为空', 'danger')
            return redirect(url_for('main.submit_feedback'))
        feedback = Feedback(user_id=current_user.id, title=title, content=content)
        db.session.add(feedback)
        db.session.commit()
        flash('反馈已提交，感谢您的建议', 'success')
        return redirect(url_for('main.profile'))
    return render_template('submit_feedback.html')