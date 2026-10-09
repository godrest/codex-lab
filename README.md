# 공용 고객관리 DB

SQLAlchemy 2.x와 SQLite로 고객·상품·직원·주문을 관리하는 샘플 DB입니다.
`Faker('ko_KR')`로 한국어 더미 데이터를 생성하며, 생성된 파일은 프로젝트 폴더의 `customer.db`에 저장됩니다.

## 파일 구성

- `models.py`: 모델 4개, 컬럼 주석, PK/FK·CHECK·UNIQUE 제약, 양방향 `relationship`, 주문 조회 인덱스.
- `database.py`: SQLite 엔진, `SessionLocal`, 외래키 검사 활성화, 테이블 생성.
- `seed.py`: 고정 시드 데이터 생성, bulk insert, 기존 데이터 비교, 품질 검증 및 건수 출력.
- `requirements.txt`: 실행에 필요한 SQLAlchemy·Faker 버전 고정.
- [erd.md](erd.md): 실제 DB 스키마를 반영한 Mermaid ERD.

`customer.db`, SQLite 임시 파일, 가상환경, Python 캐시는 Git에서 제외됩니다.
소스와 의존성을 설치한 뒤 아래 명령으로 동일한 데이터셋을 생성할 수 있습니다.

## 설치 및 실행

Python 3.10 이상이 필요합니다. SQLite는 Python에 포함되며 별도 서버 설치가 필요 없습니다.
다음 명령은 프로젝트 폴더에서 PowerShell로 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe database.py
.\.venv\Scripts\python.exe seed.py
```

현재 Python 환경에 의존성이 설치되어 있다면 다음 명령도 가능합니다.

```powershell
python database.py
python seed.py
```

`database.py`는 네 테이블을 생성합니다. 기존 테이블과 데이터는 유지하며,
기존 테이블 구조를 변경하는 마이그레이션은 수행하지 않습니다.
`seed.py`는 DB가 없어도 테이블을 생성한 뒤 데이터를 삽입할 수 있습니다.
어느 폴더에서 실행하더라도 DB 경로는 `database.py`가 있는 폴더로 고정됩니다.

## 생성되는 데이터

- 고객 **10,000명**: 한국어 이름·주소·전화번호, 고유 이메일. VIP 500명(5%), 일반 7,000명(70%), 신규 2,500명(25%).
- 상품 **500개**: 전자제품·생활용품·의류·식품·스포츠 각 100개. 가격은 1,000~2,000,000원 범위에서 1,000원 단위로 생성.
- 직원 **300명**: 한국어 이름, 고유 이메일, 부서, 입사일, 재직 여부.
- 주문 **100,000건**: 완료 90,000건(90%), 배송중 7,000건(7%), 취소 3,000건(3%). 수량은 1~5개.

주문일은 고정 기준일 **2026-10-09** 직전 2년인 **2024-10-09~2026-10-08**에 배정합니다.
730일에 걸쳐 일별 주문 수는 136~137건으로 균등하게 분포합니다.
이 기준일은 실행 날짜에 따라 바뀌지 않습니다.

주문 단가(`unit_price`)는 선택한 상품의 생성 당시 가격과 같습니다.
주문 금액(`total_amount`)은 SQLite의 저장형 생성 컬럼으로 `unit_price * quantity`를 계산합니다.
상품 가격을 나중에 변경해도 기존 주문의 단가와 금액은 유지됩니다.

## 재현성 및 재실행

`random.Random`과 Faker 인스턴스의 시드는 모두 **42**입니다.
동일한 Python 버전과 `requirements.txt`의 고정 버전, 동일한 코드로 실행하면 동일한 데이터셋을 생성합니다.
개발·검증 환경은 Python 3.10.5, SQLAlchemy 2.0.54, Faker 40.41.0입니다.
Faker 버전이 다르면 `seed.py`는 재현성을 위해 오류를 표시하므로 의존성을 먼저 설치해야 합니다.

- 5,000건 단위의 SQLAlchemy bulk insert를 사용하며, 전체 삽입과 검증은 하나의 트랜잭션으로 실행됩니다.
- 기존 데이터가 동일하면 모든 행을 비교·검증하고 종료합니다. 중복 삽입하지 않습니다.
- 기존 데이터가 다르거나 일부만 있으면 오류로 종료하며 기존 데이터를 덮어쓰지 않습니다.
- 이전 모델의 빈 DB는 현재 스키마로 재생성합니다. 데이터가 있는 구형 DB는 별도 마이그레이션이 필요합니다.
- 검증 실패 시 해당 실행의 스키마 변경과 삽입은 롤백됩니다.

## 검증 및 예상 출력

시드 실행 시 테이블별 건수, 고객 등급·주문 상태 비율, 카테고리,
가격·수량 범위, 일별 주문 분포, 주문 금액 및 외래키 무결성을 검증합니다.
성공하면 다음 건수가 출력됩니다. DB 경로와 실행 시간도 함께 출력됩니다.

```text
customers: 10,000
products: 500
employees: 300
orders: 100,000
Validation passed.
```

## 세션 사용 예시

```python
from sqlalchemy import select

from database import SessionLocal
from models import Customer

with SessionLocal() as session:
    customer = session.scalar(select(Customer).order_by(Customer.customer_id).limit(1))
    if customer is not None:
        print(customer.customer_name, customer.grade)
        print(len(customer.orders))
```

고객·상품·직원은 각각 주문과 1:N 관계이며, 모든 주문은 세 개의 필수 외래키를 가집니다.
주문에서 참조 중인 고객·상품·직원 삭제는 `ON DELETE RESTRICT`로 제한됩니다.
날짜는 `YYYY-MM-DD` 형식의 `TEXT`로 저장됩니다.
컬럼 주석은 SQLAlchemy의 `comment` 메타데이터에 있으며 SQLite 자체에는 저장되지 않습니다.
