from django.contrib import admin

from .models import Decision


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = [
        "consideration",
        "purpose_fit",
        "expected_satisfaction",
        "recommendation",
        "ai_model",
        "created_at",
    ]
    list_filter = ["purpose_fit", "expected_satisfaction", "recommendation"]
    search_fields = ["consideration__product_name", "summary"]
    readonly_fields = ["created_at", "updated_at"]
