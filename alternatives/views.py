from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def category_alternatives(request, pk):
    return render(
        request,
        "alternatives/category_alternatives.html",
        {"consideration_id": pk},
    )
