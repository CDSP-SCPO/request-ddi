from django import template

register = template.Library()


@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return None


@register.filter
def dict_get(d, key):
    return d.get(key)


@register.filter
def replace_two(value, args):
    try:
        old, new = args.split("|")
        return str(value).replace(old, new)
    except ValueError:
        return value
