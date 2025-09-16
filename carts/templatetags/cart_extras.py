from django import template
register = template.Library()

@register.filter
def divided_by(value, arg):
    """Divide value by arg with float result"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0