# components/pagination.py
from flask import request


def get_paginated_data(items, per_page=20, search_fields=None):
    """
    返回 (page_items, page, per_page, total, search)
    items: 原始完整 list
    """
    page = max(1, int(request.args.get('page', 1)))
    per_page = max(1, min(100, per_page))
    search = request.args.get('search', '').strip()


    filtered = items
    if search and search_fields:
        search_lower = search.lower()
        filtered = [
            item for item in items
            if any(search_lower in str(item.get(field, '') or '').lower() for field in search_fields)
        ]


    total = len(filtered)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = filtered[start_idx:end_idx]

    return page_items, page, per_page, total, search