# CHOEZY API 명세서

> 기준 문서: [ERD.md](ERD.md)
> 아키텍처: **Django 템플릿 페이지(HTML) + JSON API 혼합**
> 인증: **Django 세션 인증** (`django.contrib.auth`)
> 구현 기준일: **2026-08-07**

---

## 1. 문서 목적과 범위

이 문서는 CHOEZY 서비스의 **URL 규격**을 정의합니다.

CHOEZY는 화면 전환이 많지 않고 로그인 상태가 항상 필요한 서비스이므로 다음과 같이 나눕니다.

| 구분 | 역할 | 응답 |
|---|---|---|
| **페이지 URL** | 화면 진입 (GET) | HTML |
| **JSON API URL** | 화면 안에서 일어나는 동작 | JSON |

**하나의 동작은 반드시 한 곳에만 존재합니다.** 같은 일을 하는 페이지 POST와 JSON API를 함께 두지 않습니다.

판단 기준은 **"동작이 끝난 뒤 화면이 바뀌는가"** 하나입니다.

| 동작 후 | 처리 | 예 |
|---|---|---|
| **다른 페이지로 이동** | Django Form + POST + 리다이렉트 | 회원가입, 로그인, 고민 생성, 고민 삭제, 최종 선택 |
| **같은 페이지에 머무름** | JSON API | 아이디 중복 확인, 상품 URL 미리보기, 계정 수정, 대안 생성·재생성·비교 |

폼 POST로 처리하는 동작에는 **JSON API를 만들지 않습니다.** 반대로 JSON API가 있는 동작에는 페이지 POST를 두지 않습니다. (§3의 두 표에 같은 동작이 중복되면 안 됩니다.)

> **고민 생성이 폼 POST인 이유**: URL 미리보기 결과 또는 직접 입력값을
> 사용자가 확인·수정한 뒤 저장하며, 저장 후 다음 화면으로 이동하기 때문입니다.
> URL에서 상품 정보를 가져오는 동작만 같은 화면의 JSON API로 분리합니다.

> **대안 생성이 JSON API인 이유**: 응답에 5~20초가 걸려 로딩 UI가 필요하고, 성공하면 같은 페이지에서 카드만 채웁니다.

> JSON API는 **Django REST Framework(DRF)** 로 구현합니다. 인증은
> `SessionAuthentication`, 기본 권한은 `IsAuthenticated`를 사용하고,
> 아이디 중복 확인처럼 공개가 필요한 API만 `AllowAny`를 지정합니다.

---

## 2. 공통 규약

### 2.1 Base URL

```text
개발: http://127.0.0.1:8000
```

### 2.2 URL 구조

```text
config/urls.py

""              → core.urls           페이지
"accounts/"     → accounts.urls       페이지
"products/"     → products.urls       페이지
"api/"          → config.api_urls     JSON API
```

`config/api_urls.py`에서 각 앱의 `api_urls.py`를 다시 include 합니다.

```python
# config/api_urls.py
urlpatterns = [
    path("accounts/", include("accounts.api_urls")),
    path("products/", include("products.api_urls")),
    path("alternatives/", include("alternatives.api_urls")),
    path("analyses/", include("analyses.urls")),
]
```

> 앱별 `urls.py`(페이지)와 `api_urls.py`(JSON)를 분리합니다. 계정 API 뷰는
> 현재 `accounts/views.py`에 함께 있고, 상품·대안 API 뷰는 각 앱의
> `api_views.py`에 있습니다.

### 2.3 인증

- 모든 요청은 **세션 쿠키(`sessionid`)** 로 인증합니다.
- 로그인이 필요한 페이지는 `@login_required` → 미로그인 시 `/accounts/login/?next=<원래 경로>` 로 **302 리다이렉트**.
- 로그인이 필요한 JSON API는 DRF `SessionAuthentication` 기준으로
  미로그인 시 **403 Forbidden**을 반환하며 로그인 페이지로 리다이렉트하지 않습니다.
- 공개 API인 아이디 중복 확인만 `AllowAny`를 사용합니다.

### 2.4 CSRF

상태를 변경하는 모든 요청(`POST` / `PATCH` / `DELETE`)에 CSRF 토큰이 필요합니다.

```javascript
fetch("/api/alternatives/12/regenerate/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": getCookie("csrftoken"),
  },
  body: JSON.stringify({}),
});
```

템플릿에서 토큰을 사용할 수 있도록 페이지에 `{% csrf_token %}`을 포함하거나 `@ensure_csrf_cookie`를 적용합니다.

### 2.5 요청 형식

- JSON API의 요청 본문은 `Content-Type: application/json` (UTF-8).
- 금액은 **원 단위 정수**로 주고받습니다. (`2200000`, 문자열 `"2,200,000"` 아님)
- 날짜는 `YYYY-MM-DD`, 일시는 ISO 8601 + KST 오프셋(`2026-07-30T14:03:21+09:00`).
- `equivalent_quantity`는 `Decimal(8, 2)`이므로 정밀도 손실을 막기 위해 **문자열**로 내려줍니다. (`"12.22"`)

### 2.6 응답 형식

**성공** — 리소스 객체를 그대로 반환합니다. 목록은 `results`로 감쌉니다.

```json
{
  "id": 12,
  "product_name": "MacBook Air M4",
  "product_price": 2200000
}
```

```json
{
  "count": 24,
  "page": 1,
  "page_size": 10,
  "has_next": true,
  "results": [ ... ]
}
```

**실패** — 대안 및 상품 미리보기 서비스 오류는 아래 형태입니다.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력값을 확인해주세요.",
    "details": {
      "product_price": ["1원 이상이어야 합니다."]
    }
  }
}
```

`details`는 대안 API에서 추가 정보가 있을 때 사용합니다. DRF serializer의
입력값 검증 오류는 필드명을 키로 하는 DRF 기본 형식으로 반환됩니다.

### 2.7 HTTP 상태 코드

| 코드 | 사용 상황 |
|---|---|
| `200 OK` | 조회·수정 성공 |
| `201 Created` | 생성 성공 |
| `204 No Content` | 삭제 성공 |
| `400 Bad Request` | 유효성 검증 실패, JSON 파싱 실패 |
| `403 Forbidden` | 미로그인 또는 CSRF 검증 실패 |
| `422 Unprocessable Entity` | 상품 페이지는 열렸지만 상품명·가격 추출 실패 |
| `404 Not Found` | 리소스 없음 **또는 내 소유가 아님** |
| `405 Method Not Allowed` | 지원하지 않는 메서드 |
| `409 Conflict` | 현재 상태에서 허용되지 않는 동작 (이미 생성됨 등) |
| `502 Bad Gateway` | 외부 API(Gemini) 호출 실패 |
| `504 Gateway Timeout` | 외부 API 응답 시간 초과 |

> **다른 사용자의 리소스에 403이 아니라 404를 주는 이유**: 403은 "그 ID는 존재한다"는 사실을 알려줍니다. 조회 자체를 `Consideration.objects.get(pk=pk, user=request.user)`로 작성하면 소유권 검사와 조회가 한 번에 끝나고, 자연스럽게 404가 됩니다.

### 2.8 에러 코드

| code | status | 설명 |
|---|---|---|
| `NOT_FOUND` | 404 | 리소스 없음 / 내 소유 아님 |
| `VALIDATION_ERROR` | 400 | 입력값 오류 (`details` 포함) |
| `INVALID_JSON` | 400 | 요청 본문 파싱 실패 |
| `INVALID_STATUS` | 409 | 현재 `status`에서 허용되지 않는 요청 (§9) |
| `INVALID_CATEGORIES` | 409 | 선택 카테고리가 1~3개 범위를 벗어남 |
| `ALREADY_EXISTS` | 409 | 이미 생성된 리소스 (의사결정, 소비 기록 연결) |
| `NO_CANDIDATE_ITEMS` | 409 | 후보 `AlternativeItem` 부족 |
| `AI_REQUEST_FAILED` | 502 | Gemini 호출/파싱 실패 |
| `AI_TIMEOUT` | 504 | Gemini 응답 시간 초과 |
| `INVALID_URL` | 400 | 상품 URL 형식 오류 |
| `URL_NOT_REACHABLE` | 400 | 상품 URL의 도메인 주소 확인 실패 |
| `PRIVATE_URL_NOT_ALLOWED` | 400 | 내부망·사설 IP URL 차단 |
| `UNSUPPORTED_CONTENT` | 400 | HTML이 아닌 응답 형식 |
| `RESPONSE_TOO_LARGE` | 400 | 상품 페이지 응답 크기 제한 초과 |
| `PRODUCT_INFO_NOT_FOUND` | 422 | 상품명 또는 가격 메타데이터 없음 |
| `PRODUCT_FETCH_FAILED` | 502 | 외부 상품 페이지 요청 실패 |

**폼 페이지에서는 이 코드를 쓰지 않습니다.** 카테고리 3개 초과, 최종 선택의 대안 불일치 같은 검증은 폼 `clean()`의 에러 메시지로 처리되며, 화면에 그대로 렌더됩니다. (§5.1, §8.3)

### 2.9 페이지네이션

현재 구현된 JSON API에는 페이지네이션 대상 목록이 없습니다. 향후 고민·소비
기록 목록 API를 구현할 때 `?page=1&page_size=10` 형식을 적용합니다.

### 2.10 표시 문자열은 서버가 완성합니다

**프론트가 `result_type`을 보고 분기하거나, 빈 값을 대시로 바꾸는 일이 없어야 합니다.** 화면에 그대로 출력할 문자열은 서버가 만들어 `*_display`로 내려보냅니다.

| 필드 | 원본 | 표시 문자열 | `FUTURE_VALUE`일 때 |
|---|---|---|---|
| `unit_price_display` (§6.2) | `unit_price` | `"180,000원"` | **`null`** — 가격을 표시하지 않음 |
| `price` / `price_display` (§6.5) | `unit_price` | `"180,000원"` | **`null`** / `"—"` |
| `duration_display` | `duration` | `"12개월"` | `"{period_month}개월"` |
| `display_text` | 계산 결과 | `"헬스장 약 12개월"` | `"정기적금 12개월 → 약 223만원"` |
| `source.note` | `item` 필드 | `"2026.07 기준 · 한국소비자원"` | 뒤에 **` · 세전`** 추가 |

**실제 생성 위치**

| 만드는 곳 | 담당 |
|---|---|
| `analyses/calculator.py` | 계산에서 파생되는 `display_text`, 재정형의 `duration`·`expected_effect` |
| `alternatives/api_views.py` | `unit_price_display`, `price_display`, `duration_display`, `chart`, `source.note` |

```python
duration_display = alternative.duration or "—"
```

소비형 `duration`·`expected_effect`는 Gemini 응답을 저장하고, 재정형은
계산기가 만든 값을 저장합니다.

### 2.11 동시 요청 — `select_for_update()`

**"고민 1건당 1개"인 리소스를 생성하는 요청은 `Consideration` 행을 잠근 뒤 상태를 검사합니다.**

현재 구현된 해당 엔드포인트는 다음 2개입니다.

```text
POST /api/alternatives/considerations/<id>/generate/
POST /api/alternatives/<id>/regenerate/
```

```python
with transaction.atomic():
    consideration = (
        Consideration.objects
        .select_for_update()
        .get(pk=pk, user=request.user)
    )
    # 여기서 status·중복 검사 → 실패 시 409
    # 통과하면 생성까지 같은 트랜잭션 안에서 끝냄
