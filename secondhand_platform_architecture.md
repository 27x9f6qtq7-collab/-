# 二手寄售平台逻辑架构与依赖关系文档


> 📅 生成日期：2026-06-01


---


# 第 1 章：项目概览与技术栈

## 1.1 项目定位

二手寄售平台是一个面向校园场景的轻量级 Web 应用。它解决的核心问题是：在校学生需要一个安全可信的渠道来发布、浏览和交易二手商品，而校外的闲鱼、转转等平台缺乏校内身份背书，交易纠纷难以追溯。

平台以"学号"作为用户唯一标识——注册、登录、管理员权限全部围绕学号展开，天然契合校园场景中"身份可验证、行为可追溯"的需求。功能覆盖了二手交易的完整闭环：商品发布与分类浏览、订单创建与状态流转、买家砍价与卖家回复、站内私信沟通、用户反馈提交，以及管理后台的全面管控。

## 1.2 技术栈总览

整个项目基于 Flask 生态构建，依赖清单仅 9 行，是一条典型的"够用就好"的 Python 轻量栈。

| 依赖包 | 最低版本 | 在项目中的具体职责 |
|--------|---------|------------------|
| `flask` | 2.0.0 | Web 框架核心：路由分发、请求响应、模板渲染、CLI 命令 |
| `flask-sqlalchemy` | 2.5.0 | ORM 层：17 个模型类的定义、查询、关系映射，对接 SQLite |
| `flask-login` | 0.6.0 | 会话管理：登录态维护、`current_user` 代理、`@login_required` 保护路由 |
| `flask-mail` | 0.9.1 | 邮件服务：密码重置邮件的发送（通过 QQ 邮箱 SMTP） |
| `openpyxl` | 3.0.0 | Excel 读写：管理后台的订单/商品数据导出功能 |
| `apscheduler` | 3.9.0 | 后台定时调度：订单超时自动取消（每 1 分钟）、数据库每日备份 |
| `python-dateutil` | 2.8.0 | 日期工具：灵活的日期解析与计算 |
| `werkzeug` | 2.0.0 | WSGI 工具集：密码哈希（`generate_password_hash`/`check_password_hash`） |
| `pillow` | 9.0.0 | 图片处理：用户上传头像的缩放与格式转换 |

依赖之间形成了清晰的层次：Flask 是骨架，Flask-SQLAlchemy 和 Flask-Login 是血肉，APScheduler 是心跳，其余组件各司其职。没有引入 Redis、Celery 等重量级中间件，所有数据跑在单文件 SQLite 上——对于一个校园场景的并发量而言，这完全够用。

## 1.3 目录结构

项目根目录下的核心文件不超过 10 个，真正的业务逻辑全部收敛在 `app/` 包内。

```
secondhand_project/
├── run.py                     # 启动入口：创建 app 实例 + CLI 管理命令
├── config.py                  # 配置类：密钥、数据库路径、上传限制、邮件参数
├── requirements.txt           # 依赖清单（9 行）
├── start.bat                  # Windows 一键启动脚本
├── instance/                  # Flask 实例目录（自动创建）
│   ├── .secret_key            # 随机生成的密钥文件
│   └── secondhand.db          # SQLite 数据库文件
└── app/
    ├── __init__.py            # Flask 工厂函数：create_app() 启动链
    ├── models.py              # 17 个 SQLAlchemy 模型（~330 行）
    ├── utils.py               # 工具函数集：验证、通知、日志、装饰器、定时任务
    ├── forms.py               # Flask-WTF 表单（目前为空壳，预留扩展）
    ├── main/                  # 前台蓝图（用户端所有页面）
    │   ├── __init__.py        # Blueprint('main')
    │   └── views/             # 8 个视图模块
    ├── auth/                  # 认证蓝图（/auth 前缀）
    │   ├── __init__.py        # Blueprint('auth')
    │   └── routes.py          # 登录、注册、登出、密码重置
    ├── admin/                 # 后台管理蓝图（/admin 前缀）
    │   ├── __init__.py        # Blueprint('admin') + 权限映射表 + before_request 钩子
    │   └── views/             # 12 个视图模块
    ├── api/                   # API 蓝图（/api 前缀，目前仅健康检查）
    ├── templates/             # Jinja2 模板（30+ 个 .html）
    ├── static/                # 静态资源（上传文件、头像、背景图）
    └── backups/               # 数据库自动备份目录
```

