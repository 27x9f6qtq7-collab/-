from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' / 'admin' / 'super_admin'
    admin_permissions = db.Column(db.String(500), default='')  # JSON array, e.g. '["item_manage","order_manage"]'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime)
    avatar = db.Column(db.String(200), default='default.png')
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        import uuid
        self.reset_token = uuid.uuid4().hex
        self.reset_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def clear_reset_token(self):
        self.reset_token = None
        self.reset_expires = None

    @property
    def is_admin(self):
        """向后兼容：role 为 admin 或 super_admin 即视为管理员"""
        return self.role in ('admin', 'super_admin')

    def is_super_admin(self):
        """是否为超级管理员"""
        return self.role == 'super_admin'

    def has_permission(self, perm):
        """检查普通管理员是否拥有某项权限。超级管理员始终返回 True"""
        import json
        if self.role == 'super_admin':
            return True
        if self.role != 'admin':
            return False
        try:
            perms = json.loads(self.admin_permissions) if self.admin_permissions else []
        except (json.JSONDecodeError, TypeError):
            perms = []
        return perm in perms

    @property
    def is_online(self):
        if not self.last_active:
            return False
        return (datetime.utcnow() - self.last_active).total_seconds() < 300

    @property
    def last_active_display(self):
        if not self.last_active:
            return '从未在线'
        diff = (datetime.utcnow() - self.last_active).total_seconds()
        if diff < 300:
            return '在线'
        elif diff < 3600:
            return f'{int(diff // 60)}分钟前在线'
        elif diff < 86400:
            return f'{int(diff // 3600)}小时前在线'
        else:
            return self.last_active.strftime('%Y-%m-%d')


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)   # 改为允许重复（若需全局唯一可加 unique=True）
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)  # 新增父级ID
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 自关联关系（支持无限级分类，三级已足够）
    parent = db.relationship('Category', remote_side=[id], backref='children', foreign_keys=[parent_id])
    items = db.relationship('Item', backref='category', lazy=True)

    @property
    def total_item_count(self):
        """递归统计该分类及其所有后代分类下的上架商品数量"""
        def get_sub_ids(cat):
            ids = [cat.id]
            for child in cat.children:
                ids.extend(get_sub_ids(child))
            return ids
        from app.models import Item
        ids = get_sub_ids(self)
        return Item.query.filter(Item.category_id.in_(ids), Item.status == 'on_sale').count()

    def level(self):
        """计算当前分类的层级（0=一级，1=二级，2=三级）"""
        lvl = 0
        p = self.parent
        while p:
            lvl += 1
            p = p.parent
        return lvl


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(256), default='https://via.placeholder.com/300x200?text=No+Image')
    detail_images = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='on_sale')
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    allow_bargain = db.Column(db.Boolean, default=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    condition = db.Column(db.String(20), default='正常使用')  # 全新/几乎全新/轻微使用/正常使用
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系定义：关联到卖家用户
    seller = db.relationship('User', backref=db.backref('items', lazy=True))

    @property
    def is_sold_out(self):
        return self.quantity <= 0


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    snapshot = db.Column(db.Text, default='')
    buyer_note = db.Column(db.String(200))

    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='buy_orders')
    item = db.relationship('Item', backref='orders')


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivateMessage(db.Model):
    __tablename__ = 'private_messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')


class ItemComment(db.Model):
    __tablename__ = 'item_comments'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item', backref='comments')
    user = db.relationship('User', backref='comments')


class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    admin_name = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(128), nullable=False)
    target_type = db.Column(db.String(64), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('User', backref='admin_logs')


class Bargain(db.Model):
    __tablename__ = 'bargains'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    offered_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied_at = db.Column(db.DateTime, nullable=True)

    item = db.relationship('Item', backref='bargains')
    buyer = db.relationship('User', foreign_keys=[buyer_id])


class Blacklist(db.Model):
    __tablename__ = 'blacklists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    blocked = db.relationship('User', foreign_keys=[blocked_id])
    __table_args__ = (db.UniqueConstraint('user_id', 'blocked_id', name='unique_block'),)


class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

    @staticmethod
    def get(key, default=''):
        setting = Setting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            db.session.add(setting)
        db.session.commit()


class Draft(db.Model):
    __tablename__ = 'drafts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    image_url = db.Column(db.String(256))
    detail_images = db.Column(db.Text)
    allow_bargain = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='drafts')
    category = db.relationship('Category')


class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    reply = db.Column(db.Text, nullable=True)
    replied_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    replier = db.relationship('User', foreign_keys=[replied_by])


class AdminReadStatus(db.Model):
    __tablename__ = 'admin_read_status'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module = db.Column(db.String(50), nullable=False)  # 'order' 或 'feedback'
    last_read_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('admin_id', 'module', name='unique_admin_module'),)


class SearchHistory(db.Model):
    __tablename__ = 'search_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    keyword = db.Column(db.String(200), nullable=False)
    searched_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='search_history')


class BrowseHistory(db.Model):
    __tablename__ = 'browse_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    browsed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='browse_history')
    item = db.relationship('Item', backref='browse_history')


