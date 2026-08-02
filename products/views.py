from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView

from .forms import ConsiderationForm
from .models import Consideration


class ConsiderationCreateView(LoginRequiredMixin, CreateView):
    """구매 고민 입력 (docs/API.md §5.1).

    JSON API가 아니라 폼 페이지입니다. 성공하면 대안 생성 페이지로
    리다이렉트하고, 실패하면 폼 에러가 렌더된 입력 화면을 그대로 돌려줍니다.
    """

    model = Consideration
    form_class = ConsiderationForm
    template_name = "products/consideration_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        return super().form_valid(form)

    def get_success_url(self):
        # alternatives 페이지가 아직 없어 URL 이름 대신 경로를 직접 씁니다.
        return f"/alternatives/considerations/{self.object.pk}/"
