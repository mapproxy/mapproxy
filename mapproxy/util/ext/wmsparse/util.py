import re

xpath_elem = re.compile(r'(^|/)([^/]+:)?([^/]+)')


def resolve_ns(xpath, namespaces, default=None):
    """
    Resolve namespaces in xpath to absolute URL as required by etree.
    """
    def repl(match):
        ns = match.group(2)
        if ns:
            abs_ns = namespaces.get(ns[:-1], default)
        else:
            abs_ns = default

        if not abs_ns:
            return '%s%s' % (match.group(1), match.group(3))
        else:
            return '%s{%s}%s' % (match.group(1), abs_ns, match.group(3))

    return xpath_elem.sub(repl, xpath)