```

> **상태 검사만으로는 막히지 않습니다.** 대안 생성은 Gemini 응답까지 20초가 걸리는데, 그동안 `status`는 여전히 `DRAFT`입니다. 그 사이 두 번째 요청이 들어오면 **똑같이 검사를 통과합니다.** 결과적으로 두 세트가 생성되어 부분 UNIQUE 제약 `(consideration, category, slot) WHERE is_current=True`에 걸리고, 사용자는 `409`가 아니라 **500**을 봅니다.
>
> 행을 잠그면 두 번째 요청이 첫 번째가 끝날 때까지 대기했다가, 갱신된 `status`를 읽고 정상적으로 `409`를 받습니다.

> **프론트의 버튼 비활성화는 UX 장치일 뿐입니다.** 더블클릭·새로고침·탭 두 개·느린 네트워크의 재시도를 막지 못합니다. **중복은 서버에서 막습니다.**

**잠금 범위 주의** — `select_for_update()`는 트랜잭션 안에서만 유효하므로, 검사와 생성이 **같은 `atomic()` 블록** 안에 있어야 합니다. 다만 Gemini 호출이 그 안에 들어가면 DB 커넥션과 행 잠금을 20초 동안 붙잡게 됩니다. 동시 사용자가 늘면 다음으로 바꿉니다.

```text
1. 짧은 트랜잭션: 행 잠금 → status를 GENERATING으로 선점 → 커밋
2. 트랜잭션 밖에서 Gemini 호출
3. 짧은 트랜잭션: 결과 저장 → status를 GENERATED로
```

MVP 규모에서는 **1번 방식(전 과정을 한 트랜잭션)으로 충분**합니다. `GENERATING` 상태는 §9에 없으므로, 도입하려면 상태 전이 표부터 고쳐야 합니다.

---

## 3. 전체 URL 요약

### 3.1 페이지 (HTML)

| 메서드 | URL | url name | 인증 | 화면 |
|---|---|---|---|---|
| GET | `/` | `core:home` | - | 랜딩 |
| GET/POST | `/accounts/signup/` | `accounts:signup` | - | 회원가입 1단계 기본 정보 |
| GET/POST | `/accounts/signup/profile/` | `accounts:signup_profile` | - | 회원가입 2단계 소비 프로필 |
| GET/POST | `/accounts/login/` | `accounts:login` | - | 로그인 |
| POST | `/accounts/logout/` | `accounts:logout` | ✔ | 로그아웃 |
| GET | `/accounts/profile/` | `accounts:profile` | ✔ | 마이페이지 |
| GET/POST | `/products/considerations/new/` | `products:consideration_create` | ✔ | 구매 고민 입력 |
| GET | `/products/comparison/<int:pk>/` | `products:comparison_table` | - | 비교표 화면 |
| GET | `/products/opportunity-cost/<int:pk>/` | `products:opportunity_cost` | ✔ | 기회비용 시각화 |
| GET | `/alternatives/considerations/<int:pk>/` | `alternatives:consideration_alternatives` | ✔ | 카테고리별 대안 |

### 3.2 JSON API

| 메서드 | URL | 인증 | 설명 |
|---|---|---|---|
| GET | `/api/accounts/check-username/` | - | 아이디 중복 확인 |
| GET | `/api/accounts/me/` | ✔ | 내 기본 정보·소비 프로필 조회 |
| PATCH | `/api/accounts/me/basic/` | ✔ | 내 기본 정보 수정 |
| POST | `/api/accounts/me/password/` | ✔ | 내 비밀번호 변경 |
| PATCH | `/api/accounts/me/profile/` | ✔ | 내 소비 프로필 수정 |
| POST | `/api/products/preview/` | ✔ | 상품 URL에서 상품명·가격 추출 |
| POST | `/api/alternatives/considerations/<int:pk>/generate/` | ✔ | **대안 생성** |
| GET | `/api/alternatives/considerations/<int:pk>/` | ✔ | 현재 대안 목록 |
| POST | `/api/alternatives/<int:pk>/regenerate/` | ✔ | **대안 개별 재생성** |
| GET | `/api/alternatives/considerations/<int:pk>/comparison/` | ✔ | 비교표 데이터 |

> 위 표는 현재 `config/api_urls.py`에서 실제 접근 가능한 API만 적습니다.
> 카테고리 목록, 고민 비교 기준 수정, AI 의사결정 및 소비 기록 API는 문서의
> 후속 설계에는 남아 있지만 현재 라우팅되어 있지 않습니다.

---

## 4. accounts — 계정

### 4.1 `GET/POST /accounts/signup/` — 회원가입 1단계

기본 정보를 검증한 뒤 사용자를 바로 생성하지 않고
`pending_signup` 세션에 비밀번호 해시와 함께 임시 저장합니다.

| 필드 | 타입 | 필수 | 제약/허용값 |
|---|---|---|---|
| `name` | string(50) | ✔ | 빈 문자열 불가 |
| `username` | string(150) | ✔ | Django 아이디 형식, 대소문자 무시 중복 검사 |
| `email` | email | ✔ | 대소문자 무시 중복 검사, 소문자로 저장 |
| `gender` | choice | ✔ | `FEMALE` / `MALE` / `OTHER` |
| `birth_date` | date | ✔ | `YYYY-MM-DD` |
| `password` | string | ✔ | Django 비밀번호 정책 적용 |
| `password_confirm` | string | ✔ | `password`와 일치 |

- 성공: `302` → `/accounts/signup/profile/`
- 실패: `200` + 필드 오류가 포함된 HTML

### 4.2 `GET/POST /accounts/signup/profile/` — 회원가입 2단계

1단계 세션이 있어야 접근할 수 있습니다. 소비 프로필까지 검증한 후 사용자를
생성하고 Django 로그인 세션을 만든 뒤 임시 회원가입 세션을 삭제합니다.

| 필드 | 타입 | 필수 | 제약/허용값 |
|---|---|---|---|
| `spending_type` | string[] | ✔ | 아래 값 중 1~2개, 중복 불가 |
| `value_criteria` | string[] | ✔ | 아래 값 중 1~3개, 중복 불가 |
| `monthly_budget` | string | ✔ | 아래 예산 구간 중 1개 |

`spending_type`:
`VALUE`, `QUALITY`, `EXPERIENCE`, `GROWTH`, `ASSET`, `CAUTIOUS`

`value_criteria`:
`PRICE`, `SATISFACTION`, `QUALITY`, `UTILIZATION`, `DURATION`, `EFFICIENCY`

`monthly_budget`:
`UNDER_100K`, `100K_300K`, `300K_500K`, `500K_1M`, `1M_2M`, `OVER_2M`

- 성공: 사용자 생성 및 자동 로그인 후 `302` → `/products/considerations/new/`
- 1단계 세션 없음: `302` → `/accounts/signup/`
- 완료 직전 아이디와 이메일 중복 여부를 다시 검사합니다.

### 4.3 `GET/POST /accounts/login/` — 로그인

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `email` | email | ✔ | 대소문자를 구분하지 않음 |
| `password` | string | ✔ | 사용자 비밀번호 |
| `next` | string | | 동일 호스트의 안전한 이동 경로만 허용 |

- 성공: Django 세션 생성 후 안전한 `next`가 있으면 해당 경로, 없으면 `/`로 `302`
- 실패: `200` + `이메일 또는 비밀번호가 올바르지 않습니다.`

### 4.4 `POST /accounts/logout/` — 로그아웃

현재 세션을 종료하고 `302` → `/`로 이동합니다. **GET은 405**입니다.

### 4.5 `GET /api/accounts/check-username/` — 아이디 중복 확인

인증 없이 호출할 수 있습니다.

| Query | 타입 | 필수 | 설명 |
|---|---|---|---|
| `username` | string | ✔ | 최대 150자, Django 아이디 형식 |

**200 OK**

```json
{
  "username": "choezy_user",
  "available": true
}
```

`username`이 비었거나 형식에 맞지 않으면 DRF 필드 오류 형식의 `400`입니다.
현재 이 API의 조회는 대소문자를 구분하는 정확 일치이고, 실제 회원가입의
중복 검사는 대소문자를 구분하지 않습니다. 또한 중복 확인 후 다른 요청이
먼저 가입할 수 있으므로 회원가입 완료 단계에서 아이디 중복을 다시 검사합니다.

### 4.6 `GET /api/accounts/me/` — 내 정보 조회

로그인한 사용자의 기본 정보와 회원가입 때 저장한 소비 프로필을 반환합니다.
비밀번호는 반환하지 않습니다.

**200 OK**

```json
{
  "id": 5,
  "username": "choezy_user",
  "email": "user@example.com",
  "name": "최지",
  "birth_date": "2000-01-01",
  "gender": "FEMALE",
  "spending_type": ["VALUE", "CAUTIOUS"],
  "value_criteria": ["PRICE", "QUALITY"],
  "monthly_budget": "300K_500K"
}
```

### 4.7 `PATCH /api/accounts/me/basic/` — 기본 정보 수정

`username`, `name`, `birth_date`, `gender` 중 변경할 필드만 보냅니다.
`email`은 이 API에서 수정하지 않습니다. 빈 객체는 `400`이고, 아이디 중복은
대소문자를 구분하지 않고 검사합니다.

```json
{
  "username": "updated_user",
  "name": "수정 사용자",
  "birth_date": "1999-12-31",
  "gender": "FEMALE"
}
```

성공 시 `4.6`과 동일한 전체 사용자 객체를 `200`으로 반환합니다.

### 4.8 `POST /api/accounts/me/password/` — 비밀번호 변경

```json
{
  "password": "NewStrongPass!2468",
  "password_confirm": "NewStrongPass!2468"
}
```

Django 비밀번호 정책과 일치 여부를 검증하고 변경 후 현재 로그인 세션을
유지합니다.

```json
{ "detail": "비밀번호가 변경되었습니다." }
```

### 4.9 `PATCH /api/accounts/me/profile/` — 소비 프로필 수정

`spending_type`, `value_criteria`, `monthly_budget` 중 변경할 필드만 보냅니다.
선택 개수와 허용값은 회원가입 2단계와 같습니다. 빈 객체는 `400`입니다.

```json
{
  "spending_type": ["QUALITY", "CAUTIOUS"],
  "value_criteria": ["PRICE", "UTILIZATION", "EFFICIENCY"],
  "monthly_budget": "500K_1M"
}
```

성공 시 `4.6`과 동일한 전체 사용자 객체를 `200`으로 반환합니다.

---

## 5. products — 구매 고민

### 5.1 `GET/POST /products/considerations/new/` — 구매 고민 입력 (폼)

`ConsiderationForm` (`products/forms.py`)으로 처리합니다. **JSON API가 아닙니다.**

**폼 필드**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `product_url` | url(500) | | 상품 페이지 링크. 미리보기 API 사용 후에도 수정 가능 |
| `product_name` | string(200) | ✔ | 상품명. 자동 입력값 또는 사용자 직접 입력값 |
| `product_price` | int | ✔ | 가격. 원 단위 정수, 1 이상 |
| `purpose` | choice | △ | `SELF_DEVELOPMENT` / `TRAVEL` / `DESIGN` / `GIFT` / `WORK` / `HOBBY` / `CONVENIENCE` |
| `purpose_detail` | string(200) | △ | 직접 입력값이 있으면 서버가 `purpose=ETC`로 저장 |
| `categories` | int[] | ✔ | **최대 3개** (`ModelMultipleChoiceField`) |
| `category_detail` | string(50) | | 지원 카테고리 이름 직접 입력 |

> `purpose`와 `purpose_detail` 중 하나는 필수입니다. 직접 입력값이 있으면
> 선택된 `purpose`보다 직접 입력값을 우선합니다.

`category_detail`은 공백과 `·`을 제거한 뒤 지원 카테고리 별칭으로
변환합니다. 현재 지원 값은 여행, 운동·건강, 문화·여가, 생활·편의,
디지털·전자기기, 재정이며 체크박스 선택과 합쳐 최대 3개입니다.

`compare_criteria`는 폼에서 받지 않고 생성 시 서버가
`PRICE`, `DURATION`, `EXPECTED_EFFECT`, `AVAILABLE_BUDGET` 전체를 저장합니다.

**입력값 안내 (화면)**

가격을 사용자가 직접 적으므로 오타 한 자리가 기회비용 전체를 바꿉니다. 화면에서 다음을 돕습니다.

- 숫자 입력 중 **천 단위 구분 기호 표시** (`2,200,000`) — 제출 시에는 정수로 변환
- 입력값을 **한글 금액으로 되읽어주기** (`220만원`)

> 서버는 정수만 받습니다. `"2,200,000"` 같은 문자열이 오면 `product_price` 필드 에러입니다.

**응답**

- 성공: `302` → `/alternatives/considerations/<id>/` (대안 생성 페이지)
- 실패: `200` + 폼 에러가 렌더된 입력 화면

**검증 규칙**

| 상황 | 처리 |
|---|---|
| `product_price <= 0` | `product_price` 필드 에러 |
| `purpose`와 `purpose_detail`이 모두 비어 있음 | `purpose` 필드 에러 |
| 체크박스와 직접 입력을 합친 카테고리가 4개 이상 | `categories` 필드 에러 |
| 체크박스와 직접 입력이 모두 비어 있음 | `categories` 필드 에러 |
| `is_active=False`인 카테고리 | `queryset` 자체를 `is_active=True`로 제한해 애초에 선택 불가 |

생성된 고민의 `status`는 `DRAFT`입니다.

> **카테고리 3개 제한 검증 위치**: M2M 행 수 조건이라 DB `CheckConstraint`로 표현할 수 없습니다. 폼의 `clean()`에서 막고, 서비스 레이어(`alternatives/services.py`)에서도 한 번 더 확인합니다. 상수는 `config/settings.py`의 `MAX_CATEGORY_SELECTION = 3`입니다. (ERD §6)

### 5.2 `POST /api/products/preview/` — 상품 URL 미리보기

로그인이 필요합니다. URL 페이지에 공개된 Open Graph, 일반 meta 태그,
JSON-LD `Product` 정보를 읽어 상품명과 가격을 반환합니다. 반환값은 화면의
입력칸을 채우는 용도이며 사용자가 수정한 뒤 고민 생성 폼을 제출할 수 있습니다.

**Request**

```json
{ "url": "https://shop.example.com/products/123" }
```

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `url` | URL string | ✔ | 최대 500자, HTTP/HTTPS 공개 주소 |

내부망 접근을 막기 위해 localhost, loopback, private/reserved IP를 거부하고
리다이렉트된 URL도 다시 검사합니다. 응답은 최대 1MB, 요청 제한시간은 8초입니다.

**200 OK**

```json
{
  "product_name": "Apple AirPods 4",
  "product_price": 199000,
  "image_url": "https://shop.example.com/images/airpods.jpg",
  "product_url": "https://shop.example.com/products/123"
}
```

| 상황 | code | status |
|---|---|---|
| URL 형식 오류 | `INVALID_URL` 또는 DRF 필드 오류 | 400 |
| 도메인 주소 확인 실패 | `URL_NOT_REACHABLE` | 400 |
| 내부망·사설 IP | `PRIVATE_URL_NOT_ALLOWED` | 400 |
| 지원하지 않는 응답 형식 | `UNSUPPORTED_CONTENT` | 400 |
| 응답 크기 1MB 초과 | `RESPONSE_TOO_LARGE` | 400 |
| 상품명 또는 가격 없음 | `PRODUCT_INFO_NOT_FOUND` | 422 |
| 403·429·네트워크·타임아웃 오류 | `PRODUCT_FETCH_FAILED` | 502 |

```json
{
  "error": {
    "code": "PRODUCT_INFO_NOT_FOUND",
    "message": "상품명 또는 가격을 찾지 못했습니다. 직접 입력해주세요."
  }
}
```

> 네이버 스마트스토어는 429, 쿠팡은 403 등 사이트의 봇 차단 정책에 따라
> 추출에 실패할 수 있습니다. 실패하면 상품명과 가격을 직접 입력합니다.

### 5.3 후속 계획 — 고민 목록·상세 페이지 (현재 미구현)

`GET /products/considerations/` 및
`GET /products/considerations/<int:pk>/`에 대한 아래 내용은 후속 설계이며
현재 URL에 등록되어 있지 않습니다.

서버 사이드 렌더링입니다. 별도 JSON API를 두지 않습니다.

**목록 템플릿 컨텍스트**

```python
{
    "considerations": Page,  # -created_at 최신순, 10개씩
    "status_filter": "GENERATED" | None,
}
```

`?status=GENERATED&page=2` 쿼리 파라미터를 지원합니다.

**상세 템플릿 컨텍스트**

```python
{
    "consideration": Consideration,
    "has_alternatives": bool,
    "has_decision": bool,
    "has_final_choice": bool,
}
```

조회는 항상 `Consideration.objects.get(pk=pk, user=request.user)` — 내 고민이 아니면 **404**입니다.

### 5.4 후속 계획 — 비교 기준 변경 API (현재 미구현)

예정 URL: `PATCH /api/products/considerations/<int:pk>/`

**비교표 화면에서 체크박스를 바꿀 때만** 사용합니다. 화면에 머무른 채 표를 다시 그려야 하므로 JSON API입니다.

**요청**

```json
{ "compare_criteria": ["PRICE", "AVAILABLE_BUDGET"] }
```

**수정 가능 필드**: `compare_criteria` 뿐입니다.

**200 OK**

```json
{
  "id": 12,
  "compare_criteria": ["PRICE", "AVAILABLE_BUDGET"],
  "columns": [
    { "key": "price", "label": "가격" },
    { "key": "available_budget", "label": "가용 예산" }
  ]
}
```

`columns`를 함께 내려주므로 프론트는 이 값으로 표 헤더를 다시 그리면 됩니다. (§6.5와 동일한 형식)

**에러**

| 상황 | code | status |
|---|---|---|
| 없거나 내 고민이 아님 | `NOT_FOUND` | 404 |
| 허용되지 않는 값이 포함됨 | `VALIDATION_ERROR` | 400 |
| `status`가 `DECIDED` 또는 `CLOSED` | `INVALID_STATUS` | 409 |

> **`product_price`·`categories`를 수정할 수 없는 이유**: 이미 생성된 `Alternative`의 `equivalent_quantity`가 그 가격으로 계산되어 있습니다. 가격만 바꾸면 화면의 기회비용 숫자와 계산 근거가 어긋납니다. 다른 가격으로 다시 보고 싶다면 **새 고민을 생성**합니다.

> 상품 정보 수정 기능은 MVP에 없습니다. 오타를 고치고 싶다면 삭제 후 새로 만듭니다.

### 5.5 후속 계획 — 고민 삭제 (현재 미구현)

예정 URL: `POST /products/considerations/<int:pk>/delete/`

목록·상세 화면의 삭제 버튼입니다. `{% csrf_token %}`이 포함된 폼으로 제출합니다.

**응답**

- 성공: `302` → `/products/considerations/` + `messages.success`
- 실패: `302` → 원래 화면 + `messages.error`

`Alternative`, `Decision`, `FinalChoice`, `LLMRequestLog`는 `CASCADE`로 함께 삭제됩니다.

**삭제가 거부되는 경우** — 해당 고민의 `FinalChoice`에 연결된 `SpendingRecord`가 있을 때. `SpendingRecord.final_choice`는 `SET_NULL`이지만 `FinalChoice.alternative`가 `PROTECT`라 삭제 순서상 충돌이 발생할 수 있으므로, 서비스 레이어에서 먼저 확인하고 메시지로 안내합니다.

> **삭제는 `status`와 무관하게 허용됩니다.** §9의 상태 전이 규칙은 "고민을 어떻게 진행하는가"에 대한 것이고, 삭제는 소유자가 자기 데이터를 없애는 동작입니다. `DECIDED` 상태에서 삭제를 막으면 사용자가 자기 기록을 지울 수 없게 됩니다.

### 5.5 `GET /products/opportunity-cost/<int:pk>/` — 기회비용 시각화 (페이지)

"이 가격이면 대신 이걸 할 수 있어요"를 막대그래프로 보여주는 화면입니다. **JSON API가 아니라 서버 사이드 렌더링 페이지입니다.** 비교표(§6.5)와 달리 JS가 API를 부르지 않고, 막대 높이·색·표기까지 서버가 컨텍스트로 확정해 내려줍니다 (§2.10).

숫자는 전부 `Alternative`에 저장된 계산 결과를 그대로 씁니다. 화면에서 다시 계산하지 않습니다 — 같은 고민이 화면마다 다른 숫자를 보이면 안 됩니다.

**템플릿 컨텍스트**

| 키 | 설명 |
|---|---|
| `consideration_id` | 고민 id |
| `product_name` | 상품명 |
| `product_price` | 표시용 문자열. 만원 단위로 떨어지면 `"220만원"`, 아니면 `"1,234,500원"` |
| `opportunity_costs` | 막대 목록 (아래) |
| `financial_costs` | 재정형 대안 목록 (아래) |

`opportunity_costs[]`

| 키 | 설명 |
|---|---|
| `name` | `AlternativeItem.name`. **DB 문자열이므로 템플릿에서 `\|safe`를 쓰지 않습니다** |
| `count` | 막대 블록을 쌓는 실제 비율 (`equivalent_quantity`). 숫자 타입이고 내림하지 않습니다 |
| `display_count` | 표기용. `§7.4` 규칙으로 내림한 수량 + `unit_label` (예: `"12개월"`, `"0.6회"`) |
| `color` / `text_color` | `static/css/opportunity_cost.css`의 색 클래스. 막대 순서대로 팔레트를 순환합니다 |

> **`count`와 `display_count`가 다른 이유**: 막대는 실제 비율(`12.22`)로 그려야 정확하고, 옆에 적히는 숫자는 §7.4의 내림 규칙(`12개월`)을 따라야 다른 화면과 일치합니다.

**재정(`FINANCE`) 카테고리는 막대가 되지 않습니다.**

`result_type = FUTURE_VALUE`인 대안은 나눗셈이 아니라 "그 돈을 대신 굴리면 얼마"라서(§7.5) 개수 개념이 없습니다. 막대에 끼워 넣으면 항상 1블록짜리가 되어 숫자가 오히려 왜곡되므로, `financial_costs`로 갈라서 문장으로 보여줍니다.

| 키 | 설명 |
|---|---|
| `name` | 항목명 (예: `"정기적금"`) |
| `expected_effect` | 계산 결과 문장 (예: `"월 183,333원씩 12개월 → 약 223만원"`) |
| `display_text` | `expected_effect`가 비었을 때의 대체 문구 |

**응답**

- 미로그인: `302` → 로그인 페이지
- 남의 고민: `404` — `403`으로 돌려주면 "그 id는 존재한다"는 사실이 새어 나갑니다
- 대안이 없을 때(`status = DRAFT`): `200` + 빈 상태 안내. 에러가 아닙니다

---

## 6. alternatives — 대안 생성

### 6.1 후속 계획 — 카테고리 목록 API (현재 미구현)

예정 URL: `GET /api/alternatives/categories/`

메인 페이지의 카테고리 선택 UI에서 사용합니다.

**쿼리 파라미터**

| 이름 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `active_only` | bool | `true` | `is_active=True`만 조회 |

**200 OK**

```json
{
  "count": 6,
  "max_selection": 3,
  "results": [
    { "id": 1, "code": "TRAVEL", "name": "여행", "emoji": "✈️", "display_order": 1, "item_count": 24 }
  ]
}
```

`item_count`는 해당 카테고리의 활성 `AlternativeItem` 수입니다. 후보가 0인 카테고리는 대안을 만들 수 없으므로 화면에서 비활성 처리하는 데 사용합니다.

`max_selection`은 `settings.MAX_CATEGORY_SELECTION`을 그대로 내려줍니다.

### 6.2 `POST /api/alternatives/considerations/<int:pk>/generate/` — 대안 생성 ★

선택한 카테고리별로 대안 3개씩 생성합니다. **이 서비스의 핵심 엔드포인트입니다.**

**요청**

```json
{}
```

본문이 필요 없습니다. 생성에 필요한 정보(상품·목적·카테고리·소비 프로필)는 모두 서버가 DB에서 조회합니다.

**처리 순서**

```text
1. status 확인 (DRAFT만 허용)
2. 선택 카테고리의 활성 AlternativeItem 후보 조회
   → exclude_category 제외
   → is_calculable()을 통과한 항목만 남김          (§7.7)
   → 카테고리별 후보가 3개 미만이면 NO_CANDIDATE_ITEMS
