from django import template

register = template.Library()


@register.filter
def get_item_at_index(lst, index):
    """Retrieve an element from a list using an index."""
    try:
        return lst[index]
    except (IndexError, TypeError):
        return None
