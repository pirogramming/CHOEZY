from django.shortcuts import render


def category_select(request):
    return render(request, "analyses/category_select.html")


def criteria_select(request):
    return render(request, "analyses/criteria_select.html")


def comparison(request):
    return render(request, "analyses/comparison.html")


def result(request):
    return render(request, "analyses/result.html")