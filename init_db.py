from app import create_app, db
from app.models import User, Item, Setting

app = create_app()
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(student_id='admin').first()
    if not admin:
        admin = User(student_id='admin', role='super_admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("管理员创建成功")
    if Item.query.count() == 0:
        demo_item = Item(
            title='二手iPhone 12',
            description='九成新，无拆修',
            price=3299.00,
            seller_id=admin.id,
            status='on_sale'
        )
        db.session.add(demo_item)
        db.session.commit()
        print("演示物品添加成功")
    print("数据库初始化完成")