3. 사용자 소비 프로필 + 상품 정보 + 후보 목록으로 프롬프트 구성
4. Gemini 호출 → item_ids만 응답받음
5. 응답 item_id를 후보 목록과 대조 (없는 id는 거부)
6. 가격은 DB의 AlternativeItem.average_price에서 다시 조회
7. 기회비용 계산 (calculator.py)                    ← 2단계 덕분에 실패하지 않음
8. Alternative 생성 (version=1, is_current=True)
9. Consideration.status → GENERATED
10. LLMRequestLog 기록
```

**2단계에서 계산 가능 여부까지 판정하는 것이 핵심입니다.** 계산이 불가능한 항목을 AI에게 보여주지 않으므로, 7단계에서 슬롯이 비는 상황이 생기지 않습니다. (§7.7)

전 과정을 `transaction.atomic()`으로 묶습니다. 단, `LLMRequestLog`는 **실패 시에도 남아야 하므로** 트랜잭션 밖에서 별도로 기록합니다.

**201 Created**

```json
{
  "consideration_id": 12,
  "status": "GENERATED",
  "product": {
    "name": "Apple 맥북 에어 13 M4",
    "price": 2200000
  },
  "categories": [
    {
      "id": 2,
      "code": "HEALTH",
      "name": "운동(건강)",
      "emoji": "💪",
      "alternatives": [
        {
          "id": 101,
          "slot": 1,
          "version": 1,
          "is_current": true,
          "unit_price": 180000,
          "unit_price_display": "180,000원",
          "duration": "12개월",
          "duration_display": "12개월",
          "expected_effect": "주 3회 운동 습관 형성과 체력 향상",
          "ai_reason": "경험·만족을 중시하고 활용도를 중요한 가치로 꼽아, 매일 사용할 수 있는 항목을 골랐습니다.",
          "result_type": "QUANTITY",
          "equivalent_quantity": "12.22",
          "future_value": null,
          "display_text": "헬스장 약 12개월",
          "chart": {
            "type": "COUNT",
            "value": 12.22,
            "unit_label": "개월",
            "caption": "헬스장 약 12개월"
          },
          "item": {
            "id": 31,
            "name": "헬스장 1개월",
            "unit_label": "개월",
            "spec_note": "수도권 프랜차이즈 헬스장 1개월 등록 기준",
            "calc_type": "UNIT_PRICE",
            "source_name": "한국소비자원 가격정보",
            "source_url": "https://...",
            "effective_date": "2026-07-01"
          }
        }
      ]
    }
  ],
  "generated_at": "2026-07-30T14:05:02+09:00"
}
```

**`FINANCE` 카테고리의 대안 객체**는 아래와 같습니다. **`unit_price_display`가 `null`입니다.**

```json
{
  "id": 115,
  "slot": 1,
  "version": 1,
  "is_current": true,
  "unit_price": 2200000,
  "unit_price_display": null,
  "duration": "12개월",
  "duration_display": "12개월",
  "expected_effect": "12개월 뒤 약 223만원",
  "ai_reason": "자산 형성을 중시한다고 답해, 원금이 보존되는 항목을 골랐습니다.",
  "result_type": "FUTURE_VALUE",
  "equivalent_quantity": null,
  "future_value": 2235750,
  "display_text": "정기적금 12개월 → 약 223만원",
  "chart": {
    "type": "GROWTH",
    "principal": 2200000,
    "future_value": 2235750,
    "gain_amount": 35750,
    "caption": "정기적금 12개월 → 약 223만원"
  },
  "item": {
    "id": 77,
    "name": "정기적금 (연 3%)",
    "unit_label": "",
    "spec_note": "시중은행 12개월 정기적금 평균 금리 · 세전",
    "calc_type": "SAVINGS",
    "source_name": "은행연합회 소비자포털",
    "source_url": "https://...",
    "effective_date": "2026-07-01"
  }
}
```

| 필드 | 규칙 |
|---|---|
| `unit_price` | 계산에 사용한 기준 금액. `QUANTITY`는 단가, `FUTURE_VALUE`는 **원금** (§7.3) |
| `unit_price_display` | **화면에 출력할 가격 문자열.** `FUTURE_VALUE`는 항상 `null` |
| `duration_display` | 화면에 출력할 기간 문자열. 빈 값은 `"—"` (§2.10) |
| `chart` | 대안 카드용 그래프 값. 생성·목록·재생성 응답의 `caption`은 `display_text`와 같습니다 |

> **`unit_price_display: null`인 카드는 가격을 표시하지 않습니다.** `unit_price`를 그대로 찍으면 `FINANCE` 카드에 **상품 가격과 똑같은 220만원**이 "대안 가격"으로 뜹니다. 재정형의 `unit_price`는 단가가 아니라 원금이기 때문입니다. 원금을 보여주고 싶다면 `chart.principal`을 쓰고, 가격 칸은 비웁니다.
>
> 프론트가 `result_type`으로 분기하지 않아도 되도록 **서버가 `null`로 내려보냅니다.** 비교표(§6.5)의 `price` / `price_display`와 같은 규칙입니다.

**에러**

| 상황 | code | status |
|---|---|---|
| 내 고민이 아님 | `NOT_FOUND` | 404 |
| `status != DRAFT` (이미 생성됨) | `INVALID_STATUS` | 409 |
| 선택 카테고리가 1~3개가 아님 | `INVALID_CATEGORIES` | 409 |
| 어떤 카테고리의 **계산 가능한** 활성 후보가 3개 미만 (§7.7) | `NO_CANDIDATE_ITEMS` | 409 |
| Gemini 호출 실패 / JSON 파싱 실패 / 유효하지 않은 `item_id` | `AI_REQUEST_FAILED` | 502 |
| Gemini 타임아웃 | `AI_TIMEOUT` | 504 |

```json
{
  "error": {
    "code": "NO_CANDIDATE_ITEMS",
    "message": "사용할 수 있는 대안 데이터가 부족합니다.",
    "details": { "category": ["TRAVEL: 계산 가능한 활성 항목 2개 (최소 3개 필요)"] }
  }
}
```

**AI 응답 계약**

Gemini에게는 **항목 식별값만** 요구합니다. 가격·출처는 절대 받지 않습니다.

**요구하는 필드는 `calc_type`에 따라 다릅니다.**

```json
{
  "selections": [
    {
      "category_code": "HEALTH",
      "items": [
        { "item_id": 31, "slot": 1, "duration": "12개월", "expected_effect": "...", "ai_reason": "..." }
      ]
    },
    {
      "category_code": "FINANCE",
      "items": [
        { "item_id": 77, "slot": 1, "ai_reason": "..." }
      ]
    }
  ]
}
```

| `calc_type` | AI가 채우는 필드 | 서버가 채우는 필드 |
|---|---|---|
| `UNIT_PRICE` | `item_id`, `slot`, `duration`, `expected_effect`, `ai_reason` | 가격·계산 결과 |
| `SAVINGS` / `DEPOSIT` / `INVESTMENT` | `item_id`, `slot`, `ai_reason` | 가격·계산 결과 + **`duration`, `expected_effect`** |

**재정 항목의 `duration`·`expected_effect`는 AI에게 요구하지 않습니다.** 프롬프트에도 해당 후보에는 `item_id`와 `ai_reason`만 쓰라고 지시하고, **AI가 보내오더라도 서버는 무시하고 덮어씁니다.**

```text
duration        = "{period_month}개월"
expected_effect = "{period_month}개월 뒤 약 {금액}만원"     ← 만원 단위 내림 (§7.5)
```

> **두 값의 출처가 갈리면 화면에서 모순이 보입니다.** 재정 항목의 기간은 `calc_params.period_month`에서 오고 `display_text`도 그 값으로 만들어집니다. 여기서 AI가 `duration: "24개월"`이라고 써버리면, 비교표의 "지속 가능 기간" 열에는 `24개월`이, 바로 옆 기회비용 문구에는 `"12개월 → 약 223만원"`이 나란히 뜹니다. `expected_effect`도 마찬가지입니다 — `"12개월 뒤 약 223만원"`은 AI가 쓴 문장이 아니라 **계산 결과**입니다. (§6.5 예시)

> 소비형(`UNIT_PRICE`)은 반대입니다. `duration`("주 3회 12개월")과 `expected_effect`("운동 습관 형성")은 계산으로 나오지 않는 값이라 AI가 씁니다.

> 가격까지 AI가 만들면 같은 "일본 여행"이 호출할 때마다 금액이 달라져 기회비용 숫자를 믿을 수 없게 됩니다. (ERD §1) 서버는 `item_id`가 **이번 요청에서 전달한 후보 목록에 실제로 있는지** 반드시 대조하고, 없으면 `AI_REQUEST_FAILED`로 처리합니다.

**응답 시간과 프론트 처리**

이 API는 Gemini 호출 때문에 **5~20초**가 걸릴 수 있습니다.

- 프론트는 로딩 UI를 띄우고 **버튼을 비활성화**합니다. 이는 **UX 장치일 뿐 중복 방지 수단이 아닙니다.**
- `fetch` 타임아웃을 30초 이상으로 잡습니다.
- 서버는 Gemini 호출에 자체 타임아웃(예: 25초)을 걸고 `504 AI_TIMEOUT`을 반환합니다.
- **중복 호출은 서버가 `select_for_update()`로 막습니다.** 상태 검사만으로는 막히지 않습니다 — 첫 요청이 Gemini를 기다리는 20초 동안 `status`는 여전히 `DRAFT`이기 때문입니다. (§2.11)

### 6.3 `GET /api/alternatives/considerations/<int:pk>/` — 현재 대안 목록

`is_current=True`인 대안만 카테고리별로 반환합니다. 응답 구조는 `6.2`의 201과 동일합니다.

**쿼리 파라미터**

| 이름 | 타입 | 설명 |
|---|---|---|
| `category` | string | 카테고리 `code` 필터 (예: `HEALTH`) |
| `include_history` | bool | `true`면 이전 버전(`is_current=False`)도 포함 |

`include_history=true`일 때 각 대안에 `history` 배열이 추가됩니다.

```json
{
  "id": 108,
  "slot": 2,
  "version": 3,
  "is_current": true,
  "history": [
    { "id": 104, "version": 2, "display_text": "요가 클래스 약 8개월", "created_at": "..." },
    { "id": 102, "version": 1, "display_text": "PT 약 22회", "created_at": "..." }
  ]
}
```

**404 NOT_FOUND** — 없거나 내 고민이 아닐 때. 대안이 아직 없으면 `categories`가 빈 배열인 `200`입니다.

**구현 메모** — N+1을 막기 위해 다음을 사용합니다.

```python
Alternative.objects.filter(consideration=consideration, is_current=True)
    .select_related("category", "item")
    .order_by("category__display_order", "slot")
