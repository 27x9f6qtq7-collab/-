import os
import sys
from app import create_app, db
from app.models import User

app = create_app()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'create-admin':
        student_id = input('学号: ').strip()
        password = input('密码: ').strip()
        confirm = input('确认密码: ').strip()
        if password != confirm:
            print('两次密码不一致')
            sys.exit(1)
        if len(password) < 8:
            print('密码至少8位')
            sys.exit(1)
        if not any(c.isupper() for c in password):
            print('密码需包含大写字母')
            sys.exit(1)
        if not any(c.islower() for c in password):
            print('密码需包含小写字母')
            sys.exit(1)
        if not any(c.isdigit() for c in password):
            print('密码需包含数字')
            sys.exit(1)
        with app.app_context():
            user = User.query.filter_by(student_id=student_id).first()
            if user:
                user.role = 'super_admin'
                user.set_password(password)
                db.session.commit()
                print(f'已将 {student_id} 提升为超级管理员')
            else:
                user = User(student_id=student_id, role='super_admin')
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                print(f'已创建超级管理员 {student_id}')
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == 'revoke-admin':
        student_id = input('学号: ').strip()
        if not student_id:
            print('学号不能为空')
            sys.exit(1)
        with app.app_context():
            user = User.query.filter_by(student_id=student_id).first()
            if not user:
                print(f'用户 {student_id} 不存在')
                sys.exit(1)
            if user.role != 'super_admin':
                print(f'{student_id} 不是超级管理员')
                sys.exit(1)
            user.role = 'user'
            user.admin_permissions = ''
            db.session.commit()
            print(f'已撤销 {student_id} 的超级管理员权限')
        sys.exit(0)

    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)