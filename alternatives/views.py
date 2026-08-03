from django.shortcuts import render


def category_alternatives(request):
    return render(request, "alternatives/category_alternatives.html")