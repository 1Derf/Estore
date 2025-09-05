from django import template

register = template.Library()

@register.filter
def lookup(queryset, field):
    return queryset.values_list(field, flat=True)