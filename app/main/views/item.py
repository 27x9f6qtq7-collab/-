import json
from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Item, ItemComment, Bargain, BrowseHistory
from app.utils import utc_to_local
from app.main import bp

@bp.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    detail_images = json.loads(item.detail_images) if item.detail_images else []
    comments = ItemComment.query.filter_by(item_id=item.id).order_by(ItemComment.created_at.desc()).all()
    for comment in comments:
        comment.local_time = utc_to_local(comment.created_at)
    agreed_bargain = None
    if current_user.is_authenticated:
        agreed_bargain = Bargain.query.filter_by(item_id=item.id, buyer_id=current_user.id, status='agreed').first()
        # 记录浏览历史
        browse = BrowseHistory(user_id=current_user.id, item_id=item.id)
        db.session.add(browse)
        db.session.commit()
    return render_template('item_detail.html',
                           item=item,
                           detail_images=detail_images,
                           comments=comments,
                           agreed_bargain=agreed_bargain)

@bp.route('/item/<int:item_id>/comment', methods=['POST'])
@login_required
def add_comment(item_id):
    item = Item.query.get_or_404(item_id)
    content = request.form.get('content', '').strip()
    if not content:
        flash('评论内容不能为空', 'danger')
    elif len(content) > 500:
        flash('评论内容不能超过 500 字', 'danger')
    else:
        comment = ItemComment(item_id=item.id, user_id=current_user.id, content=content)
        db.session.add(comment)
        db.session.commit()
        flash('评论已添加', 'success')
    return redirect(url_for('main.item_detail', item_id=item_id))


