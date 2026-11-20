from decimal import Decimal
from django import template
register=template.Library()
@register.filter
def amount(value):
    if value is None:return '—'
    try:return f'{Decimal(value):,.0f}'.replace(',','.')
    except (ValueError,TypeError):return value
@register.filter
def initials(value):
    parts=str(value).split();return ''.join(p[0] for p in parts[:2]).upper()
@register.filter
def dictitems(value):return value.items() if isinstance(value,dict) else []
