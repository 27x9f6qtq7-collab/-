from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import re
from app import db
from app.models import User, Setting
from app.utils import log_admin_action


def _validate_password(password):
    """密码强度校验：至少8位、含大小写字母和数字"""
    if len(password) < 8:
        return '密码至少8位'
    if not re.search(r'[A-Z]', password):
        return '密码需包含大写字母'
    if not re.search(r'[a-z]', password):
        return '密码需包含小写字母'
    if not re.search(r'\d', password):
        return '密码需包含数字'
    return None

from . import bp

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        email = request.form.get('email')
        password = request.form.get('password')
        agree_privacy = request.form.get('agree_privacy')
        agree_terms = request.form.get('agree_terms')
        agree_disclaimer = request.form.get('agree_disclaimer')
        if not (agree_privacy and agree_terms and agree_disclaimer):
            flash('请阅读并同意所有协议', 'danger')
            return redirect(url_for('auth.register'))
        if not student_id or not password:
            flash('学号和密码不能为空', 'danger')
            return redirect(url_for('auth.register'))
        pw_error = _validate_password(password)
        if pw_error:
            flash(pw_error, 'danger')
            return redirect(url_for('auth.register'))
        if len(student_id) < 5:
            flash('学号长度至少5位', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(student_id=student_id).first():
            flash('该学号已注册', 'danger')
            return redirect(url_for('auth.register'))
        if email:
            if User.query.filter_by(email=email).first():
                flash('该邮箱已被使用', 'danger')
                return redirect(url_for('auth.register'))
            if '@' not in email or '.' not in email:
                flash('邮箱格式不正确', 'danger')
                return redirect(url_for('auth.register'))
        user = User(student_id=student_id, email=email if email else None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('注册成功', 'success')
        return redirect(url_for('main.index'))
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        user = User.query.filter_by(student_id=student_id).first()

        # 检查账户是否被锁定
        if user and user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            flash(f'账户已被锁定，请 {remaining} 分钟后重试', 'danger')
            return render_template('login.html')

        if user and user.check_password(password):
            # 登录成功，重置失败计数和锁定状态
            user.login_attempts = 0
            user.locked_until = None
            db.session.commit()
            login_user(user)
            flash('登录成功', 'success')
            if user.is_admin:
                log_admin_action('登录后台')
                return redirect(url_for('admin.dashboard'))
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            # 登录失败，增加计数
            if user:
                user.login_attempts += 1
                if user.login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    db.session.commit()
                    flash('登录失败次数过多，账户已被锁定 15 分钟', 'danger')
                else:
                    remaining = 5 - user.login_attempts
                    db.session.commit()
                    flash(f'学号或密码错误，还剩 {remaining} 次尝试机会', 'danger')
            else:
                flash('学号或密码错误', 'danger')
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('main.index'))

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not current_user.check_password(old_password):
            flash('原密码错误', 'danger')
            return redirect(url_for('auth.change_password'))
        pw_error = _validate_password(new_password)
        if pw_error:
            flash(pw_error, 'danger')
            return redirect(url_for('auth.change_password'))
        if new_password != confirm_password:
            flash('两次密码不一致', 'danger')
            return redirect(url_for('auth.change_password'))
        current_user.set_password(new_password)
        db.session.commit()
        flash('密码修改成功，请重新登录', 'success')
        logout_user()
        return redirect(url_for('auth.login'))
    return render_template('change_password.html')

@bp.route('/forgot-password')
def forgot_password():
    admin_contact = Setting.get('admin_contact', 'admin@example.com')
    return render_template('forgot_password.html', admin_contact=admin_contact)