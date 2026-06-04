from flask import render_template, request
from flask_login import current_user
from app import db
from app.main import bp
from app.models import Item, Category, Announcement, SearchHistory


@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 9
    search = request.args.get('search', '')
    category_id = request.args.get('category', type=int)
    sort = request.args.get('sort', 'newest')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    condition = request.args.get('condition', '')

    query = Item.query.filter_by(status='on_sale')

    if search:
        query = query.filter(Item.title.contains(search) | Item.description.contains(search))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if min_price is not None:
        query = query.filter(Item.price >= min_price)
    if max_price is not None:
        query = query.filter(Item.price <= max_price)
    if condition:
        query = query.filter_by(condition=condition)

    if sort == 'price_asc':
        query = query.order_by(Item.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Item.price.desc())
    else:
        query = query.order_by(Item.created_at.desc())

    # 记录搜索历史（登录用户 + 有搜索关键词）
    if search and current_user.is_authenticated:
        history = SearchHistory(user_id=current_user.id, keyword=search.strip())
        db.session.add(history)
        db.session.commit()

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items
    featured_items = Item.query.filter_by(is_featured=True, status='on_sale').order_by(Item.created_at.desc()).limit(5).all()
    categories = Category.query.order_by(Category.sort_order).all()
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(5).all()
    return render_template('index.html',
                           items=items,
                           featured_items=featured_items,
                           categories=categories,
                           announcements=announcements,
                           pagination=pagination)