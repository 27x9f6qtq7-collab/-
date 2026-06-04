import os
import json
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录'

from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect()

# 全局调度器，指定时区为北京时间
beijing_tz = ZoneInfo('Asia/Shanghai')
scheduler = BackgroundScheduler(timezone=beijing_tz)

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # 确保必要文件夹存在
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    app.add_template_filter(json.loads, 'from_json')

    db.init_app(app)
    login_manager.init_app(app)

    csrf.init_app(app)

    # 导入所有模型
    from app.models import User, Item, Order, Message, AdminLog, Bargain, Blacklist, Setting, Announcement, Draft, Feedback, SearchHistory, BrowseHistory

    # 创建数据库表和默认数据
    with app.app_context():
        db.create_all()
        # 首次启动提示
        if User.query.count() == 0:
            print("数据库为空，使用以下命令创建超级管理员：")
            print("  flask create-admin")

    @app.cli.command('create-admin')
    def create_admin():
        """创建或提升超级管理员"""
        import click
        student_id = click.prompt('学号')
        password = click.prompt('密码', hide_confirmation=True, confirmation_prompt='确认密码')
        if len(password) < 8:
            click.echo('密码至少8位')
            return
        if not any(c.isupper() for c in password):
            click.echo('密码需包含大写字母')
            return
        if not any(c.islower() for c in password):
            click.echo('密码需包含小写字母')
            return
        if not any(c.isdigit() for c in password):
            click.echo('密码需包含数字')
            return
        with app.app_context():
            user = User.query.filter_by(student_id=student_id).first()
            if user:
                user.role = 'super_admin'
                user.set_password(password)
                click.echo(f'已将 {student_id} 提升为超级管理员，密码已更新')
            else:
                user = User(student_id=student_id, role='super_admin')
                user.set_password(password)
                db.session.add(user)
                click.echo(f'已创建超级管理员 {student_id}')
            db.session.commit()

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def update_last_active():
        if current_user.is_authenticated:
            current_user.last_active = datetime.utcnow()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    # 注册蓝图
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # 上下文处理器
    from app.utils import inject_settings
    app.context_processor(inject_settings)

    # ----- 定时任务（包装应用上下文）-----
    from app.utils import auto_cancel_timeout_orders, backup_database

    def run_auto_cancel():
        with app.app_context():
            auto_cancel_timeout_orders()

    def run_backup():
        with app.app_context():
            backup_database()

    if not scheduler.running:
        scheduler.add_job(func=run_auto_cancel, trigger="interval", minutes=1)
        scheduler.add_job(func=run_backup, trigger="cron", hour=1, minute=0)  # 北京时间凌晨1:00
        scheduler.start()
        print("定时任务调度器已启动（北京时间）")

    return app