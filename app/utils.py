import os
import shutil
import random
from datetime import datetime, timedelta
from flask import current_app, request
from flask_login import current_user
from app import db
from app.models import Message, AdminLog, Order, Setting, PrivateMessage

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def validate_file_content(file_storage):
    """验证文件内容魔数，防止扩展名伪装"""
    allowed_magic = {
        b'\x89PNG\r\n\x1a\n': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'RIFF': 'webp',  # WebP: RIFF....WEBP
        b'\x00\x00\x00': 'mp4',  # MP4: ftyp box
    }
    header = file_storage.read(12)
    file_storage.seek(0)
    for magic, fmt in allowed_magic.items():
        if header.startswith(magic):
            if fmt == 'webp' and header[8:12] != b'WEBP':
                continue
            if fmt == 'mp4' and b'ftyp' not in header[4:12]:
                continue
            return True
    return False

def generate_order_number():
    now = datetime.now()
    prefix = now.strftime('%Y%m%d%H%M%S')
    random_suffix = str(random.randint(100000, 999999))
    return prefix + random_suffix

def send_notification(user_id, title, content, sender_id=None):
    msg = Message(sender_id=sender_id, receiver_id=user_id, title=title, content=content)
    db.session.add(msg)
    db.session.commit()

def log_admin_action(action, target_type=None, target_id=None, details=None, request_path=None, request_method=None):
    if current_user.is_authenticated and current_user.is_admin:
        ip = request.remote_addr
        path = request_path or request.path
        method = request_method or request.method
        full_details = f"{details} | Path: {path} | Method: {method}" if details else f"Path: {path} | Method: {method}"
        log = AdminLog(
            admin_id=current_user.id,
            admin_name=current_user.student_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=full_details,
            ip_address=ip
        )
        db.session.add(log)
        db.session.commit()

def utc_to_local(utc_dt):
    if not utc_dt:
        return None
    return utc_dt + timedelta(hours=8)

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort
            abort(403)
        return func(*args, **kwargs)
    return decorated_view

def permission_required(perm):
    """权限检查装饰器：超级管理员全通过，普通管理员需拥有指定权限"""
    from functools import wraps
    def decorator(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                from flask import abort
                abort(401)
            if not current_user.has_permission(perm):
                from flask import abort
                abort(403)
            return func(*args, **kwargs)
        return decorated_view
    return decorator

def inject_settings():
    unread_count = 0
    unread_private_count = 0
    if current_user.is_authenticated:
        unread_count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
        unread_private_count = PrivateMessage.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    bg_file = os.path.join(current_app.static_folder, 'backgrounds', 'bg.jpg')
    has_custom_bg = os.path.exists(bg_file)
    return {
        'setting_background_type': Setting.get('background_type', 'color'),
        'setting_background_value': Setting.get('background_value', '#f8f9fa'),
        'show_contact_btn': Setting.get('show_contact_btn', 'true') == 'true',
        'contact_btn_text': Setting.get('contact_btn_text', '联系管理人员'),
        'contact_info': Setting.get('contact_info', '请通过邮箱联系管理员：admin@example.com'),
        'unread_count': unread_count,
        'unread_private_count': unread_private_count,
        'has_custom_bg': has_custom_bg,
        'custom_bg_timestamp': int(datetime.now().timestamp()) if has_custom_bg else 0,
    }

def auto_cancel_timeout_orders():
    """自动取消超过10分钟未支付的订单，并重新上架商品"""
    with current_app.app_context():
        timeout_limit = datetime.utcnow() - timedelta(minutes=10)
        timeout_orders = Order.query.filter(Order.status == 'pending', Order.created_at <= timeout_limit).all()
        for order in timeout_orders:
            order.status = 'cancelled'
            if order.item.status == 'off_sale':
                order.item.status = 'on_sale'
            db.session.commit()
            send_notification(order.buyer_id, '订单已自动取消', f'您的订单 {order.order_number} 因超时未支付已自动取消。')
            print(f"自动取消超时订单: {order.order_number}")

def backup_database():
    """数据库备份，每天凌晨2点执行（实际时间由调度器决定）"""
    with current_app.app_context():
        # 使用 Flask 的 instance_path 获取正确的 instance 文件夹路径
        db_path = os.path.join(current_app.instance_path, 'secondhand.db')
        print(f"数据库路径: {db_path}")
        if not os.path.exists(db_path):
            print("数据库文件不存在，退出备份")
            return
        backup_dir = os.path.join(current_app.root_path, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'secondhand_backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        shutil.copy2(db_path, backup_path)
        print(f"数据库备份完成: {backup_path}")
        # 删除超过30天的备份
        for f in os.listdir(backup_dir):
            if f.startswith('secondhand_backup_') and f.endswith('.db'):
                file_path = os.path.join(backup_dir, f)
                if os.path.getmtime(file_path) < (datetime.now() - timedelta(days=30)).timestamp():
                    os.remove(file_path)
                    print(f"删除过期备份: {file_path}")