```

### 6.4 `POST /api/alternatives/<int:pk>/regenerate/` — 개별 재생성 ★

대안 카드의 재생성 버튼입니다. `pk`는 **재생성할 `Alternative`의 id**입니다.

**요청**

```json
{}
```

**처리 순서** (ERD §5.5)

```text
1. 대상 Alternative 조회 (is_current=True인 것만)
2. 같은 카테고리의 활성 후보 조회
   → 현재 같은 고민에서 사용 중인 item은 제외 (같은 대안 재등장 방지)
   → is_calculable()을 통과한 항목만 남김          (§7.7)
   → 남은 후보가 0개면 NO_CANDIDATE_ITEMS
3. Gemini 호출 → item_id 1개 (+ ai_reason, 소비형이면 duration·expected_effect)
4. 기회비용 계산 (calculator.py)
   → 재정형이면 duration·expected_effect를 서버 값으로 덮어씀 (§6.2)
5. 기존 행 is_current = False
6. 새 행 생성 (version = 기존 + 1, is_current = True)
7. LLMRequestLog(purpose=REGENERATE) 기록
```

1단계에서 `Consideration`을 `select_for_update()`로 잠급니다. (§2.11) 잠그지 않으면 같은 카드를 두 번 누를 때 두 행이 모두 `is_current=True`로 들어가 부분 UNIQUE 제약에 걸립니다.

5~6단계는 `transaction.atomic()` 안에서 처리합니다. 부분 UNIQUE 제약 `(consideration, category, slot) WHERE is_current=True` 때문에 **반드시 기존 행을 먼저 `False`로 바꾼 뒤 새 행을 INSERT**해야 합니다.

**201 Created** — 새로 만들어진 대안 1개

```json
{
  "id": 108,
  "category": { "id": 2, "code": "HEALTH", "name": "운동(건강)", "emoji": "💪" },
  "slot": 2,
  "version": 3,
  "is_current": true,
  "previous_alternative_id": 104,
  "unit_price": 250000,
  "unit_price_display": "250,000원",
  "duration": "8개월",
  "duration_display": "8개월",
  "expected_effect": "유연성 향상과 스트레스 관리",
  "ai_reason": "이전에 추천한 항목과 겹치지 않으면서 활용도가 높은 항목을 골랐습니다.",
  "result_type": "QUANTITY",
  "equivalent_quantity": "8.80",
  "future_value": null,
  "display_text": "요가 클래스 약 8개월",
  "chart": {
    "type": "COUNT",
    "value": 8.8,
    "unit_label": "개월",
    "caption": "요가 클래스 약 8개월"
  },
  "item": {
    "id": 44,
    "name": "요가 클래스 1개월",
    "unit_label": "개월",
    "spec_note": "주 2회 그룹 클래스 기준",
    "calc_type": "UNIT_PRICE",
    "source_name": "...",
    "source_url": "https://...",
    "effective_date": "2026-07-01"
  }
}
```

`FINANCE` 카테고리의 대안을 재생성하면 §6.2의 `FINANCE` 객체와 같은 모양으로 내려옵니다 — **`unit_price_display`는 `null`, `chart.type`은 `GROWTH`입니다.**

**에러**

| 상황 | code | status |
|---|---|---|
| 대안이 없거나 내 고민의 대안이 아님 | `NOT_FOUND` | 404 |
| `is_current=False`인 과거 버전을 지정 | `INVALID_STATUS` | 409 |
| `status != GENERATED` (§9) | `INVALID_STATUS` | 409 |
| 남은 후보가 없음 | `NO_CANDIDATE_ITEMS` | 409 |
| AI 실패 | `AI_REQUEST_FAILED` | 502 |

> **최종 선택 이후 재생성을 막는 이유**: `FinalChoice`가 특정 `Alternative`를 `PROTECT`로 참조합니다. 선택이 끝난 뒤 대안이 바뀌면 "무엇을 보고 결정했는지"가 흐려집니다.

> **재생성이 실패해도 기존 대안은 그대로 남습니다.** 트랜잭션이 롤백되므로 `is_current=False`로 바뀌었던 기존 행이 복구됩니다. 프론트는 실패 시 카드를 원래대로 두고 토스트만 띄우면 됩니다.

### 6.5 `GET /api/alternatives/considerations/<int:pk>/comparison/` — 비교표 데이터

비교표·기회비용 시각화 화면 전용입니다. `Consideration.compare_criteria`에 선택된 열만 반환합니다.

**200 OK**

```json
{
  "consideration_id": 12,
  "product": {
    "name": "Apple 맥북 에어 13 M4",
    "price": 2200000,
    "features": "M4 칩, 16GB 통합 메모리, 512GB SSD"
  },
  "user_budget": { "code": "300K_500K", "display": "30~50만원" },
  "columns": [
    { "key": "price", "label": "가격" },
    { "key": "duration", "label": "지속 가능 기간" },
    { "key": "expected_effect", "label": "기대 효과" }
  ],
  "tabs": [
    {
      "category": { "id": 2, "code": "HEALTH", "name": "운동(건강)", "emoji": "💪" },
      "rows": [
        {
          "alternative_id": 101,
          "slot": 1,
          "name": "헬스장 1개월",
          "price": 180000,
          "price_display": "180,000원",
          "duration_display": "12개월",
          "expected_effect": "주 3회 운동 습관 형성과 체력 향상",
          "available_budget": {
            "budget_code": "300K_500K",
            "budget_display": "30~50만원",
            "budget_min": 300000,
            "budget_max": 500000,
            "difference_min": 120000,
            "difference_max": 320000,
            "status": "UNDER",
            "display": "월 예산 대비 12만원~32만원 여유"
          },
          "opportunity_cost": {
            "result_type": "QUANTITY",
            "equivalent_quantity": "12.22",
            "future_value": null,
            "display_text": "헬스장 약 12개월"
          },
          "chart": {
            "type": "COUNT",
            "value": 12.22,
            "unit_label": "개월",
            "caption": "Apple 맥북 에어 13 M4 = 헬스장 약 12개월"
          },
          "source": {
            "name": "한국소비자원 가격정보",
            "url": "https://...",
            "effective_date": "2026-07-01",
            "note": "2026.07 기준 · 한국소비자원 가격정보"
          }
        }
      ]
    }
  ]
}
```

`FINANCE` 카테고리 행은 `opportunity_cost`와 `chart`의 모양이 다르고, **`price`가 `null`입니다.**

```json
{
  "alternative_id": 115,
  "slot": 1,
  "name": "정기적금 (연 3%)",
  "price": null,
  "price_display": "—",
  "duration_display": "12개월",
  "expected_effect": "12개월 뒤 약 223만원",
  "available_budget": {
    "budget_code": "300K_500K",
    "budget_display": "30~50만원",
    "budget_min": 300000,
    "budget_max": 500000,
    "difference_min": null,
    "difference_max": null,
    "status": "NOT_APPLICABLE",
    "display": "해당 없음"
  },
  "opportunity_cost": {
    "result_type": "FUTURE_VALUE",
    "equivalent_quantity": null,
    "future_value": 2235750,
    "display_text": "정기적금 12개월 → 약 223만원"
  },
  "chart": {
    "type": "GROWTH",
    "principal": 2200000,
    "future_value": 2235750,
    "gain_amount": 35750,
    "caption": "정기적금 12개월 → 약 223만원"
  },
  "source": {
    "name": "은행연합회 소비자포털",
    "url": "https://...",
    "effective_date": "2026-07-01",
    "note": "2026.07 기준 · 은행연합회 소비자포털 · 세전"
  }
}
```

`source.note` 끝의 **` · 세전`** 은 `result_type = FUTURE_VALUE`일 때 서버가 자동으로 붙입니다. (§7.5)

`product_price = 2,200,000` / `return_rate = 3.0` / `period_month = 12` 기준이며, 계산 과정은 §7.5와 같습니다. **원금은 항목이 아니라 상품 가격에서 옵니다.**

**필드 설명**

| 필드 | 설명 |
|---|---|
| `columns` | `compare_criteria`에 선택된 열만. 순서 고정 (가격 → 기간 → 효과 → 예산) |
| `price` | `QUANTITY`는 `unit_price`(단가), **`FUTURE_VALUE`는 항상 `null`** (§7.3) |
| `price_display` | "가격" 열에 그대로 출력할 문자열. `FUTURE_VALUE`는 `"—"` |
| `duration_display` | "지속 가능 기간" 열에 그대로 출력할 문자열. 빈 값은 `"—"` (§2.10) |
| `available_budget` | 사용자 월 예산 구간과 대안 가격의 비교 결과. 재정형은 `NOT_APPLICABLE` |
| `opportunity_cost` | 계산 결과 원본. `result_type`에 따라 채워지는 필드가 다릅니다 (§7.2) |
| `chart` | **시각화 전용 가공값.** `type`으로 그래프 종류가 결정됩니다 |
| `source.note` | 화면에 그대로 출력할 문구. **서버에서 조립합니다** |

**`chart.type`별 계약**

| `result_type` | `chart.type` | 필드 | 그래프 |
|---|---|---|---|
| `QUANTITY` | `COUNT` | `value`(수량), `unit_label`, `caption` | "상품명 = 대안 기회비용" — **개수를 보여주는** 아이콘 반복 또는 막대 |
| `FUTURE_VALUE` | `GROWTH` | `principal`, `future_value`, `gain_amount`, `caption` | 원금 대비 증가분을 보여주는 누적 막대 |

> **`ratio`(`unit_price ÷ product_price`)를 쓰지 않는 이유**: 이 화면이 전하려는 메시지는 "헬스장 1개월은 맥북 가격의 8%"가 아니라 **"맥북 1대 = 헬스장 12개월"** 입니다. 필요한 값은 비율이 아니라 `equivalent_quantity`입니다. 게다가 `FUTURE_VALUE` 행에서는 `future_value ÷ product_price`가 1을 넘어 막대 의미 자체가 깨집니다. 두 유형은 **애초에 다른 그래프**이므로 `chart.type`으로 분기합니다.

> **`chart`를 서버에서 만드는 이유**: `Decimal`을 문자열로 내려주는 `opportunity_cost`와 달리, `chart.value`는 그래프 너비 계산에 바로 쓰이는 값이라 **숫자 타입**입니다. 자릿수 처리도 서버에서 끝냅니다.

> **`FUTURE_VALUE` 행의 "가격" 열을 비우는 이유**: 재정형은 나눗셈을 하지 않으므로 "이 대안의 단가"라는 개념이 없습니다. 원금(220만원)을 그 칸에 넣으면 상품 가격 열과 같은 숫자가 중복되고, 항목 가격(예: 30만원)을 넣으면 사용자가 **"적금이 30만원짜리 상품"** 으로 읽습니다. 원금은 `chart.principal`에만 담고 가격 열은 `—`로 비웁니다. (§7.3)

> **출처 문구를 서버에서 조립하는 이유**: `"2026.07 기준 · 출처 OO"` 표기는 숫자의 신뢰를 만드는 요소이자, 값이 틀렸다는 지적에 대한 방어입니다. (ERD §5.4) 프론트마다 다르게 조립되면 안 됩니다.

> `AVAILABLE_BUDGET` 열이 선택되면 `user_budget`을 사용해 "월 예산 대비 몇 개월" 같은 표현을 만듭니다. `monthly_budget`은 구간 문자열이므로 **정확한 나눗셈을 하지 않고 구간 라벨을 그대로 표시**합니다.

> **`FINANCE` 카테고리는 MVP에 포함됩니다.** (§12) `chart.type` 분기는 선택이 아니라 **필수 구현**입니다. `GROWTH` 행이 실제로 화면에 나옵니다.

**알려진 제약 — `FINANCE` 탭의 "가격" 열**

`columns`는 탭별이 아니라 **최상위에 한 벌만** 있습니다. `FINANCE` 탭은 모든 행의 `price`가 `null`이므로 **"가격" 열 전체가 `—`로 채워집니다.**

MVP에서는 그대로 둡니다. 없애려면 `columns`를 탭 안으로 옮겨야 합니다.

```json
"tabs": [
  { "category": {...}, "columns": [...], "rows": [...] }
]
```

> 지금 고치지 않는 이유는 응답 구조가 바뀌면 §5.3의 `PATCH` 응답(`columns`를 함께 내려주는 부분)까지 같이 흔들리기 때문입니다. **빈 열 하나가 보이는 것은 잘못된 숫자가 보이는 것보다 낫습니다.** 재정 카테고리를 켠 뒤 화면이 어색하면 그때 옮깁니다.

---

## 7. 기회비용 계산 규칙

`Alternative`와 비교표 응답의 계산 필드가 **언제 무엇으로 채워지는지**를 정의합니다. 계산 구현은 `analyses/calculator.py`이며, 이 섹션이 그 함수의 명세입니다.

### 7.1 두 갈래

`AlternativeItem.calc_type`이 `Alternative.result_type`을 결정합니다. **AI가 정하지 않습니다.**

| `calc_type` | 의미 | → `result_type` | 카테고리 |
|---|---|---|---|
| `UNIT_PRICE` | 단가 환산 | `QUANTITY` | 여행·운동·문화·생활편의·디지털 |
| `SAVINGS` | 적금 | `FUTURE_VALUE` | 재정 |
| `DEPOSIT` | 예금 | `FUTURE_VALUE` | 재정 |
| `INVESTMENT` | 투자 | `FUTURE_VALUE` | 재정 |

### 7.2 `result_type`별 채워지는 필드

DB `CheckConstraint`(`valid_alternative_result`)와 동일한 규칙입니다. **응답에서도 반대쪽 필드는 항상 `null`입니다.**

| 필드 | `QUANTITY` | `FUTURE_VALUE` |
|---|---|---|
| `equivalent_quantity` | **필수** (`"12.22"`, 문자열) | `null` |
| `future_value` | `null` | **필수** (`2235750`, 정수) |
| `display_text` | 필수 | 필수 |
| `chart.type` (§6.5) | `COUNT` | `GROWTH` |
| `unit_price` (§7.3) | `item.average_price` | `product_price` (원금) |
| `unit_price_display` (§6.2) | `"180,000원"` | **`null`** |
| 비교표 `price` / `price_display` (§6.5) | `unit_price` / `"180,000원"` | **`null`** / `"—"` |
| `duration_display` | AI가 쓴 값 (없으면 `"—"`) | `"{period_month}개월"` |
| `source.note` 꼬리말 | 없음 | **` · 세전`** |

> 프론트는 `result_type`으로 분기하면 됩니다. **`equivalent_quantity`의 `null` 여부로 판단하지 마세요.**

### 7.3 계산 입력값의 출처

| 입력값 | 출처 | 비고 |
|---|---|---|
| 상품 가격 | `Consideration.product_price` | 고민 생성 시점 스냅샷 |
| 단가 | `AlternativeItem.average_price` → `Alternative.unit_price`에 복사 | 생성 시점 스냅샷 |
| 이율·기간 | **`AlternativeItem.calc_params` (JSONB)** | 시드 데이터로 우리가 입력 |
| 단위 | `AlternativeItem.unit_label` | `회` `박` `개월` `잔` `마리` |

> **이율과 기간을 AI도 사용자도 정하지 않습니다.** `calc_params`에 미리 넣어둔 값만 씁니다. AI가 이율을 만들면 같은 항목이 호출할 때마다 다른 수익률을 내놓아 숫자를 믿을 수 없게 됩니다. (ERD §1과 같은 이유)

**`Alternative.unit_price`에 무엇을 저장하는가**

`unit_price`는 `PositiveIntegerField` + `unit_price > 0` 제약이라 **비워둘 수 없습니다.** `result_type`에 따라 의미가 다릅니다.

| `result_type` | `unit_price` 값 | 역할 |
|---|---|---|
| `QUANTITY` | `item.average_price` | 나눗셈의 **분모**. 계산에 직접 쓰임 |
| `FUTURE_VALUE` | `product_price` (= 원금) | 계산에 쓰인 **원금 스냅샷**. 나눗셈은 하지 않음 |

두 경우 모두 "**그 대안을 계산할 때 사용한 기준 금액**"이라는 점은 같습니다. 나중에 `AlternativeItem`의 가격이 바뀌어도 과거 계산의 입력값이 보존됩니다.

> **`FUTURE_VALUE`일 때 `item.average_price`를 넣지 않습니다.** 재정 항목의 `average_price`(예: 적금 상품의 최소 납입액 30만원)는 계산에 전혀 쓰이지 않는 값입니다. 그걸 `unit_price`에 넣으면 "계산에 사용한 금액"이라는 필드의 의미가 깨지고, 비교표에 그대로 노출되면 사용자가 **"적금이 30만원짜리 상품"** 으로 읽습니다. 그래서 비교표의 `price`도 `null`로 내려보냅니다. (§6.5)

> **항목 이름에도 금액을 넣지 않습니다.** `"정기적금 (월 30만원, 연 3%)"`처럼 이름에 납입액이 박혀 있으면, 원금이 상품 가격에서 오는 것과 모순되어 사용자가 화면에서 두 숫자를 동시에 봅니다. 시드 데이터의 `name`은 **`"정기적금 (연 3%)"`** 처럼 이율·기간만 담고, 금액은 `spec_note`에도 넣지 않습니다.

### 7.4 소비형 — `calc_type = UNIT_PRICE`

```text
equivalent_quantity = product_price ÷ unit_price
```

```text
예) 2,200,000 ÷ 180,000 = 12.2222...
    → equivalent_quantity = 12.22
    → display_text = "헬스장 약 12개월"
