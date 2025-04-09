def escape_html(data):
    """
    Escape user-provided input data for safe inclusion in HTML _and_ JS to prevent XSS.
    """
    data = data.replace('&', '&amp;')
    data = data.replace('>', '&gt;')
    data = data.replace('<', '&lt;')
    data = data.replace("'", '')
    data = data.replace('"', '')
    return data
