from django import template
from ..forms import valor_html

register = template.Library()


@register.filter
def fv(valores, nombre):
    return valor_html((valores or {}).get(nombre))


@register.filter
def fe(errores, nombre):
    return (errores or {}).get(nombre)
