from django.contrib import admin

from .models import Decision, FinalChoice, SpendingRecord


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


@admin.register(FinalChoice)
class FinalChoiceAdmin(admin.ModelAdmin):
    list_display = [
        "consideration",
        "choice_type",
        "alternative",
        "decided_on",
        "created_at",
    ]
    list_filter = ["choice_type", "decided_on"]
    search_fields = ["consideration__product_name", "memo"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SpendingRecord)
class SpendingRecordAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "consideration",
        "product_name",
        "purchase_status",
        "product_price",
        "monthly_budget_snapshot",
        "budget_amount_snapshot",
        "satisfaction",
        "recorded_on",
        "purchased_on",
    ]
    list_filter = ["purchase_status", "category", "recorded_on"]
    search_fields = [
        "user__username",
        "consideration__product_name",
        "product_name",
        "category",
        "purpose_snapshot",
        "purpose_detail_snapshot",
    ]
    readonly_fields = ["created_at", "updated_at"]
