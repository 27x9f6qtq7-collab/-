from flask import jsonify
from . import bp

@bp.route('/')
def index():
    return jsonify({'message': 'API v1'})