```

**정밀도 규칙**

| 항목 | 규칙 |
|---|---|
| 저장 | `Decimal(8, 2)` — 소수 셋째 자리에서 **버림**(`ROUND_DOWN`) |
| 응답 | 문자열 `"12.22"` (부동소수점 오차 방지) |
| `chart.value` | 숫자 `12.22` |
| `display_text` | 아래 표기 규칙 |

**`display_text` 표기 규칙**

| 수량 | 표기 | 예 |
|---|---|---|
| `>= 1` | 정수로 **내림** | `12.22` → `"헬스장 약 12개월"` |
| `< 1` | 소수 첫째 자리까지 내림 | `0.68` → `"제주도 2박 3일 여행 약 0.6회"` |

```text
display_text = "{item.name} 약 {수량}{unit_label}"
```

> **반올림이 아니라 내림인 이유**: `11.9개월`을 `12개월`로 올리면 실제보다 기회비용을 크게 보여주게 됩니다. 이 서비스의 숫자는 "적어도 이만큼은 된다"여야 신뢰를 얻습니다.

**경계 조건**

- `unit_price > 0`은 DB 제약으로 보장되므로 0으로 나누는 경우는 없습니다.
- `equivalent_quantity`는 `Decimal(8, 2)`라 **최대 `999999.99`** 입니다. 초과하는 항목은 **후보 조회 단계에서 미리 제외합니다.** (§7.7)

### 7.5 재정형 — `calc_type = SAVINGS / DEPOSIT / INVESTMENT`

"상품 가격만큼의 돈을 대신 운용하면 얼마가 되는가"를 계산합니다. **나눗셈이 아닙니다.**

#### `calc_params` 스키마 (확정)

| 키 | 타입 | 사용하는 `calc_type` | 설명 |
|---|---|---|---|
| `period_month` | int | 전부 | 비교 기간 (개월). **`> 0`** |
| `return_rate` | float | 전부 | **퍼센트 단위** — `7.0`은 `7%` |
| `base_date` | date | `INVESTMENT` | 수익률 기준일 |
| `ticker` | string | `INVESTMENT` (선택) | 종목 코드. 계산에 쓰지 않음 |

```json
{ "period_month": 12, "return_rate": 3.0 }
{ "period_month": 12, "return_rate": 7.0, "base_date": "2026-07-28", "ticker": "379800" }
```

**`calc_params`에 저장하지 않는 값**

| 값 | 어디서 오는가 |
|---|---|
| `product_price` | `Consideration.product_price` — 모든 계산의 **시작 금액** |
| `monthly_amount` | **계산으로 구합니다** — `product_price ÷ period_month` |

> **`monthly_amount`를 저장하지 않는 이유**: 항목에 `월 10만원`을 박아두면 상품 가격이 220만원이든 120만원이든 같은 금액을 모으게 되어, **원금을 `product_price`로 잡기로 한 결정과 충돌**합니다. 상품 가격에서 나누면 가격이 달라질 때 자동으로 따라갑니다.

> **`return_rate`는 퍼센트 단위입니다.** `0.03`이 아니라 `3.0`으로 저장합니다. 계산에서는 `r = return_rate / 100`으로 변환해 씁니다. 시드 데이터를 사람이 채우므로 화면에 보이는 숫자와 같은 단위로 두는 편이 실수가 적습니다.

#### 공식

| `calc_type` | 공식 | `return_rate`의 의미 |
|---|---|---|
| `DEPOSIT` (예금, 단리) | `FV = P × (1 + r × n/12)` | **연이율** — 기간에 비례 |
| `SAVINGS` (적금, 단리) | `m = P ÷ n`<br>`이자 = m × (r/12) × n(n+1)/2`<br>`FV = P + 이자` | **연이율** — 기간에 비례 |
| `INVESTMENT` (투자) | `FV = P × (1 + r)` | **기준일까지 실현된 수익률** — 기간에 비례하지 않음 |

```text
P = product_price          (시작 금액)
r = return_rate ÷ 100      (3.0 → 0.03)
n = period_month           (개월)
m = P ÷ n                  (월 납입액, 파생값)
```

> **같은 `return_rate` 키지만 의미가 다릅니다.** 적금·예금은 **연이율**이라 기간이 길수록 이자가 늘고, 투자는 `base_date`까지 **이미 실현된 수익률**이라 기간을 곱하지 않습니다. ETF 수익률에 기간을 다시 곱하면 실제로 일어나지 않은 수익을 만들어내게 됩니다.

**예시 1 — `SAVINGS`, 상품가 2,200,000원, `return_rate: 3.0`, `period_month: 12`**

```text
r    = 3.0 ÷ 100 = 0.03
m    = 2,200,000 ÷ 12 = 183,333.333...   (버리지 않음)
이자  = 183,333.333... × (0.03 ÷ 12) × (12 × 13 ÷ 2)
     = 183,333.333... × 0.195
     = 35,750