整体来看，这是一个标准的 Flask 单体应用——没有拆微服务，没有消息队列，但分层清晰：路由在 views/ 里，业务逻辑散落在 views/ 和 utils.py 里，数据访问统一走 SQLAlchemy ORM。



---


# 第 2 章：逻辑架构与配置管理

## 2.1 四层架构

从代码组织方式和运行时调用链路来看，平台呈现清晰的分层结构：

```
┌─────────────────────────────────────────────────────┐
│  路由层（Route Layer）                                │
│  main/views/  auth/routes.py  admin/views/          │
│  接收 HTTP 请求 → 参数校验 → 调用业务逻辑 → 渲染模板   │
├─────────────────────────────────────────────────────┤
│  业务逻辑层（Business Logic Layer）                   │
│  utils.py 工具函数 + views 中的业务处理逻辑            │
│  订单号生成、通知发送、权限判断、文件验证、数据聚合     │
├─────────────────────────────────────────────────────┤
│  数据访问层（Data Access Layer）                      │
│  Flask-SQLAlchemy ORM（models.py 17 个模型类）        │
│  User.query / Item.query / db.session.add / commit   │
├─────────────────────────────────────────────────────┤
│  数据存储层（Storage Layer）                          │
│  SQLite (instance/secondhand.db)                    │
│  + 文件系统 (static/uploads/ 用户上传)                │
│  + 文件系统 (backups/ 每日备份)                       │
└─────────────────────────────────────────────────────┘
```

