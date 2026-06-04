from flask import render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.main import bp
from app import db
from app.models import PrivateMessage, Blacklist, User
from app.utils import utc_to_local

@bp.route('/messages')
@login_required
def messages():
    page_received = request.args.get('page_received', 1, type=int)
    page_sent = request.args.get('page_sent', 1, type=int)
    per_page = 10
    received_query = PrivateMessage.query.filter_by(receiver_id=current_user.id).order_by(PrivateMessage.created_at.desc())
    sent_query = PrivateMessage.query.filter_by(sender_id=current_user.id).order_by(PrivateMessage.created_at.desc())
    received_pagination = received_query.paginate(page=page_received, per_page=per_page, error_out=False)
    sent_pagination = sent_query.paginate(page=page_sent, per_page=per_page, error_out=False)
    for msg in received_pagination.items:
        msg.local_time = utc_to_local(msg.created_at)
    for msg in sent_pagination.items:
        msg.local_time = utc_to_local(msg.created_at)
    return render_template('messages.html',
                           received=received_pagination.items,
                           sent=sent_pagination.items,
                           received_pagination=received_pagination,
                           sent_pagination=sent_pagination)

@bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose_message():
    if request.method == 'POST':
        receiver_student_id = request.form.get('receiver_student_id')
        content = request.form.get('content')
        if not receiver_student_id:
            flash('请填写收件人学号', 'danger')
            return redirect(url_for('main.compose_message'))
        receiver = User.query.filter_by(student_id=receiver_student_id).first()
        if not receiver:
            flash('该学号不存在，请核对后再试', 'danger')
            return redirect(url_for('main.compose_message'))
        if receiver.id == current_user.id:
            flash('不能给自己发送私信', 'danger')
            return redirect(url_for('main.compose_message'))
        if not content:
            flash('内容不能为空', 'danger')
            return redirect(url_for('main.compose_message'))
        if Blacklist.query.filter_by(user_id=receiver.id, blocked_id=current_user.id).first():
            flash('对方已将您屏蔽，无法发送私信', 'danger')
            return redirect(url_for('main.compose_message'))
        if Blacklist.query.filter_by(user_id=current_user.id, blocked_id=receiver.id).first():
            flash('您已屏蔽对方，请先解除屏蔽', 'danger')
            return redirect(url_for('main.compose_message'))
        msg = PrivateMessage(sender_id=current_user.id, receiver_id=receiver.id, content=content)
        db.session.add(msg)
        db.session.commit()
        flash('私信发送成功', 'success')
        return redirect(url_for('main.profile'))
    return render_template('compose_message.html')

@bp.route('/send-message/<int:user_id>', methods=['GET', 'POST'])
@login_required
def send_message(user_id):
    receiver = User.query.get_or_404(user_id)
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            msg = PrivateMessage(sender_id=current_user.id, receiver_id=receiver.id, content=content)
            db.session.add(msg)
            db.session.commit()
            flash('私信发送成功', 'success')
            return redirect(url_for('main.profile'))
        else:
            flash('内容不能为空', 'danger')
    return render_template('send_message.html', receiver=receiver)

@bp.route('/message/<int:msg_id>')
@login_required
def view_message(msg_id):
    msg = PrivateMessage.query.get_or_404(msg_id)
    if msg.receiver_id == current_user.id and not msg.is_read:
        msg.is_read = True
        db.session.commit()
    msg.local_time = utc_to_local(msg.created_at)
    return render_template('message_detail.html', message=msg)

@bp.route('/reply-message/<int:msg_id>', methods=['POST'])
@login_required
def reply_message(msg_id):
    original = PrivateMessage.query.get_or_404(msg_id)
    receiver_id = original.sender_id if original.receiver_id == current_user.id else original.receiver_id
    content = request.form.get('content')
    if content:
        msg = PrivateMessage(sender_id=current_user.id, receiver_id=receiver_id, content=content)
        db.session.add(msg)
        db.session.commit()
        flash('回复已发送', 'success')
    else:
        flash('内容不能为空', 'danger')
    return redirect(url_for('main.profile'))

@bp.route('/block-user/<int:user_id>')
@login_required
def block_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash('不能屏蔽自己', 'danger')
        return redirect(request.referrer or url_for('main.index'))
    if target.is_admin:
        flash('不能屏蔽管理员', 'danger')
        return redirect(request.referrer or url_for('main.index'))
    existing = Blacklist.query.filter_by(user_id=current_user.id, blocked_id=target.id).first()
    if existing:
        flash('已经屏蔽过该用户', 'danger')
    else:
        block = Blacklist(user_id=current_user.id, blocked_id=target.id)
        db.session.add(block)
        db.session.commit()
        flash(f'已屏蔽用户 {target.student_id}', 'success')
    return redirect(url_for('main.profile'))

@bp.route('/unblock-user/<int:user_id>')
@login_required
def unblock_user(user_id):
    block = Blacklist.query.filter_by(user_id=current_user.id, blocked_id=user_id).first()
    if block:
        db.session.delete(block)
        db.session.commit()
        flash('已解除屏蔽', 'success')
    else:
        flash('未找到屏蔽记录', 'danger')
    return redirect(url_for('main.profile'))

@bp.route('/my-blacklist')
@login_required
def my_blacklist():
    blocks = Blacklist.query.filter_by(user_id=current_user.id).all()
    for block in blocks:
        block.local_time = utc_to_local(block.created_at)
    return render_template('my_blacklist.html', blocks=blocks)