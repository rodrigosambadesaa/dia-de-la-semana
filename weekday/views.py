from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .parser import DateInputError, parse_date


@require_http_methods(["GET", "POST"])
def index(request):
    date_value = ""
    language = ""
    order = "auto"
    result = None
    error = None
    if request.method == "POST":
        date_value = request.POST.get("date", "")
        language = request.POST.get("language", "")
        order = request.POST.get("order", "auto")
        try:
            result = parse_date(
                date_value, language=language, order=order,
                accept_language=request.headers.get("Accept-Language", ""),
            )
        except DateInputError as exc:
            error = str(exc)
    return render(request, "weekday/index.html", {
        "date_value": date_value, "language": language,
        "order": order, "result": result, "error": error,
    })
