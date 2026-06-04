from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.models import Setting
from app.utils import admin_required
from app.admin import bp

@bp.route('/agreements', methods=['GET', 'POST'])
@login_required
@admin_required
def agreements():
    if request.method == 'POST':
        agreement_type = request.form.get('type')
        content = request.form.get('content')
        if agreement_type == 'privacy':
            Setting.set('privacy_policy', content)
        elif agreement_type == 'terms':
            Setting.set('service_terms', content)
        elif agreement_type == 'disclaimer':
            Setting.set('disclaimer', content)
        flash('协议内容已更新', 'success')
        return redirect(url_for('admin.agreements'))
    privacy = Setting.get('privacy_policy', '')
    terms = Setting.get('service_terms', '')
    disclaimer = Setting.get('disclaimer', '')
    return render_template('admin/agreements.html', privacy=privacy, terms=terms, disclaimer=disclaimer)