FV   = 2,200,000 + 35,750 = 2,235,750

future_value = 2235750
display_text = "정기적금 12개월 → 약 223만원"   ← 223.575만원 내림
```

**예시 2 — `INVESTMENT`, 상품가 2,200,000원, `return_rate: 7.0`, `base_date: 2026-07-28`**

```text
r  = 7.0 ÷ 100 = 0.07
FV = 2,200,000 × 1.07 = 2,354,000

future_value = 2354000
display_text = "KODEX 미국S&P500 (2026-07-28 기준) → 약 235만원"   ← 235.4만원 내림
```

**정밀도·표기 규칙**

| 항목 | 규칙 |
|---|---|
| 중간 계산 | **반올림·버림하지 않습니다.** `Decimal`로 끝까지 계산합니다 |
| `future_value` | 마지막에만 원 단위로 **버림** (`PositiveIntegerField`) |
| `display_text` 금액 | **만원 단위 내림** — `2,235,750` → `223.575만` → `약 223만원` |
| 세금 | **세전으로 계산합니다.** 이자소득세(15.4%)를 반영하지 않고, `source.note`에 표기합니다 |

> **중간값을 버리면 안 되는 이유**: 위 예시에서 `m`을 먼저 `183,333`으로 버리면 이자가 `35,749`가 되어 결과가 1원 달라집니다. `float`이 아니라 `Decimal`을 쓰고, **버림은 마지막 한 번만** 합니다.

> **`display_text`도 내림입니다.** `223.575만원`을 `224만원`으로 올리면 §7.4와 마찬가지로 기회비용을 실제보다 크게 보여주게 됩니다. 두 갈래 모두 같은 규칙을 씁니다.

**문구 템플릿은 `calc_type`마다 다릅니다.** `INVESTMENT`만 기준일을 함께 표기합니다.

| `calc_type` | `display_text` |
|---|---|
| `SAVINGS` / `DEPOSIT` | `"{item.name} {period_month}개월 → 약 {금액}만원"` |
| `INVESTMENT` | `"{item.name} ({base_date} 기준) → 약 {금액}만원"` |

```text
정기적금 (연 3%) 12개월 → 약 223만원
KODEX 미국S&P500 (2026-07-28 기준) → 약 235만원
```

> **`INVESTMENT`에 기간을 쓰지 않는 이유**: ETF는 "몇 개월 넣어두면 얼마"가 아니라 **특정 기준일까지의 실현 수익률**입니다. `period_month`는 다른 대안과 기간을 맞추기 위한 값이지 수익률을 만들어내는 값이 아니므로, 문구에는 **기준일을 표기**합니다.

**`duration`과 `expected_effect`도 서버가 만듭니다**

재정형에서는 이 두 필드가 계산 결과에서 파생되므로 **AI에게 요구하지 않습니다.** (§6.2)

| `calc_type` | `duration` | `expected_effect` |
|---|---|---|
| `SAVINGS` / `DEPOSIT` | `"{period_month}개월"` | `"{period_month}개월 뒤 약 {금액}만원"` |
| `INVESTMENT` | `"{period_month}개월"` | `"{base_date} 기준 약 {금액}만원"` |

금액은 `display_text`와 **같은 만원 단위 내림**을 씁니다. 한 항목의 모든 문구가 같은 값에서 나오므로 화면에서 어긋날 수 없습니다.

`SAVINGS`는 월 납입액을 함께 보여줍니다.

```text
expected_effect = "월 183,333원씩 12개월 → 약 223만원"
```

| 필드 | `QUANTITY` | `FUTURE_VALUE` |
|---|---|---|
| `duration` | AI | **서버** (`period_month`) |
| `expected_effect` | AI | **서버** (계산 결과) |
| `ai_reason` | AI | AI |
| `display_text` | 서버 | 서버 |

> 재정형은 `duration`이 항상 채워지므로 빈 값이 나오지 않습니다. 다만 **소비형은 AI가 `duration`을 빠뜨릴 수 있습니다.** `Alternative.duration`이 `CharField(blank=True)`라 빈 문자열이 저장될 수 있으므로, 화면에 출력할 문자열은 **서버가 `duration_display`로 완성해 내려보냅니다** — 빈 값이면 `"—"`입니다. (§2.10) 프론트가 빈 값을 대시로 바꾸지 않습니다.

**"세전" 표기는 서버가 붙입니다**

```text
FUTURE_VALUE 행의 source.note
= "{effective_date} 기준 · {source_name} · 세전"
```

```text
2026.07 기준 · 은행연합회 소비자포털 · 세전
```

`result_type`으로 판정되므로 자동으로 붙습니다. **시드 데이터 작성자가 `spec_note`에 "세전"을 적었는지에 의존하지 않습니다.**

> **`source.note`를 서버가 조립하기로 한 이유가 여기에도 그대로 적용됩니다.** 표기가 빠지면 숫자가 과장됩니다. 세전으로 계산하고 표기를 누락하는 것은 실제보다 수익을 크게 보여주는 것이고, 그건 §7.4에서 내림을 쓰기로 한 이유와 정확히 반대되는 결과입니다. 사람의 기억에 맡기면 언젠가 빠집니다.

> 비과세 한도·금융소득종합과세까지 반영하면 개인별로 결과가 달라져 MVP 범위를 넘습니다. 그래서 **세전으로 계산하되 반드시 표기합니다.**

> `INVESTMENT`에도 같은 꼬리말을 붙입니다. ETF 수익은 상품 유형에 따라 과세 여부가 갈리므로, "세전"이라고 밝혀두는 편이 안전합니다.

> **ETF(`INVESTMENT`)는 실시간 시세를 조회하지 않습니다.** `base_date` 시점의 수익률을 `return_rate`에 고정값으로 저장하고, 화면에 기준일을 함께 표기합니다. (ERD §7)

> **ERD §7과의 차이 — 이 문서가 최신입니다.** ERD의 `calc_params` 예시에는 `monthly_amount: 300000`, `principal: 1000000`처럼 **원금이 항목에 박혀** 있고 키 이름도 `annual_rate`·`term_months`입니다. 그대로 쓰면 220만원짜리 상품이든 50만원짜리 상품이든 같은 미래가치가 나와 기회비용이 성립하지 않습니다.
>
> 팀 논의로 위 스키마를 확정했으므로 **[ERD.md](ERD.md) §7도 같은 내용으로 갱신해야 합니다.**
>
> | ERD §7 | 확정 |
> |---|---|
> | `annual_rate` (0.03) | `return_rate` (3.0, 퍼센트) |
> | `term_months` | `period_month` |
> | `monthly_amount` 저장 | `product_price ÷ period_month`로 파생 |
> | `principal` 저장 | `Consideration.product_price` 사용 |
> | `INVESTMENT`에 수익률 없음 | `return_rate` 필수 |

### 7.6 계산 함수 시그니처

```python
# analyses/calculator.py

def calculate_opportunity_cost(
    item: AlternativeItem,
    product_price: int,
) -> CalculationResult:
    """calc_type에 따라 QUANTITY 또는 FUTURE_VALUE 결과를 반환한다."""


@dataclass(frozen=True)
class CalculationResult:
    unit_price: int
    result_type: str
    equivalent_quantity: Decimal | None
    future_value: int | None
    duration: str
    expected_effect: str
    display_text: str
