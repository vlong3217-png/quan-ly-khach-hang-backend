import sys
import os

backend_path = os.path.abspath(r'D:\Nhóm 10 người\quan-ly-khach-hang-backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import SessionLocal, engine
from app.models.user import Base, User as UserModel
from app.models.product import Product as ProductModel
from app.models.customer import Customer as CustomerModel
from app.models.contact import Contact as ContactModel
from app.models.campaign import Campaign as CampaignModel
from app.models.lead import Lead as LeadModel
from app.models.opportunity import OpportunityModel
from app.models.quote import QuoteModel
from app.core.security import hash_password
from datetime import datetime, date

Base.metadata.create_all(bind=engine)
db = SessionLocal()

print("=== SEEDING LOCAL DATABASE (crm_local.db) ===")

# 1. Users
users_data = [
    {
        "id": 1,
        "email": "vlong3217@gmail.com",
        "username": "admin",
        "full_name": "Nguyễn Văn Long (Admin)",
        "role": "ADMIN",
        "phone": "0901234567",
        "email_signature": "Trân trọng,\nNguyễn Văn Long | CEO Công Ty TNHH Giải Pháp Công Nghệ ABC\nHotline: 0901 234 567",
        "is_active": True,
        "status": "ACTIVE",
        "hashed_password": hash_password("123456")
    },
    {
        "id": 2,
        "email": "huy.tran@congtydemo.vn",
        "username": "huy.tran",
        "full_name": "Trần Quang Huy",
        "role": "MANAGER",
        "team_id": 1,
        "phone": "0918234567",
        "is_active": True,
        "status": "ACTIVE",
        "hashed_password": hash_password("123456")
    },
    {
        "id": 3,
        "email": "mai.nguyen@congtydemo.vn",
        "username": "mai.nguyen",
        "full_name": "Nguyễn Thị Mai",
        "role": "USER",
        "team_id": 1,
        "phone": "0987112233",
        "is_active": True,
        "status": "ACTIVE",
        "hashed_password": hash_password("123456")
    },
    {
        "id": 4,
        "email": "nam.le@congtydemo.vn",
        "username": "nam.le",
        "full_name": "Lê Văn Nam",
        "role": "USER",
        "team_id": 2,
        "phone": "0345667788",
        "is_active": True,
        "status": "ACTIVE",
        "hashed_password": hash_password("123456")
    }
]

for u in users_data:
    existing = db.query(UserModel).filter(UserModel.email == u["email"]).first()
    if not existing:
        db.add(UserModel(**u))
    else:
        for k, v in u.items():
            setattr(existing, k, v)
db.commit()
print("  ✓ Đã cập nhật 4 tài khoản người dùng.")

# 2. Products
products_data = [
    {
        "code": "CRM-PRO-ONETIME",
        "name": "Phần mềm Quản lý Khách hàng CRM Pro (Vĩnh viễn)",
        "product_type": "ONE_TIME",
        "unit": "Gói",
        "list_price": 25000000.0,
        "floor_price": 20000000.0,
        "cost_price": 10000000.0,
        "status": "ACTIVE"
    },
    {
        "code": "CLOUD-BIZ-SUB",
        "name": "Dịch vụ CRM Cloud Doanh Nghiệp (Thuê bao năm)",
        "product_type": "SUBSCRIPTION",
        "unit": "User/Năm",
        "list_price": 1800000.0,
        "floor_price": 1500000.0,
        "cost_price": 600000.0,
        "status": "ACTIVE"
    },
    {
        "code": "SRV-TRAIN-01",
        "name": "Gói đào tạo & Hướng dẫn sử dụng tận nơi",
        "product_type": "ONE_TIME",
        "unit": "Buổi",
        "list_price": 5000000.0,
        "floor_price": 4000000.0,
        "cost_price": 2000000.0,
        "status": "ACTIVE"
    }
]

for p in products_data:
    ex = db.query(ProductModel).filter(ProductModel.code == p["code"]).first()
    if not ex:
        db.add(ProductModel(**p))
db.commit()
print("  ✓ Đã cập nhật 3 sản phẩm và bảng giá.")

# 3. Customers & Contacts
customers_data = [
    {
        "id": 1,
        "name": "Công ty Cổ phần Công nghệ & Giải pháp FPT Smart",
        "tax_code": "0101234567",
        "industry": "Công nghệ thông tin",
        "company_size": "50-100 nhân viên",
        "website": "https://fptsmart.vn",
        "address": "Tầng 6, Tòa nhà FPT, Phố Duy Tân, Cầu Giấy, Hà Nội",
        "email": "contact@fptsmart.vn",
        "phone": "02473008888",
        "status": "CUSTOMER",
        "owner_id": 1
    },
    {
        "id": 2,
        "name": "Tập đoàn Xây dựng & Phát triển Đô thị Hòa Bình Group",
        "tax_code": "0309876543",
        "industry": "Xây dựng & Bất động sản",
        "company_size": "200-500 nhân viên",
        "website": "https://hoabinhgroup.vn",
        "address": "Số 235 Võ Thị Sáu, Phường 7, Quận 3, TP. Hồ Chí Minh",
        "email": "info@hoabinhgroup.vn",
        "phone": "02839301234",
        "status": "POTENTIAL",
        "owner_id": 1
    },
    {
        "id": 3,
        "name": "Công ty TNHH Dược phẩm & Thiết bị Y tế Minh Tâm",
        "tax_code": "0105556677",
        "industry": "Dược phẩm & Y tế",
        "company_size": "20-50 nhân viên",
        "website": "https://minhtampharma.com",
        "address": "Số 48 Phố Quán Sứ, Phường Hàng Bông, Quận Hoàn Kiếm, Hà Nội",
        "email": "kinhdoanh@minhtampharma.com",
        "phone": "02438889999",
        "status": "CUSTOMER",
        "owner_id": 1
    }
]

for c in customers_data:
    ex = db.query(CustomerModel).filter(CustomerModel.id == c["id"]).first()
    if not ex:
        db.add(CustomerModel(**c))
    else:
        for k, v in c.items():
            setattr(ex, k, v)
db.commit()
print("  ✓ Đã cập nhật 3 khách hàng doanh nghiệp.")

contacts_data = [
    {
        "name": "Hoàng Đức Nam",
        "phone": "0912334455",
        "email": "nam.hoang@fptsmart.vn",
        "position": "Giám đốc Công nghệ (CTO)",
        "is_primary": True,
        "customer_id": 1
    },
    {
        "name": "Trần Thị Lan Anh",
        "phone": "0988776655",
        "email": "lananh@hoabinhgroup.vn",
        "position": "Trưởng phòng Mua sắm & Đấu thầu",
        "is_primary": True,
        "customer_id": 2
    },
    {
        "name": "Nguyễn Minh Tuấn",
        "phone": "0903445566",
        "email": "tuan.minh@minhtampharma.com",
        "position": "Phó Tổng Giám Đốc",
        "is_primary": True,
        "customer_id": 3
    }
]

for ct in contacts_data:
    ex = db.query(ContactModel).filter(ContactModel.email == ct["email"]).first()
    if not ex:
        db.add(ContactModel(**ct))
db.commit()
print("  ✓ Đã cập nhật 3 người liên hệ chính.")

# 4. Campaigns & Leads
campaigns_data = [
    {
        "id": 1,
        "code": "CAMP-2026-01",
        "name": "Chiến dịch Chuyển Đổi Số Đầu Năm 2026",
        "channel": "DIGITAL",
        "budget": 30000000.0,
        "actual_cost": 15000000.0,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 3, 31),
        "target_leads": 50,
        "expected_revenue": 150000000.0,
        "status": "ACTIVE",
        "description": "Quảng cáo Google Search và Facebook Ads",
        "owner_id": 1
    },
    {
        "id": 2,
        "code": "CAMP-2026-02",
        "name": "Hội Thảo B2B: Tối Ưu Quản Trị Khách Hàng 4.0",
        "channel": "EVENT",
        "budget": 50000000.0,
        "actual_cost": 25000000.0,
        "start_date": date(2026, 2, 15),
        "end_date": date(2026, 4, 30),
        "target_leads": 100,
        "expected_revenue": 300000000.0,
        "status": "ACTIVE",
        "description": "Tổ chức hội thảo tại Hà Nội",
        "owner_id": 1
    }
]

