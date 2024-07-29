from django import template

register = template.Library()


@register.filter
def remove_chars(value):
    return value.replace("-", "").replace(" ", "")

