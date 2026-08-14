# EC2 배포 순서

이 설정은 Ubuntu EC2, Nginx, Gunicorn, RDS PostgreSQL 조합을 기준으로 한다.

## 1. AWS 리소스

- EC2 보안 그룹 인바운드: SSH(22, 본인 IP), HTTP(80), HTTPS(443)
- RDS PostgreSQL 보안 그룹 인바운드: PostgreSQL(5432, EC2 보안 그룹)
- RDS는 EC2와 같은 VPC에 두고 퍼블릭 액세스는 끈다.

## 2. 서버 준비

```bash
sudo apt update
sudo apt install -y nginx git python3-venv python3-pip libpq-dev
sudo mkdir -p /srv/choezy
sudo chown ubuntu:www-data /srv/choezy
git clone <GITHUB_REPOSITORY_URL> /srv/choezy
cd /srv/choezy
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

비공개 저장소라면 배포 전용 GitHub deploy key 또는 제한된 토큰을 사용한다.

## 3. 환경변수

`/etc/choezy.env` 파일을 만들고 실제 값을 입력한다.

```bash
sudo nano /etc/choezy.env
```

```env
DJANGO_SECRET_KEY=<RANDOM_SECRET_KEY>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<EC2_PUBLIC_IP_OR_DOMAIN>
DJANGO_CSRF_TRUSTED_ORIGINS=http://<EC2_PUBLIC_IP_OR_DOMAIN>
DJANGO_USE_HTTPS=False

DB_NAME=<RDS_DATABASE_NAME>
DB_USER=<RDS_USERNAME>
DB_PASSWORD=<RDS_PASSWORD>
DB_HOST=<RDS_ENDPOINT>
DB_PORT=5432
DB_CONN_MAX_AGE=60
DB_SSLMODE=require

GEMINI_API_KEY=<GEMINI_API_KEY>
GEMINI_MODEL=gemini-2.5-flash
```

```bash
sudo chown root:www-data /etc/choezy.env
sudo chmod 640 /etc/choezy.env
```

## 4. DB와 정적 파일

```bash
cd /srv/choezy
sudo -u ubuntu -g www-data bash -c 'set -a; source /etc/choezy.env; set +a; .venv/bin/python manage.py migrate --noinput'
sudo -u ubuntu -g www-data bash -c 'set -a; source /etc/choezy.env; set +a; .venv/bin/python manage.py collectstatic --noinput'
```

필요한 시드 명령과 `createsuperuser`는 최초 배포 때 한 번 실행한다.

## 5. Gunicorn과 Nginx

```bash
sudo cp deploy/ec2/choezy.service /etc/systemd/system/choezy.service
sudo cp deploy/ec2/nginx.conf /etc/nginx/sites-available/choezy
sudo ln -s /etc/nginx/sites-available/choezy /etc/nginx/sites-enabled/choezy
sudo rm /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable --now choezy
sudo nginx -t
sudo systemctl restart nginx
```

서비스 확인:

```bash
sudo systemctl status choezy
sudo journalctl -u choezy -n 100 --no-pager
curl -I http://127.0.0.1
```

## 6. 이후 코드 업데이트

```bash
cd /srv/choezy
git pull origin develop
.venv/bin/pip install -r requirements.txt
sudo -u ubuntu -g www-data bash -c 'set -a; source /etc/choezy.env; set +a; .venv/bin/python manage.py migrate --noinput'
sudo -u ubuntu -g www-data bash -c 'set -a; source /etc/choezy.env; set +a; .venv/bin/python manage.py collectstatic --noinput'
sudo systemctl restart choezy
```

도메인과 HTTPS를 적용한 뒤에는 다음 값을 변경한다.

```env
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
DJANGO_USE_HTTPS=True
```
