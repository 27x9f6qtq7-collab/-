from flask import Blueprint, abort, request
from flask_login import current_user

bp = Blueprint('admin', __name__)

from app import csrf
# CSRF 保护已对 admin 蓝图启用，JSON 端点需在请求头中加入 X-CSRFToken

# 路由 → 所需权限 映射表（超级管理员不受此限制）
PERMISSION_MAP = {
    # 商品管理
    'admin.items': 'item_manage',
    'admin.item_add': 'item_manage',
    'admin.item_edit': 'item_manage',
    'admin.item_toggle': 'item_manage',
    'admin.item_feature': 'item_manage',
    'admin.item_delete': 'item_manage',
    # 订单管理
    'admin.orders': 'order_manage',
    'admin.order_update': 'order_manage',
    'admin.order_delete': 'order_manage',
    # 分类管理
    'admin.categories': 'category_manage',
    'admin.category_add': 'category_manage',
    'admin.category_edit': 'category_manage',
    'admin.category_delete': 'category_manage',
    # 用户管理
    'admin.users': 'user_manage',
    'admin.toggle_admin': 'user_manage',
    'admin.edit_permissions': 'user_manage',
    'admin.user_delete': 'user_manage',
    'admin.reset_password': 'user_manage',
    # 公告管理
    'admin.announcements': 'announcement_manage',
    'admin.announcement_add': 'announcement_manage',
    'admin.announcement_edit': 'announcement_manage',
    'admin.announcement_delete': 'announcement_manage',
    'admin.announcement_toggle': 'announcement_manage',
}

# 所有管理员均可访问的路由（无需特定权限）
PUBLIC_ADMIN_ENDPOINTS = {
    'admin.dashboard', 'admin.stats',
    'admin.mark_orders_read', 'admin.mark_feedback_read',
    'static',
}

@bp.before_request
def check_admin_permission():
    if not current_user.is_authenticated:
        return  # login_required 会处理
    if not current_user.is_admin:
        abort(403)
    # 超级管理员全部通过
    if current_user.is_super_admin():
        return
    # 公开端点（dashboard 等）所有管理员可访问
    if request.endpoint in PUBLIC_ADMIN_ENDPOINTS:
        return
    # 普通管理员：按映射表检查权限
    perm = PERMISSION_MAP.get(request.endpoint)
    if perm is None:
        # 未在映射表中的端点（如 settings/logs/export/agreement/feedback/draft），
        # 普通管理员默认无权限访问
        abort(403)
    if not current_user.has_permission(perm):
        abort(403)

from app.admin.views import dashboard
from app.admin.views import item
from app.admin.views import category
from app.admin.views import announcement
from app.admin.views import order
from app.admin.views import user
from app.admin.views import setting
from app.admin.views import agreement
from app.admin.views import log
from app.admin.views import export
from app.admin.views import feedback
from app.admin.views import draft
