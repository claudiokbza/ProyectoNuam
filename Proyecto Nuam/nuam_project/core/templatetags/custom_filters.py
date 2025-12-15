from django import template

register = template.Library()

@register.filter
def get_factor_value(obj, factor_number):
    # Convierte el número 8 en 'factor_08' y busca el valor en el objeto
    field_name = f'factor_{int(factor_number):02d}'
    return getattr(obj, field_name, 0)