```

계산기는 기회비용 결과와 `display_text`, 재정형의 `duration` 및
`expected_effect`를 만듭니다. `unit_price_display`, `chart`, `source.note`는
`alternatives/api_views.py`의 직렬화 함수에서 만듭니다.

```python
duration = calculation.duration or selection["duration"].strip()
expected_effect = (
    calculation.expected_effect
    or selection["expected_effect"].strip()
)
```

`UNIT_PRICE` 계산 결과의 두 문자열은 빈 문자열이므로 AI가 작성한 값을
사용하고, 재정형은 계산 결과가 채워져 있으므로 서버 값을 사용합니다.

AI 호출 없이 순수 함수로 동작하므로 **단위 테스트를 먼저 작성합니다.** 최소 케이스는 다음과 같습니다.

```text
UNIT_PRICE  나누어떨어짐 / 소수 발생 / 결과 < 1 / 상한 초과
DEPOSIT     period_month=12 / 0개월 방어 / return_rate 퍼센트 변환
SAVINGS     period_month=12 / n(n+1)/2 공식 검증 / 중간값 버림 없음
            monthly_amount = product_price ÷ period_month
INVESTMENT  return_rate 양수 / 음수(손실) / 전액 손실
표기        만원 단위 내림 (223.575만 → 223) / 정수 내림 (12.22 → 12)
필드 소유    FUTURE_VALUE는 duration·expected_effect를 채우고
            QUANTITY는 빈 문자열로 둔다
            INVESTMENT는 기간을 곱하지 않는다 (FV = P × (1+r))
직렬화      unit_price_display가 FUTURE_VALUE에서 None
            source.note에 " · 세전"이 붙는지
공통        result_type과 채워진 필드가 CheckConstraint를 만족하는지
```

### 7.7 계산 불가 후보 걸러내기

계산이 실패할 수 있는 조합이 있습니다.

| 조건 | 이유 |
|---|---|
| `equivalent_quantity > 999999.99` | `Decimal(8, 2)` 상한 초과 (§7.4) |
| `future_value <= 0` | `PositiveIntegerField` 위반. `return_rate`가 `-1` 이하일 때 (§7.5) |
| `period_month <= 0` | 0으로 나눔 |
| `calc_params` 필수 키 누락 | 아래 표 |

**필수 키는 `calc_type`마다 다릅니다.**

| `calc_type` | 필수 키 |
|---|---|
| `UNIT_PRICE` | 없음 (`calc_params`가 비어 있어도 됨) |
| `SAVINGS` / `DEPOSIT` | `period_month` (`> 0`), `return_rate` |
| `INVESTMENT` | `period_month` (`> 0`), `return_rate`, `base_date` |

> **`calc_type`을 보지 않고 한 벌로 검사하면 안 됩니다.** `base_date`까지 모든 항목에 요구하면 **적금·예금이 전부 걸러집니다.** 후보가 0이 되어 `NO_CANDIDATE_ITEMS`가 나고, 원인을 찾기 어렵습니다.

> `ticker`는 화면 표시·데이터 관리용이며 계산에 쓰이지 않으므로 **필수 키가 아닙니다.**

**이 판정은 AI 호출 전에 끝냅니다.** `product_price`와 `AlternativeItem`만 있으면 되므로 AI가 필요 없습니다.

```python
def is_calculable(item: AlternativeItem, product_price: int) -> bool:
    """calculate()가 유효한 결과를 내는 항목인지 판정한다."""
