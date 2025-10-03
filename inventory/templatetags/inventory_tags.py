from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="pipe_breaks")
def pipe_breaks(value: str | None) -> str:
    """Convert pipe-delimited titles into <br>-separated HTML."""
    if not value:
        return ""

    segments = [escape(part.strip()) for part in str(value).split("|") if part.strip()]
    if not segments:
        return ""

    return mark_safe("<br>".join(segments))
