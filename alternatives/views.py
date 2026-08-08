from django.shortcuts import render


def category_alternatives(request, pk):
    return render(
        request,
        "alternatives/category_alternatives.html",
        {"consideration_id": pk},
    )