for camp in campaigns_data:
    ex = db.query(CampaignModel).filter(CampaignModel.id == camp["id"]).first()
    if not ex:
        db.add(CampaignModel(**camp))
db.commit()
print("  ✓ Đã cập nhật 2 chiến dịch marketing.")

leads_data = [
    {
        "name": "Nguyễn Quốc Bảo",
        "title": "Giám đốc điều hành",
        "company": "Công ty Vận tải & Logistics Bảo An",
        "email": "bao.nguyen@vantai-baoan.vn",
        "phone": "0977112233",
        "industry": "Vận tải / Logistics",
        "budget": 50000000.0,
        "source": "FACEBOOK",
        "status": "CONTACTED",
        "campaign_id": 1,
        "notes": "Quan tâm gói CRM Pro cho 15 nhân viên điều vận.",
        "owner_id": 1
    },
    {
        "name": "Phạm Thu Hương",
        "title": "Kế toán trưởng",
        "company": "Hệ thống Nha khoa Thẩm mỹ Việt Pháp",
        "email": "huong.pham@nhakhoavietphap.vn",
        "phone": "0933445566",
        "industry": "Y tế / Chăm sóc sức khỏe",
        "budget": 35000000.0,
        "source": "EVENT",
        "status": "QUALIFIED",
        "campaign_id": 2,
        "notes": "Đã tham gia hội thảo, muốn đăng ký dùng thử 3 chi nhánh.",
        "owner_id": 1
    },
    {
        "name": "Đặng Đình Trọng",
        "title": "Trưởng phòng Kinh doanh",
        "company": "Bất động sản Đất Vàng Miền Trung",
        "email": "trong.dang@datvangland.com",
        "phone": "0944556677",
        "industry": "Bất động sản",
        "budget": 20000000.0,
        "source": "GOOGLE",
        "status": "NEW",
        "campaign_id": 1,
        "notes": "Điền form đăng ký tư vấn qua website.",
        "owner_id": 1
    }
]

