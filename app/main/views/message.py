from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import Message
from app.utils import utc_to_local

@bp.route('/my-messages')
@login_required
def my_messages():
    messages = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.created_at.desc()).all()
    for msg in messages:
        msg.local_time = utc_to_local(msg.created_at)
    unread_count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return render_template('my_messages.html', messages=messages, unread_count=unread_count)

@bp.route('/mark-message-read/<int:msg_id>')
@login_required
def mark_message_read(msg_id):
    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({'success': False, 'message': '消息不存在'}), 404
    if msg.receiver_id != current_user.id:
        return jsonify({'success': False, 'message': '无权限'}), 403
    if not msg.is_read:
        msg.is_read = True
        db.session.commit()
    unread_count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return jsonify({'success': True, 'unread_count': unread_count})