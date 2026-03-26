from decimal import Decimal

from django import template

from sales.models import get_sales_unit_price


register = template.Library()


@register.filter
def sales_price(value):
    """
    Template helper for showing the sales-side price without mutating the
    stored product base price.
    """
    if value in (None, ""):
        return Decimal("0.00")
    return get_sales_unit_price(value)