值得注意的是，这个分层并不是通过独立的 Python 包或模块边界强制实现的——路由层和业务逻辑层在实际代码中往往混在同一个 views/*.py 文件里。但它为理解系统提供了有用的认知框架：HTTP 请求从最上层进入，经业务处理，最终落到 SQLite 或文件系统。

## 2.2 蓝图路由体系

应用通过三个 Flask Blueprint 将路由按职能拆分，各自挂载在不同的 URL 前缀下：

| 蓝图 | 内部名称 | URL 前缀 | 视图模块数 | 职责 |
|------|---------|----------|----------|------|
| `main` | main_bp | `/`（根路径） | 8 | 前台用户端：首页、商品、订单、砍价、消息、私信、个人中心、反馈 |
| `auth` | auth_bp | `/auth` | 1 (routes.py) | 认证：登录、注册、登出、密码重置 |
| `admin` | admin_bp | `/admin` | 12 | 管理后台：仪表盘、商品、订单、分类、用户、公告、设置、协议、日志、导出、反馈、草稿 |

此外还有一个预留的 `api` 蓝图（`/api` 前缀），当前仅包含一个返回 `{"message": "API v1"}` 的健康检查端点，为后续移动端或第三方对接留了扩展口。

蓝图之间没有直接的代码依赖——它们通过共享的模型层（`app.models`）和工具层（`app.utils`）间接协作。auth 蓝图管理登录态，main 和 admin 通过 `flask-login` 的 `current_user` 代理读取当前用户信息并做权限判断。

## 2.3 应用初始化链路

`create_app()` 工厂函数（位于 `app/__init__.py`）是理解整个启动过程的关键。它的执行步骤可以概括为一条 11 步的流水线：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | `Flask(__name__)` | 创建 Flask 实例，加载 Config 配置类 |
| 2 | `os.makedirs` | 确保 instance 目录和 uploads 目录存在 |
| 3 | `app.add_template_filter` | 注册 `from_json` Jinja2 过滤器，模板中可直接解析 JSON 字符串 |
| 4 | `db.init_app(app)` | 将 SQLAlchemy 绑定到 app |
| 5 | `login_manager.init_app(app)` | 将 LoginManager 绑定到 app，未登录用户重定向至 `auth.login` |
| 6 | `csrf.init_app(app)` | 启用 CSRF 保护（Flask-WTF），Token 有效期 1 小时 |
| 7 | `db.create_all()` | 在应用上下文中自动建表（所有 17 个模型） |
| 8 | `login_manager.user_loader` | 注册用户加载回调，Flask-Login 通过 `User.query.get(int(user_id))` 恢复会话 |
| 9 | `before_request` 钩子 | 每次请求更新 `current_user.last_active` 时间戳，用于在线状态判断 |
| 10 | 注册三个蓝图 | 按顺序注册 main → auth（`/auth`）→ admin（`/admin`） |
| 11 | 启动定时任务 | 注册两个 APScheduler Job 并启动调度器（时区：`Asia/Shanghai`） |

两步定时任务的注册值得单独说明：

- **订单超时取消**：`interval` 触发器，每 60 秒执行一次。遍历所有 `status='pending'` 且创建时间超过 10 分钟的订单，将其状态改为 `cancelled`，同时将关联商品重新上架（如果之前因下单而下架）。
- **数据库备份**：`cron` 触发器，每日北京时间凌晨 1:00 执行。将 `secondhand.db` 复制到 `app/backups/` 目录，文件名带时间戳；同时清理超过 30 天的旧备份。

两个 Job 都通过闭包包装了 `app.app_context()`，确保在调度器线程中能正常访问数据库。

## 2.4 配置管理策略

`config.py` 的核心设计原则是"零硬编码敏感信息"。

| 配置项 | 取值策略 | 安全考量 |
|--------|---------|---------|
| `SECRET_KEY` | 优先级：环境变量 `SECRET_KEY` > `instance/.secret_key` 文件 > 首次自动生成 `os.urandom(24).hex()` 并写入文件 | 密钥不进入版本控制，部署时可通过环境变量覆盖 |
| `SQLALCHEMY_DATABASE_URI` | 固定为 `sqlite:///instance/secondhand.db` | SQLite 单文件，无需额外数据库服务 |
| `UPLOAD_FOLDER` | `app/static/uploads` | 上传文件放在静态目录下，可通过 URL 直接访问 |
| `ALLOWED_EXTENSIONS` | 图片（png/jpg/jpeg/gif/webp）+ 视频（mp4/webm/mov/avi） | 配合 `utils.validate_file_content()` 的魔数验证，双重防伪装 |
| `MAX_CONTENT_LENGTH` | 100MB | 防止恶意上传撑爆磁盘 |
| `WTF_CSRF_ENABLED` | True，Token 有效期 3600 秒 | 所有 POST/PUT/DELETE 请求需携带 CSRF Token |
| `MAIL_*` | QQ 邮箱 SMTP，用户名和密码从环境变量读取 | 邮件凭据不入代码，部署时按需配置 |

一个值得注意的细节：邮件配置是"软依赖"——如果环境变量未设置，`MAIL_USERNAME` 和 `MAIL_PASSWORD` 为空字符串，邮件发送会静默失败而不是抛异常。这意味着密码重置功能在开发环境中可以跳过，不影响其他功能。



---


# 第 3 章：数据模型与实体关系

## 3.1 模型总览

`app/models.py` 定义了 17 个 SQLAlchemy 模型类，可以分为六个业务域。每个模型只列出其区别于通用字段（id、created_at）的核心业务字段。

### 3.1.1 用户与权限

| 模型 | 表名 | 核心字段 |
|------|------|---------|
| **User** | `users` | `student_id`(唯一，学号), `email`, `password_hash`, `role`(user/admin/super_admin), `admin_permissions`(JSON 权限数组), `avatar`, `login_attempts`, `locked_until`, `last_active` |

User 是整个系统关联最密集的模型——几乎所有其他模型都通过 `db.ForeignKey('users.id')` 指向它。它同时承担了认证（密码哈希、登录尝试计数、锁定机制）和授权（角色 + 细粒度权限 JSON）的双重职责。

### 3.1.2 商品与分类

| 模型 | 表名 | 核心字段 |
|------|------|---------|
| **Category** | `categories` | `name`, `parent_id`(自引用外键), `sort_order` |
| **Item** | `items` | `title`, `description`, `price`, `image_url`, `detail_images`(JSON), `status`(on_sale/off_sale), `quantity`, `is_featured`, `condition`, `allow_bargain`, `seller_id`, `category_id` |

Category 通过 `parent_id` 自引用（`parent → children`）实现无限级分类树，`level()` 方法递归计算当前节点深度。`total_item_count` 属性递归统计该分类及其所有后代下的在售商品数量——这意味着一次属性访问可能触发多次数据库查询，在高分类层级下需要注意性能。

Item 的 `detail_images` 以 JSON 文本存储多张图片路径，`status` 字段控制商品的上架/下架状态，与订单系统联动（下单取下架，取消/超时恢复上架）。

### 3.1.3 交易与议价

| 模型 | 表名 | 核心字段 |
|------|------|---------|
| **Order** | `orders` | `order_number`(唯一，时间戳+随机数), `total_price`, `status`(pending→paid→shipped→completed/cancelled), `snapshot`(JSON 商品快照), `buyer_note`, `buyer_id`, `item_id` |
| **Bargain** | `bargains` | `offered_price`(买家出价), `status`(pending/accepted/rejected), `replied_at`, `item_id`, `buyer_id` |

Order 的 `snapshot` 字段是防止"卖家改价"的关键设计：下单时把商品的标题、价格、描述等序列化为 JSON 存入订单，即使后续卖家修改了商品信息，订单中的快照不受影响。

### 3.1.4 消息与互动

| 模型 | 表名 | 核心字段 |
|------|------|---------|
| **Message** | `messages` | `title`, `content`, `is_read`, `sender_id`, `receiver_id` |
| **PrivateMessage** | `private_messages` | `content`, `is_read`, `sender_id`, `receiver_id` |
| **Announcement** | `announcements` | `title`, `content`, `is_active` |
| **ItemComment** | `item_comments` | `content`, `item_id`, `user_id` |

Message 是系统级通知（订单状态变更、超时取消提醒等），`sender_id` 可为空（系统自动发送）。PrivateMessage 是用户间点对点私信，两者分表存储。ItemComment 是商品评论区。

### 3.1.5 管理与审计

| 模型 | 表名 | 核心字段 |
|------|------|---------|
| **AdminLog** | `admin_logs` | `action`, `target_type`, `target_id`, `details`, `ip_address`, `admin_id`, `admin_name` |
| **AdminReadStatus** | `admin_read_status` | `module`(order/feedback), `last_read_time`, `admin_id`（唯一约束 `unique_admin_module`） |
| **Blacklist** | `blacklists` | `user_id`, `blocked_id`（唯一约束 `unique_block`） |
| **Setting** | `settings` | `key`(唯一), `value`（提供 `get()`/`set()` 静态方法） |

Setting 模型实现了一个简单的键值存储，用于系统级配置项（背景类型、联系方式等）。它绕过了 config.py 的静态配置限制——管理员在后台修改后立即生效，无需重启应用。

### 3.1.6 辅助模型

| 模型 | 表名 | 核心字段 |
|------|------|---------|
| **Draft** | `drafts` | `title`, `description`, `price`, `category_id`, `allow_bargain`, `user_id` |
| **Feedback** | `feedbacks` | `title`, `content`, `status`(pending/resolved), `reply`, `replied_by`, `user_id` |
| **SearchHistory** | `search_history` | `keyword`, `user_id` |
| **BrowseHistory** | `browse_history` | `item_id`, `user_id` |

Draft 与 Item 的字段高度重叠——它本质上是"未发布的商品"的快照。SearchHistory 和 BrowseHistory 为个性化推荐和数据统计提供了基础数据。

## 3.2 实体关系图

以下文字版 ER 图展示了核心实体之间的关联方向和外键依赖：

```
                           ┌──────────────┐
                           │    User      │
                           │  (users)     │
                           └──┬───┬───┬──┘
                              │   │   │
        ┌─────────────────────┤   │   ├──────────────────────┐
        │                     │   │                          │
        ▼                     │   ▼                          ▼
┌──────────────┐              │ ┌──────────────┐   ┌──────────────────┐
│    Item      │              │ │    Order     │   │  Message /       │
│   (items)    │──────────────┤ │   (orders)   │   │  PrivateMessage  │
│  seller_id ──┼── User       │ │  buyer_id ───┼───│  sender_id ──────┼── User
│  category_id─┼── Category   │ │  item_id ────┼───│  receiver_id ────┼── User
└──────┬───────┘              │ │  snapshot ───┼── Item(JSON)         │
       │                      │ └──────────────┘   └──────────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐     ┌──────────────┐
│   Category   │     │   Bargain    │
│ (categories) │     │  (bargains)  │
│  parent_id ──┼─┐   │  item_id ────┼── Item
│              │ │   │  buyer_id ───┼── User
│  children ◄──┼─┘   └──────────────┘
└──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  AdminLog    │     │  Blacklist   │     │   Setting    │
│  admin_id ───┼─User│  user_id ────┼─User│  独立存储    │
└──────────────┘     │  blocked_id ─┼─User│  key → value │
                     └──────────────┘     └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Draft     │     │  Feedback    │     │SearchHistory │
│  user_id ────┼─User│  user_id ────┼─User│  user_id ────┼─User
│  category_id─┼─Cat │  replied_by ─┼─User│BrowseHistory │
└──────────────┘     └──────────────┘     │  user_id ────┼─User
                                          │  item_id ────┼─Item
                                          └──────────────┘
```

两点值得注意的设计选择：

1. **没有显式的"卖家-订单"关系**。Order 通过 `item_id → Item → seller_id` 间接关联卖家，而不是直接存 `seller_id`。这样做的好处是订单永远指向具体商品而非卖家本人，避免了"卖家被删除后订单找不到商品"的问题。
2. **用户自引用出现在两个地方**：Category 的 `parent → children`（无限级分类树），Blacklist 的 `user → blocked`（拉黑关系）。前者用 `remote_side=[id]` 显式指定了外键的远端。

## 3.3 用户权限体系

权限体系是平台设计中复杂度最高的部分，它实现了一个三级角色 + 细粒度权限的组合模型。

### 3.3.1 角色分级

| 角色 | role 字段值 | 能力边界 |
|------|-----------|---------|
| 普通用户 | `user` | 浏览商品、下单购买、砍价、私信、发布商品、提交反馈 |
| 普通管理员 | `admin` | 同普通用户 + 后台访问，但具体能力由 `admin_permissions` JSON 字段决定 |
| 超级管理员 | `super_admin` | 所有功能无限制，`has_permission()` 始终返回 True |

### 3.3.2 细粒度权限控制

`admin_permissions` 字段存储一个 JSON 数组，例如 `["item_manage", "order_manage"]`。目前定义了五种权限标识：

| 权限标识 | 控制范围 |
|---------|---------|
| `item_manage` | 商品的增删改查、上下架、精选标记 |
| `order_manage` | 订单的状态更新和删除 |
| `category_manage` | 分类的增删改 |
| `user_manage` | 用户管理、角色分配、权限编辑、密码重置、删除用户 |
| `announcement_manage` | 公告的增删改、启用/停用切换 |

### 3.3.3 权限拦截机制

权限拦截的关键代码在 `app/admin/__init__.py` 的 `before_request` 钩子中。它按三级优先级判断：

1. **超级管理员**：直接放行，不做任何权限检查。
2. **公开端点**（`PUBLIC_ADMIN_ENDPOINTS`）：dashboard、stats、标记已读等，所有管理员均可访问。
3. **普通管理员**：查询 `PERMISSION_MAP` 字典——当前路由端点映射到哪个权限标识，再调用 `current_user.has_permission(perm)` 检查。如果路由不在映射表中且不是公开端点，默认返回 403。

这意味着新增一个后台管理功能，如果不显式加入 `PERMISSION_MAP` 或 `PUBLIC_ADMIN_ENDPOINTS`，普通管理员将无法访问——这是一种"默认拒绝"的安全策略。

未在映射表中的端点（settings、logs、export、agreement、feedback、draft）对普通管理员一律返回 403。如果将来需要让普通管理员访问这些模块，只需在 `PERMISSION_MAP` 中添加对应的映射条目并定义新的权限标识即可。



---


# 第 4 章：核心业务模块

平台的业务功能分布在三个蓝图中。本章按模块逐一拆解关键逻辑，不追求逐行解释代码，而是聚焦于"数据怎么流转、状态怎么变化、边界条件怎么处理"。

## 4.1 认证模块

认证模块集中在 `auth` 蓝图（`/auth` 前缀），核心流程如下：

```
注册 → 登录 → session 维持 → before_request 活跃追踪 → 登出
  │                │
  └── 密码重置（邮件）──┘
```

**注册**：以学号（`student_id`）为唯一标识。学号和密码由用户填写，后端做基础的密码强度校验（≥8 位、含大小写字母和数字）。User 模型创建时 `role` 默认为 `user`。

**登录**：`check_password()` 通过 werkzeug 的哈希比对验证密码。如果密码错误，`login_attempts` 递增；达到阈值后设置 `locked_until` 锁定字段，阻止短期内暴力尝试。

**会话维持**：Flask-Login 管理 cookie-based session。`user_loader` 回调通过 `User.query.get(int(user_id))` 从数据库恢复用户对象，每次请求都会触发。

**活跃追踪**：`app/__init__.py` 中的 `before_request` 钩子在每次请求时更新 `current_user.last_active = datetime.utcnow()`。User 模型的 `is_online` 属性（5 分钟内活跃视为在线）和 `last_active_display` 属性（返回"在线""X 分钟前在线"等人性化文本）都依赖这个时间戳。

**密码重置**：通过 Flask-Mail 发送重置链接。重置 Token 由 `uuid.uuid4().hex` 生成，有效期 1 小时。注意邮件凭据来自环境变量——如果未配置，此功能不可用但不会阻塞其他功能。

## 4.2 商品与分类模块

### 4.2.1 商品生命周期

商品在前台和后台各有一组视图。前台负责"用户能做什么"，后台负责"管理员能管什么"。

```
用户：创建草稿 → 发布 → 编辑 → （被下单后自动下架）→ （超时取消后自动上架）
管理员：查看列表 → 上架/下架切换 → 精选标记 → 删除
```

发布商品时需要上传封面图（`image_url`）和详情图（`detail_images`，JSON 数组）。文件上传有两层防护：`allowed_file()` 校验扩展名，`validate_file_content()` 校验文件头魔数——防止把 `.exe` 改名为 `.jpg` 上传。

### 4.2.2 分类树

Category 通过 `parent_id` 自引用构建树形结构。三个辅助能力值得注意：

- `level()` 方法递归向上计算层级深度（一级=0，二级=1，三级=2），模板中可用于渲染不同级别的样式。
- `total_item_count` 属性递归统计该分类及所有后代下在售商品数。这个属性在每次访问时执行多次数据库查询，分类越深、查询越多。
- `sort_order` 字段控制同级分类的显示顺序，管理员可在后台拖拽排序。

## 4.3 订单交易模块

订单模块是平台中状态机最复杂的部分。

### 4.3.1 订单状态流转

```
pending（待支付）
  ├── 用户支付 → paid（已支付）
  │                └── 卖家发货 → shipped（已发货）
  │                                 └── 买家确认 → completed（已完成）
  └── 超时 10 分钟自动取消 → cancelled（已取消）
                                └── 关联商品自动恢复上架
```

下单时系统做两件事：调用 `generate_order_number()` 生成 `YYYYMMDDHHmmss + 6 位随机数` 格式的订单号，把商品当前信息序列化为 JSON 存入 `snapshot` 字段，然后将商品状态改为 `off_sale`。

"支付"环节在代码中是一个模拟操作——没有接入真实支付网关（代码中 `static/images/` 下有支付二维码图片，但订单状态变更是手动触发的）。这意味着在实际部署中，订单从 `pending` 到 `paid` 的转换需要额外集成。

### 4.3.2 超时自动取消

这是第 2 章提到的定时任务的核心逻辑（`utils.auto_cancel_timeout_orders()`）：

```python
timeout_limit = datetime.utcnow() - timedelta(minutes=10)
timeout_orders = Order.query.filter(
    Order.status == 'pending',
    Order.created_at <= timeout_limit
).all()
```

对每个超时订单：状态改为 `cancelled`，关联商品如果处于 `off_sale` 则恢复为 `on_sale`，向买家发送系统通知。整个过程在一个 `db.session.commit()` 中完成，保证了"取消订单 + 恢复商品"的原子性。

## 4.4 砍价模块

砍价逻辑相对简单，但交互链条涉及两个用户角色：

```
买家出价 → Bargain 记录创建（status=pending）
  ├── 卖家接受 → status=accepted，商品按砍价价格出售
  └── 卖家拒绝 → status=rejected
```

砍价记录包含 `offered_price`（买家报价）、`replied_at`（卖家回复时间）等字段。卖家的砍价管理页面和买家的砍价记录页面分别对应两组不同的视图函数。

砍价成功后，买家需要以砍价价格重新下单——砍价本身不自动生成订单。这意味着如果卖家在砍价接受后又改了商品原价，砍价结果可能失效。

## 4.5 消息与私信模块

系统内有两套消息机制：

| 类型 | 模型 | 触发方式 | 典型场景 |
|------|------|---------|---------|
| 系统通知 | Message | 后端自动发送（`utils.send_notification()`） | 订单超时取消、订单状态变更 |
| 用户私信 | PrivateMessage | 用户间手动发送 | 买卖双方沟通细节 |
| 站内信 | Message | 管理员手动发送 | 系统公告补充、定向通知 |

Message 的 `sender_id` 可为空（代表系统），`title` + `content` 结构适合展示在通知列表中。PrivateMessage 只有 `content` 字段，类似即时通讯的对话模式。

未读消息数量通过 `utils.inject_settings()` 上下文处理器注入到所有模板，导航栏上可以实时显示红点徽标。

## 4.6 管理后台权限系统

管理后台的权限控制已经在第 3 章建模层面介绍过。这里从运行时角度补充拦截流程：

```
请求进入 /admin/* 路由
  │
  ├── before_request: check_admin_permission()
  │     ├── 未登录 → login_required 重定向到登录页
  │     ├── 非管理员 → abort(403)
  │     ├── 超级管理员 → 直接放行（不检查 PERMISSION_MAP）
  │     ├── 公开端点（dashboard/stats/mark_read）→ 直接放行
  │     └── 普通管理员 → 查询 PERMISSION_MAP
  │           ├── 端点有映射 → 调用 has_permission(perm)
  │           │     ├── admin_permissions JSON 含该权限 → 放行
  │           │     └── 不含 → abort(403)
  │           └── 端点无映射 → abort(403)（默认拒绝）
  │
  └── 视图函数执行 → 操作前后调用 log_admin_action() 记录审计日志
```

这种设计下，新增一个"优惠券管理"功能只需三步：在 `PERMISSION_MAP` 中添加路由到权限的映射、定义新的权限标识（如 `coupon_manage`）、在创建管理员时勾选该权限。路由拦截和审计日志都自动生效，不需要修改视图函数代码。

一个值得注意的限制：`utils.py` 中虽然定义了 `permission_required(perm)` 装饰器用于函数级权限检查，但 admin 蓝图实际使用的是 `before_request` 的统一拦截——两者是互补的，装饰器更多用于 API 端点或非标准路由的权限控制。



---


# 第 5 章：基础设施支撑

如果说前四章描述的是平台的"骨架"和"血肉"，本章聚焦于让它持续稳定运转的"神经系统"——工具函数、定时任务和模块间的依赖关系。

## 5.1 工具函数层

`app/utils.py` 定义了 11 个函数，按职责可以归为四类。

### 5.1.1 文件安全

| 函数 | 职责 |
|------|------|
| `allowed_file(filename)` | 校验文件扩展名是否在 `ALLOWED_EXTENSIONS` 白名单内 |
| `validate_file_content(file_storage)` | 读取文件头 12 字节，比对魔数（PNG/JPEG/GIF/WebP/MP4），防止扩展名伪装攻击 |

两层防护的叠加逻辑是：先过扩展名白名单（快速过滤），再过魔数校验（精确识别）。后者特别处理了 WebP（需确认 `RIFF....WEBP` 完整头）和 MP4（需确认 `ftyp` box），避免了仅匹配"RIFF"前缀可能误判其他 RIFF 格式（如 AVI）的问题。

### 5.1.2 业务辅助

| 函数 | 职责 |
|------|------|
| `generate_order_number()` | 生成 `YYYYMMDDHHmmss + 6 位随机数` 格式的唯一订单号 |
| `send_notification(user_id, title, content, sender_id)` | 创建 Message 记录并提交——系统通知的标准入口 |
| `log_admin_action(action, ...)` | 创建 AdminLog 记录，自动附带请求路径、HTTP 方法和客户端 IP |
| `utc_to_local(utc_dt)` | UTC 时间 +8 小时转北京时间——但因为模板中未系统使用，实际还是以展示 UTC 时间为主 |

`log_admin_action()` 的设计值得单独提一下：它自动从 `request` 对象中提取 `remote_addr`、`path`、`method`，拼入 `details` 字段。这意味着只要视图函数在操作前后调用它，审计日志就自动包含"谁、什么时候、从哪个 IP、做了什么操作"的完整记录，不需要每个视图各自处理。

### 5.1.3 权限控制装饰器

| 装饰器 | 职责 |
|--------|------|
| `admin_required` | 检查 `current_user.is_admin`，非管理员返回 403 |
| `permission_required(perm)` | 检查 `current_user.has_permission(perm)`，无权限返回 403 |

这两个装饰器是"函数级"权限控制，与 admin 蓝图的 `before_request`（路由级）形成了双层防护。当前 admin 蓝图主要依赖 `before_request` 的统一拦截——它的优势是集中管理、不会遗漏新增路由。装饰器更适合 API 蓝图或未来需要更细粒度控制的场景。

### 5.1.4 上下文注入

| 函数 | 职责 |
|------|------|
| `inject_settings()` | 向所有 Jinja2 模板注入全局变量：未读消息数、背景配置、联系方式、自定义背景是否存在 |

这个函数在 `create_app()` 中通过 `app.context_processor(inject_settings)` 注册，意味着每个渲染的模板都能直接使用 `{{ unread_count }}`、`{{ setting_background_type }}` 等变量，不需要在每个视图函数中手动传参。

它同时承担了一个性能敏感的职责——每次模板渲染都会查询未读 Message 和 PrivateMessage 的计数。对于高并发场景，这个设计可能需要加缓存层。

## 5.2 定时任务

两个 APScheduler Job 的细节已在第 2 章介绍，这里补充它们的工程考量：

| 维度 | 订单超时取消 | 数据库备份 |
|------|------------|----------|
| 触发方式 | `interval`，60 秒 | `cron`，每日 1:00（北京时间） |
| 核心逻辑 | 筛选超 10 分钟未支付订单 → 取消 + 恢复商品 + 发通知 | 复制 `secondhand.db` → `backups/secondhand_backup_时间戳.db` |
| 失败处理 | 无显式异常捕获——如果某次执行失败，下一次（60 秒后）会重试 | 检查文件是否存在后才执行；过期备份（>30 天）自动清理 |
| 数据安全 | 取消操作和恢复商品在同一个 `commit()` 中完成，保证原子性 | 使用 `shutil.copy2()` 保留文件元数据 |

两个任务都通过 `app.app_context()` 包装执行，解决了 APScheduler 默认线程中无法访问 Flask-SQLAlchemy 的问题。调度器在 `create_app()` 末尾启动，确保了所有扩展初始化完毕后才开始定时触发。

当前的不足：订单超时取消每 60 秒扫描全表 `status='pending'` 的订单。虽然 SQLite 在小数据量下表现尚可，但如果订单量增长到数万级别，这种全表扫描会成为一个性能瓶颈——加一个 `created_at` 索引可以缓解，或者改用 Redis 的 TTL 过期机制。

## 5.3 模块依赖关系总览

以下表格展示了项目中各 Python 模块之间的 `import` 依赖关系。行是被依赖方（提供者），列是依赖方（引用方）。

| 被依赖 → 依赖 ↓ | app/__init__ | models | utils | config | main/views | admin/views | auth | api |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **app/__init__** | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| **models.py** | — | — | ✓ | — | ✓ | ✓ | ✓ | — |
| **utils.py** | ✓ | ✓ | — | — | ✓ | ✓ | — | — |
| **config.py** | ✓ | — | — | — | — | — | — | — |
| **main/views/\*** | — | ✓ | ✓ | — | — | — | — | — |
| **admin/views/\*** | — | ✓ | ✓ | — | — | — | — | — |
| **auth/routes.py** | — | ✓ | — | — | — | — | — | — |
| **api/routes.py** | — | — | — | — | — | — | — | — |

从这个依赖矩阵中可以读出几条关键信息：

1. **`app/__init__.py` 是唯一的上帝模块**——它 import 了几乎所有其他模块（通过蓝图注册）。这是 Flask 工厂模式的典型特征：工厂函数负责组装所有组件。
2. **`models.py` 是最纯粹的依赖提供方**——17 个视图模块都依赖它，但它自己不依赖任何业务模块。这是良好分层设计的标志。
3. **`utils.py` 有循环依赖风险**——它 import 了 `app.db` 和 `app.models`（通过 `from app import db`），同时 `app/__init__.py` import 了 `utils`。不过 Python 的模块缓存机制让这种循环在 Flask 应用上下文中是安全的。
4. **蓝图之间零直接依赖**——main 和 admin 的视图文件没有任何相互 import。它们的协作完全通过共享的 models 和 utils 完成，这在单体应用中是一种干净的解耦策略。

## 5.4 技术债务与改进方向

在完成全量代码分析后，有几处值得关注的改进点：

| 问题 | 影响 | 建议 |
|------|------|------|
| Category 递归查询 | `total_item_count` 每次访问触发多次 SQL，深分类场景下性能差 | 加 `item_count` 缓存字段，通过触发器或定时任务更新 |
| 订单超时全表扫描 | 订单量增长后每次扫描成本递增 | 在 `(status, created_at)` 上建复合索引 |
| 支付为模拟流程 | 订单从 pending→paid 无真实支付回调 | 接入微信/支付宝支付网关，或至少加支付凭证上传机制 |
| 无 API 鉴权 | api 蓝图无任何认证机制 | 如需对外开放，加 JWT 或 API Key 认证 |
| views 中业务逻辑比重高 | 视图函数直接写 SQLAlchemy 查询和业务判断 | 抽取 Service 层，降低视图函数复杂度 |

这些问题在校园场景的并发量下都不是致命问题——但它们是项目从"毕设级别"走向"生产级别"需要逐一解决的关卡。
