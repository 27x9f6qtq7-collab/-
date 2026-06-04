from flask import Blueprint

bp = Blueprint('main', __name__)

from app.main.views import index, item, order, bargain, message, private_message, user_center, feedback