```

후보 조회 단계에서 `is_calculable()`을 통과한 항목만 AI에게 넘깁니다. (§6.2 2단계, §6.4 2단계)

> **계산 단계에서 제외하면 안 되는 이유**: AI가 항목을 고르는 것은 §6.2의 4단계이고 계산은 7단계입니다. 7단계에서 후보를 버리면 **그 슬롯이 비어버립니다.** 채우는 방법이 둘 다 나쁩니다 — Gemini를 다시 부르면 응답 시간이 또 늘어나고, 서버가 임의로 고르면 "AI가 추천했다"는 전제가 깨집니다.
>
> 2단계에서 걸러내면 **7단계는 절대 실패하지 않습니다.** 걸러낸 뒤 후보가 3개 미만이면 기존 `NO_CANDIDATE_ITEMS`(409)로 자연스럽게 처리되므로, **예외 경로가 하나 사라집니다.**

> 시드 데이터가 정상이라면 실제로 걸리는 항목은 거의 없습니다. 그래도 `is_calculable()`을 두는 이유는, 값이 잘못 들어왔을 때 **사용자가 20초를 기다린 뒤 500을 보는 대신 즉시 409를 받게 하기 위해서**입니다.

---

## 8. analyses — 의사결정 · 최종 선택 · 소비 기록 (후속 계획)

> 이 절의 페이지와 API는 현재 `analyses` URL에 등록되어 있지 않은 후속
> 설계입니다. 현재 구현 API 목록에는 포함하지 않습니다.

### 8.1 `POST /api/analyses/considerations/<int:pk>/decision/` — AI 의사결정 생성 ★

**요청**

```json
{}
```

**전제 조건**: `status = GENERATED` (대안이 생성되어 있어야 합니다.)

**201 Created**

```json
{
  "id": 7,
  "consideration_id": 12,
  "purpose_fit": "HIGH",
  "purpose_fit_display": "높음",
  "expected_satisfaction": "MIDDLE",
  "expected_satisfaction_display": "중간",
  "recommendation": "MIDDLE",
  "recommendation_display": "중간",
  "key_points": [
    "개발·업무 목적에 성능이 부합합니다",
    "월 예산 대비 약 5개월치 소비입니다",
    "동일 비용으로 여행·자기계발도 가능합니다"
  ],
  "summary": "개발·업무 목적에는 잘 맞지만, 월 예산 30~50만원 기준으로 220만원은 약 5개월치 소비 예산에 해당합니다. 지금 필요한 성능이 아니라면 한 단계 낮은 사양도 고려해볼 만합니다.",
  "ai_model": "gemini-2.5-flash",
  "created_at": "2026-07-30T14:12:44+09:00",
  "chart": {
    "gauge": {
      "key": "purpose_fit",
      "label": "구매 목적 적합도",
      "level": "HIGH",
      "level_display": "높음",
      "score": 88,
      "color": "#2ECC71",
      "angle_deg": 158.4
    },
    "bars": [
      { "key": "purpose_fit", "label": "구매 목적 적합도", "level": "HIGH", "level_display": "높음", "score": 88, "color": "#2ECC71" },
      { "key": "expected_satisfaction", "label": "예상 만족도", "level": "MIDDLE", "level_display": "중간", "score": 55, "color": "#F4C430" },
      { "key": "recommendation", "label": "추천도", "level": "MIDDLE", "level_display": "중간", "score": 55, "color": "#F4C430" }
    ]
  }
}
```

**필드 설명**

| 필드 | 설명 |
|---|---|
| `key_points` | 화면의 체크리스트. **정확히 3줄**, 각 100자 이하. AI가 씁니다 |
| `chart.gauge` | 반원 게이지. `angle_deg`는 **0도가 왼쪽 끝(낮음), 180도가 오른쪽 끝(높음)** |
| `chart.bars` | 막대그래프 3개. `score`는 막대 높이(%), 순서 고정 (적합도 → 만족도 → 추천도) |

> **`score`·`color`를 서버가 내려주는 이유**: §2.10과 같습니다. 게이지 바늘 각도와 막대 높이는 `HIGH`/`MIDDLE`/`LOW`에서 파생되는 값이고, 프론트마다 다르게 매핑되면 같은 등급이 화면마다 다른 높이로 보입니다. 매핑은 `analyses/serializers.py` 한 곳에만 둡니다.

**에러**

| 상황 | code | status |
|---|---|---|
| 없거나 내 고민이 아님 | `NOT_FOUND` | 404 |
| `status != GENERATED` | `INVALID_STATUS` | 409 |
| 이미 의사결정이 있음 | `ALREADY_EXISTS` | 409 |
| AI 실패 / 응답 형식 오류 | `AI_REQUEST_FAILED` | 502 |
| AI 타임아웃 | `AI_TIMEOUT` | 504 |

**AI 응답 계약**

Gemini에게는 **등급 3개와 문장만** 요구합니다. 점수·확률·가격은 받지 않습니다.

```json
{
  "purpose_fit": "HIGH",
  "expected_satisfaction": "MIDDLE",
  "recommendation": "MIDDLE",
  "key_points": ["...", "...", "..."],
  "summary": "..."
}
```

기회비용 숫자는 이미 `Alternative`에 계산되어 있으므로 프롬프트에 근거로 넣고, **AI가 새 숫자를 만들지 않도록 응답 스키마에서 제외합니다.** 등급이 `HIGH`/`MIDDLE`/`LOW`가 아니거나 `key_points`가 3개가 아니면 `AI_REQUEST_FAILED`(502)입니다.

> `Decision`은 `OneToOneField`이므로 고민당 1개만 존재합니다. 다시 만들고 싶다면 별도의 "재생성" 정책이 필요하지만 **MVP에서는 재생성을 제공하지 않습니다.** 이미 있으면 `409 ALREADY_EXISTS`를 주고, 프론트는 `GET`으로 기존 결과를 보여줍니다.

> **`ALREADY_EXISTS` 검사도 `select_for_update()` 안에서 합니다.** (§2.11) 이 API 역시 Gemini 응답까지 수 초가 걸리므로, 잠그지 않으면 그 사이 들어온 두 번째 요청이 "아직 `Decision`이 없다"고 판단하고 통과합니다. 결과적으로 `OneToOneField`의 UNIQUE 제약에 걸려 `409`가 아니라 **500**이 납니다.

> 점수(0~100) 대신 `HIGH` / `MIDDLE` / `LOW` 3단계입니다. LLM이 만드는 숫자 점수는 재현성이 없고 근거가 없는 정밀도를 보여줍니다.

### 8.2 `GET /api/analyses/considerations/<int:pk>/decision/` — 의사결정 조회

`8.1`과 동일한 구조. 아직 없으면 **404 NOT_FOUND**.

### 8.3 `GET/POST /analyses/considerations/<int:pk>/final-choice/` — 최종 선택 (폼)

`FinalChoiceForm` (`analyses/forms.py`)으로 처리합니다. **JSON API가 아닙니다.** 라디오 3개 + 메모 한 줄이고 저장 후 결과 페이지로 이동하므로 화면에 머무를 이유가 없습니다.

**폼 필드**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `choice_type` | choice | ✔ | `PRODUCT` / `ALTERNATIVE` / `POSTPONE` (라디오) |
| `alternative` | int | △ | `ALTERNATIVE`일 때 **필수**, 나머지는 **비어 있어야 함** |
| `memo` | string | | 선택 이유 |
| `decided_on` | date | | 기본값: 오늘 |

`alternative` 선택지는 **해당 고민의 `is_current=True` 대안으로 제한**합니다.

```python
self.fields["alternative"].queryset = Alternative.objects.filter(
    consideration=consideration, is_current=True
)
```

**응답**

- 성공: `302` → `/analyses/considerations/<id>/result/`
- 실패: `200` + 폼 에러가 렌더된 화면

저장에 성공하면 `Consideration.status`가 `DECIDED`로 바뀝니다. 폼 저장과 상태 변경은 `transaction.atomic()`으로 묶고, **`Consideration`을 `select_for_update()`로 잠근 뒤 중복 여부를 검사합니다.** (§2.11) 폼 페이지도 더블클릭·새로고침으로 두 번 제출될 수 있고, `FinalChoice`는 `OneToOneField`라 두 번째 저장이 500이 됩니다.

**검증 규칙**

| 상황 | 처리 |
|---|---|
| `choice_type=ALTERNATIVE`인데 `alternative` 없음 | `clean()` non-field 에러 |
| `choice_type=PRODUCT`/`POSTPONE`인데 `alternative` 있음 | `clean()` non-field 에러 |
| `alternative`가 다른 고민의 대안 | `queryset` 제한으로 애초에 선택 불가 + `clean()`에서 재확인 |
| 이미 최종 선택이 있음 | 폼을 보여주지 않고 결과 페이지로 `302` |
| `status`가 `DRAFT` (대안 생성 전) | `409` 대신 대안 생성 페이지로 `302` + `messages.error` |

> 앞의 두 조건은 `FinalChoice`의 `CheckConstraint`로도 막히지만, DB에서 `IntegrityError`가 터지면 500이 됩니다. **폼 `clean()`에서 먼저 잡고**, `CheckConstraint`는 최후의 방어선으로 둡니다.

> 세 번째 조건(`FinalChoice.consideration_id == FinalChoice.alternative.consideration_id`)은 다른 테이블 행과의 비교라 DB 제약으로 표현할 수 없으므로 **반드시 서비스 레이어에서 검증**합니다. (ERD §8.4) `queryset` 제한만 믿으면 폼을 우회한 요청을 막지 못합니다.

> **페이지 흐름에서는 409를 쓰지 않습니다.** 폼 화면은 `messages` + 리다이렉트로 안내합니다. `409 INVALID_STATUS`는 JSON API에만 해당합니다.

### 8.4 소비 기록 (후순위)

MVP 이후 구현 대상입니다. 인터페이스만 정의해 둡니다.

#### `GET /api/analyses/spending/` — 목록

**쿼리 파라미터**: `year`, `month`, `category`, `page`, `page_size`

```json
{
  "count": 12,
  "page": 1,
  "page_size": 10,
  "has_next": true,
  "total_amount": 843000,
  "results": [
    {
      "id": 55,
      "spent_on": "2026-07-28",
      "category": "운동(건강)",
      "item_name": "헬스장 3개월 등록",
      "amount": 480000,
      "final_choice_id": 4,
      "from_consideration": { "id": 12, "product_name": "Apple 맥북 에어 13 M4" }
    }
  ]
}
```

`final_choice_id`가 있으면 "고민 → 실제 지출"이 연결된 기록입니다.

#### `POST /api/analyses/spending/` — 생성

```json
{
  "spent_on": "2026-07-28",
  "category": "운동(건강)",
  "item_name": "헬스장 3개월 등록",
  "amount": 480000,
  "final_choice_id": 4
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `spent_on` | date | ✔ | 지출 날짜 |
| `category` | string(50) | ✔ | 자유 입력 문자열 |
| `item_name` | string(200) | ✔ | 상품·대안 이름 |
| `amount` | int | ✔ | **1 이상** |
| `final_choice_id` | int | | 연결할 최종 선택 (내 것만, `OneToOne`이므로 중복 불가) |

**에러**: `amount <= 0` → `VALIDATION_ERROR`, 이미 연결된 `final_choice_id` → `ALREADY_EXISTS`

> `SpendingRecord.category`는 FK가 아니라 자유 문자열입니다. 소비 기록은 대안 카테고리 6개에 들어맞지 않는 지출(식비, 교통비 등)도 담아야 하기 때문입니다. (ERD §5.9)

#### `PATCH /api/analyses/spending/<int:pk>/` · `DELETE /api/analyses/spending/<int:pk>/`

수정은 `spent_on`, `category`, `item_name`, `amount`. 삭제는 `204`.

#### `GET /api/analyses/spending/summary/` — 집계 (차트)

**쿼리 파라미터**: `year`(필수), `month`(선택)

```json
{
  "year": 2026,
  "monthly": [
    { "month": "2026-01", "amount": 620000 },
    { "month": "2026-07", "amount": 843000 }
  ],
  "by_category": [
    { "category": "운동(건강)", "amount": 480000, "ratio": 0.569 },
    { "category": "문화(여가)", "amount": 363000, "ratio": 0.431 }
  ],
  "total_amount": 843000
}
```

`(user, spent_on)` 인덱스 위에서 `TruncMonth` + `Sum`으로 계산합니다. **월별 집계 테이블은 두지 않습니다.**

---

## 9. 상태 전이

현재 구현된 API가 변경하는 상태는 `DRAFT`에서 `GENERATED`까지입니다.

```text
DRAFT ──POST /api/alternatives/considerations/<id>/generate/──▶ GENERATED
```

| 엔드포인트 | `DRAFT` | `GENERATED` | `DECIDED` | `CLOSED` |
|---|:---:|:---:|:---:|:---:|
| 대안 생성 `POST .../generate/` | ✔ | ✘ | ✘ | ✘ |
| 개별 재생성 `POST /api/alternatives/<id>/regenerate/` | ✘ | ✔ | ✘ | ✘ |
| 대안 목록 `GET .../considerations/<id>/` | ✔ | ✔ | ✔ | ✔ |
| 비교표 `GET .../comparison/` | ✘ | ✔ | ✔ | ✔ |

`✘`인 조합은 JSON API에서 **409 `INVALID_STATUS`** 입니다.

```json
{
  "error": {
    "code": "INVALID_STATUS",
    "message": "이미 대안이 생성된 고민입니다.",
    "details": { "status": ["현재 상태: GENERATED, 필요한 상태: DRAFT"] }
  }
}
```

`DECIDED`, `CLOSED` 값은 모델에 존재하지만 이를 만드는 의사결정·최종 선택
API는 현재 미구현입니다. 해당 후속 설계는 §8을 참고합니다.

---

## 10. 화면 ↔ API 매핑

| 화면 | 진입 (GET) | 제출 (폼 POST) | 화면 안 동작 (JSON) |
|---|---|---|---|
| 회원가입 1단계 | `/accounts/signup/` | 같은 URL | `GET /api/accounts/check-username/` |
| 회원가입 2단계 | `/accounts/signup/profile/` | 같은 URL | - |
| 로그인 | `/accounts/login/` | 같은 URL | - |
| 마이페이지 | `/accounts/profile/` | - | `GET /api/accounts/me/`<br>`PATCH /api/accounts/me/basic/`<br>`POST /api/accounts/me/password/`<br>`PATCH /api/accounts/me/profile/` |
| 구매 고민 입력 | `/products/considerations/new/` | 같은 URL | `POST /api/products/preview/` |
| 카테고리별 대안 | `/alternatives/considerations/<id>/` | - | `POST /api/alternatives/considerations/<id>/generate/`<br>`GET /api/alternatives/considerations/<id>/`<br>`POST /api/alternatives/<id>/regenerate/` |
| 비교표·기회비용 | `/products/comparison/<id>/` | - | `GET /api/alternatives/considerations/<id>/comparison/` |
| 기회비용 시각화 | `/products/opportunity-cost/<id>/` | - | - (서버 사이드 렌더링, §5.5) |

**"제출" 열과 "화면 안 동작" 열에 같은 동작이 동시에 나오지 않습니다.** (§1)

**현재 백엔드 기준 대안 생성 흐름**

```text
구매 고민 폼 제출
  └─ Consideration(status=DRAFT) 생성
       └─ POST /api/alternatives/considerations/12/generate/
            Gemini 호출 후 카테고리별 대안 3개 생성
            성공 → status=GENERATED + 응답 JSON으로 카드 렌더
            실패 → 에러 메시지 + 재시도

카드의 재생성 버튼 클릭
  └─ POST /api/alternatives/108/regenerate/
       해당 카드만 로딩
       성공 → 그 카드만 교체
       실패 → 카드 유지 + 토스트
```

> 상품 입력 성공 후 `/alternatives/considerations/<id>/` 페이지로
> 이동하는 라우팅은 연결되어 있습니다. 다만 해당 템플릿에서 실제 생성·조회·
> 재생성 API 결과를 카드로 렌더링하는 프론트 연결은 필요합니다.

---

## 11. 구현 체크리스트

### 파일 구조

```text
accounts/
  urls.py  views.py  forms.py      2단계 회원가입·로그인·로그아웃
  api_urls.py                    계정 JSON API URL
  serializers.py                계정 조회·수정 검증

products/
  urls.py  views.py  forms.py      고민 생성 폼·비교표 페이지
  api_urls.py  api_views.py        상품 URL 미리보기 API
  serializers.py  services.py     URL 검증·메타데이터 추출

alternatives/
  urls.py  views.py                고민별 카테고리 대안 페이지
  api_urls.py  api_views.py        generate, list, regenerate, comparison
  services.py      대안 생성·재생성 (검증 포함)
  ai_service.py    Gemini 호출 + 응답 파싱

analyses/
  calculator.py    기회비용 계산 (§7)
```

### 서비스 레이어에서 반드시 검증할 항목

```text
Consideration.categories 개수 <= 3
Alternative.category_id == Alternative.item.category_id
재생성 시 version = 기존 + 1
슬롯별 is_current=True 행은 항상 1개
AI가 반환한 item_id가 후보 목록에 실제로 존재하는지
AI에게 넘기는 후보는 is_calculable()을 통과한 항목만
FUTURE_VALUE 대안의 unit_price는 product_price (item.average_price 아님)
FUTURE_VALUE 대안의 duration·expected_effect는 AI 응답을 무시하고 서버가 채움
FUTURE_VALUE 응답의 unit_price_display / price는 항상 null (§6.2, §6.5)
계산 결과의 duration·expected_effect가 있으면 서버값, 없으면 AI 값을 사용
FUTURE_VALUE의 source.note에는 서버가 " · 세전"을 붙임 (§7.5)
calc_params 필수 키는 calc_type별로 검사 (적금·예금에 base_date 요구 금지)
생성 계열 요청은 select_for_update()로 Consideration을 잠근 뒤 상태 검사
```

### 현재 구현 상태

```text
[✔] Django 세션 기반 2단계 회원가입·로그인·로그아웃
[✔] 아이디 중복 확인
[✔] 내 정보 조회·기본 정보 수정·비밀번호 변경·소비 프로필 수정
[✔] 구매 고민 입력 폼과 카테고리 최대 3개 검증
[✔] 상품 URL 공개 메타데이터 미리보기 + 직접 입력 fallback
[✔] AlternativeItem 시드(생활·편의, 디지털·전자기기)
[✔] Gemini 기반 카테고리별 대안 3개 생성
[✔] 개별 대안 재생성과 버전 관리
[✔] 현재 대안 목록 및 비교표 JSON API
[✔] 상품 입력 → 고민별 카테고리 대안 HTML 페이지 라우팅·렌더링 연결
[ ] 마이페이지 HTML과 계정 API 연결
[ ] AI 의사결정·최종 선택·소비 기록 API
```

> **`calculator.py`를 3번으로 올렸습니다.** 기회비용 계산은 순수 함수라 DB·AI 없이 단위 테스트를 쓸 수 있고, 이 서비스에서 숫자가 틀리면 안 되는 유일한 부분입니다. 여기가 확정돼야 7·9번의 응답 필드가 고정됩니다.

### `.env` 추가 항목

```text
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

Gemini 제한시간은 현재 `config/settings.py`의
`GEMINI_TIMEOUT_MS = 25_000`으로 고정되어 있습니다.

---

## 12. 확정된 결정

### `calc_params` 스키마 — 확정 (§7.5)

```json
{ "period_month": 12, "return_rate": 3.0 }
```

- 모든 계산의 시작 금액은 **`Consideration.product_price`**
- `period_month` — 비교 기간 (개월)
- `return_rate` — **퍼센트 단위** (`7.0` = `7%`). 적금·예금은 연이율, 투자는 기준일까지의 실현 수익률
- `monthly_amount` — **저장하지 않고** `product_price ÷ period_month`로 구함
- `base_date` — `INVESTMENT`만 사용


### 비회원 체험 — 미지원 확정

**전면 로그인 필수입니다.** `Consideration.user`는 `null=False`를 유지하고 `session_key`를 추가하지 않습니다. 고민 관련 모든 페이지·API는 로그인을 요구합니다. (§2.3)

### 재정(`FINANCE`) 카테고리 — MVP 포함 확정

`FINANCE.is_active = True`로 출시합니다. 따라서 다음이 **모두 구현 범위에 포함됩니다.**

| 항목 | 위치 |
|---|---|
| `FUTURE_VALUE` 계산 (적금·예금·투자) | §7.5 |
| `chart.type = GROWTH` 시각화 | §6.5 |
| `unit_price_display` / `price`가 `null`인 카드·행 | §6.2, §6.5 |
| `source.note`의 ` · 세전` 꼬리말 | §7.5 |
| `calc_type`별 필수 키 검사 | §7.7 |

### `AlternativeItem` 시드 데이터 — 분담 완료

카테고리별 최소 3개(권장 10개)가 필요합니다. 조사 항목은 이름·평균 가격·출처·기준일이며, 재정 카테고리는 `calc_params`(`period_month`, `return_rate`, `base_date`)를 함께 채웁니다.

> 후보가 3개 미만인 카테고리는 `NO_CANDIDATE_ITEMS`(409)로 대안 생성이 실패합니다. (§6.2) 재생성을 반복해도 새로운 대안이 나오려면 후보가 넉넉해야 하므로 **10개를 권장합니다.** (ERD §6)

---

## 13. 남은 논의 항목

### AI 호출 방식

현재는 **동기 호출**입니다. 요청 하나가 최대 25초 워커를 점유합니다.

MVP·시연 규모에서는 문제가 없지만, 동시 사용자가 늘면 Celery + 폴링 방식으로 바꿔야 합니다. 그 경우 인터페이스는 다음과 같이 달라집니다.

```text
POST /api/alternatives/considerations/<id>/generate/
→ 202 Accepted { "task_id": "..." }

GET /api/alternatives/tasks/<task_id>/
→ { "status": "PENDING" | "SUCCESS" | "FAILURE", "result": {...} }
```

**응답 스키마 자체는 그대로 재사용**할 수 있으므로, 지금은 동기로 구현하고 필요할 때 전환합니다.

### `FINANCE` 탭의 "가격" 열

`columns`가 탭별이 아니라 최상위에 한 벌만 있어 재정 탭은 가격 열 전체가 `—`가 됩니다. MVP에서는 유지하고, 화면이 어색하면 `columns`를 탭 안으로 옮깁니다. (§6.5 알려진 제약)
