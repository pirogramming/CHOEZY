# CHOEZY

> **사용자의 소비 가치관과 구매 목적을 반영하여, 구매 선택으로 인해 포기하는 대안을 비교하고 더 나은 소비 결정을 돕는 서비스**


## 프로젝트 소개

우리는 물건을 구매할 때 가격만 비교하는 경우가 많습니다.

하지만 실제 소비에서는 **'이 돈으로 다른 무엇을 할 수 있었을까?'** 라는 **기회비용(Opportunity Cost)** 이 중요한 판단 기준이 됩니다.

**CHOEZY**는 사용자의 구매 목적과 관심사를 바탕으로 AI가 다양한 대안을 제안하고, 기회비용을 시각화하여 더욱 합리적인 소비 결정을 돕는 서비스입니다.


---

## 프로젝트 목표

* 단순 가격 비교가 아닌 **기회비용 중심의 소비 의사결정 지원**
* AI 기반 맞춤형 비교 대상 추천
* 소비자가 후회 없는 선택을 할 수 있도록 데이터 기반 정보 제공


---
## 실행 방법

### 1. 프로젝트 클론

```bash
git clone https://github.com/pirogramming/CHOEZY.git
cd CHOEZY
```

### 2. 가상환경 생성 및 실행

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 필요한 라이브러리 설치

```bash
pip install -r requirements.txt
```


### 4. 환경 변수(.env) 설정

프로젝트 루트에 `.env` 파일을 생성한 후 아래 내용을 입력합니다.

```env
SECRET_KEY=your_secret_key

DEBUG=True

DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

GEMINI_API_KEY=your_gemini_api_key
```


### 5. 데이터베이스 마이그레이션

```bash
python manage.py makemigrations
python manage.py migrate
```


### 6. 개발 서버 실행

```bash
python manage.py runserver
```


### 7. 브라우저 접속

```
http://127.0.0.1:8000/
```

### 8. 관리자 계정 생성 (선택)

```bash
python manage.py createsuperuser
```

관리자 페이지

```
http://127.0.0.1:8000/admin/
```

---

## 기술 스택

### Front-end

* HTML
* CSS
* JavaScript

### Back-end

* Django
* Python

### Database

* PostgreSQL

### AI

* Gemini API

### Deployment

* AWS EC2 (Ubuntu)
* Amazon RDS for PostgreSQL
* Gunicorn / Nginx
* Duck DNS / Let's Encrypt (HTTPS)
* GitHub Actions (develop 브랜치 자동 배포)

배포 주소: [https://choezy.duckdns.org](https://choezy.duckdns.org)



---

## 프로젝트 구조


```text
CHOEZY/
├── accounts/        # 회원 관리
├── alternatives/    # AI 대안 생성
├── analyses/        # 비교 및 분석
├── config/          # Django 프로젝트 설정
├── core/            # 공통 페이지 및 Base Template
├── docs/            # 프로젝트 문서
├── media/           # 업로드 파일
├── products/        # 상품 검색 및 정보
├── static/          # CSS, JS, Images
├── templates/       # 공통 컴포넌트
├── manage.py
├── requirements.txt
└── README.md
```



---

## 👥 Team

| 역할        | 담당  |
| --------- | --- |
| PM/Front-end  | 임현아 |
| Front-end | 문예지 |
| Back-end  | 김민서 |
| Back-end  | 이지연 |

---