for ld in leads_data:
    ex = db.query(LeadModel).filter(LeadModel.email == ld["email"]).first()
    if not ex:
        db.add(LeadModel(**ld))
db.commit()
print("  ✓ Đã cập nhật 3 khách hàng tiềm năng (Leads).")

# 5. Opportunities & Quotes
opps_data = [
    {
        "id": 1,
        "title": "Triển khai CRM Cloud 50 Users - FPT Smart",
        "value": 90000000.0,
        "stage": "PROPOSAL",
        "customer_id": 1,
        "contact_person": "Hoàng Đức Nam",
        "source": "DIRECT",
        "expected_close_date": date(2026, 11, 30),
        "win_probability": 70.0,
        "probability_notes": "Khách hàng rất hài lòng sau buổi demo",
        "description": "Gói 50 users Cloud năm kèm đào tạo tận nơi",
        "owner_id": 1,
        "status": "OPEN"
    },
    {
        "id": 2,
        "title": "Cung cấp Bản quyền Vĩnh viễn - Hòa Bình Group",
        "value": 25000000.0,
        "stage": "NEGOTIATION",
        "customer_id": 2,
        "contact_person": "Trần Thị Lan Anh",
        "source": "REFERRAL",
        "expected_close_date": date(2026, 12, 15),
        "win_probability": 85.0,
        "probability_notes": "Đã thống nhất giá trị hợp đồng",
        "description": "Gói CRM Pro On-Premise",
        "owner_id": 1,
        "status": "OPEN"
    }
]

for op in opps_data:
    ex = db.query(OpportunityModel).filter(OpportunityModel.id == op["id"]).first()
    if not ex:
        db.add(OpportunityModel(**op))
db.commit()
print("  ✓ Đã cập nhật 2 cơ hội bán hàng (Opportunities).")

quotes_data = [
    {
        "opportunity_id": 1,
        "quote_number": "BG-20261021-001",
        "title": "Báo giá Triển khai Phần mềm CRM Cloud - FPT Smart",
        "amount": 90000000.0,
        "customer_id": 1,
        "status": "SENT",
        "payment_terms": "Thanh toán 50% sau khi ký hợp đồng, 50% sau khi bàn giao",
        "valid_until": date(2026, 12, 31),
        "notes": "Báo giá đã bao gồm chiết khấu 10% cho khách hàng thân thiết."
    }
]

for q in quotes_data:
    ex = db.query(QuoteModel).filter(QuoteModel.quote_number == q["quote_number"]).first()
    if not ex:
        db.add(QuoteModel(**q))
db.commit()
print("  ✓ Đã cập nhật Báo giá mẫu.")

db.close()
print("\n=== HOÀN TẤT ĐỒNG BỘ DỮ LIỆU ĐẦY ĐỦ CẢ CLOUD & LOCAL! ===")
