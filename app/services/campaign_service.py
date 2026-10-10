"""
Campaign Service for S4-03:
- Declare campaigns with budget, running time, channel
- Link Leads and Opportunities to campaigns
- Measure leads count, opportunities count, closed-won value, conversion rates, and ROI
"""

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.campaign import Campaign as CampaignModel
from app.services import auth_service
from app.services.opportunity_service import FAKE_OPPORTUNITIES

INITIAL_CAMPAIGNS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Hội thảo Chuyển đổi số 2026",
        "code": "CAMP-2026-EXPO",
        "budget": 50000000.0,
        "actual_cost": 45000000.0,
        "start_date": datetime(2026, 3, 1, 0, 0, 0),
        "end_date": datetime(2026, 3, 31, 23, 59, 59),
        "channel": "EVENT",
        "target_leads": 50,
        "expected_revenue": 200000000.0,
        "status": "ACTIVE",
        "description": "Hội thảo giới thiệu giải pháp quản lý khách hàng tại Trung tâm Hội nghị Quốc gia",
        "owner_id": 1,
        "team_id": 1,
        "created_at": datetime(2026, 2, 20, 8, 0, 0),
        "updated_at": None,
    },
    {
        "id": 2,
        "name": "Chiến dịch Facebook Ads Q1",
        "code": "CAMP-FB-Q1",
        "budget": 30000000.0,
        "actual_cost": 28000000.0,
        "start_date": datetime(2026, 1, 15, 0, 0, 0),
        "end_date": datetime(2026, 3, 31, 23, 59, 59),
        "channel": "FACEBOOK_ADS",
        "target_leads": 100,
        "expected_revenue": 150000000.0,
        "status": "ACTIVE",
        "description": "Quảng cáo tiếp cận doanh nghiệp vừa và nhỏ",
        "owner_id": 2,
        "team_id": 1,
        "created_at": datetime(2026, 1, 10, 8, 0, 0),
        "updated_at": None,
    },
]

FAKE_CAMPAIGNS: List[Dict[str, Any]] = copy.deepcopy(INITIAL_CAMPAIGNS)


def reset_fake_campaigns() -> None:
    global FAKE_CAMPAIGNS
    FAKE_CAMPAIGNS = copy.deepcopy(INITIAL_CAMPAIGNS)

    try:
        db: Session = SessionLocal()
        try:
            db.query(CampaignModel).delete()
            for c in INITIAL_CAMPAIGNS:
                m = CampaignModel(
                    id=c["id"],
                    name=c["name"],
                    code=c["code"],
                    budget=c["budget"],
                    actual_cost=c.get("actual_cost", 0.0),
                    start_date=c["start_date"],
                    end_date=c.get("end_date"),
                    channel=c["channel"],
                    target_leads=c.get("target_leads", 0),
                    expected_revenue=c.get("expected_revenue", 0.0),
                    status=c.get("status", "ACTIVE"),
                    description=c.get("description"),
                    owner_id=c.get("owner_id", 1),
                    team_id=c.get("team_id"),
                    created_at=c.get("created_at"),
                )
                db.add(m)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _enrich_campaign_display(c: dict) -> dict:
    enriched = dict(c)
    owner = auth_service.get_user_by_id(enriched.get("owner_id"))
    enriched["owner_name"] = owner.get("full_name") if owner else None
    return enriched


def create_campaign(data: dict, current_user: dict) -> dict:
    """AC S4-03: Khai báo chiến dịch với ngân sách, thời gian chạy, kênh."""
    code = str(data["code"]).strip().upper()
    if any(c["code"].upper() == code for c in FAKE_CAMPAIGNS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã chiến dịch '{code}' đã tồn tại",
        )

    new_id = (max((c["id"] for c in FAKE_CAMPAIGNS), default=0) + 1) if FAKE_CAMPAIGNS else 1
    new_camp = {
        "id": new_id,
        "name": str(data["name"]).strip(),
        "code": code,
        "budget": float(data["budget"]),
        "actual_cost": float(data.get("actual_cost", 0.0)),
        "start_date": data["start_date"],
        "end_date": data.get("end_date"),
        "channel": str(data["channel"]).strip(),
        "target_leads": int(data.get("target_leads", 0)),
        "expected_revenue": float(data.get("expected_revenue", 0.0)),
        "status": data.get("status", "ACTIVE"),
        "description": data.get("description"),
        "owner_id": data.get("owner_id") or current_user.get("id", 1),
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    FAKE_CAMPAIGNS.append(new_camp)

    # Lưu DB
    try:
        db: Session = SessionLocal()
        try:
            m = CampaignModel(
                id=new_camp["id"],
                name=new_camp["name"],
                code=new_camp["code"],
                budget=new_camp["budget"],
                actual_cost=new_camp["actual_cost"],
                start_date=new_camp["start_date"],
                end_date=new_camp["end_date"],
                channel=new_camp["channel"],
                target_leads=new_camp["target_leads"],
                expected_revenue=new_camp["expected_revenue"],
                status=new_camp["status"],
                description=new_camp["description"],
                owner_id=new_camp["owner_id"],
                team_id=new_camp["team_id"],
            )
            db.add(m)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return _enrich_campaign_display(new_camp)


def get_campaign_by_id(campaign_id: int) -> Optional[dict]:
    for c in FAKE_CAMPAIGNS:
        if c["id"] == campaign_id:
            return _enrich_campaign_display(c)
    return None


def get_campaign_by_code(code: str) -> Optional[dict]:
    norm_code = code.strip().upper()
    for c in FAKE_CAMPAIGNS:
        if c["code"].strip().upper() == norm_code:
            return _enrich_campaign_display(c)
    return None


def list_campaigns(
    status_filter: Optional[str] = None,
    channel_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    results = list(FAKE_CAMPAIGNS)

    if status_filter:
        s_val = status_filter.upper().strip()
        results = [c for c in results if c.get("status") == s_val]

    if channel_filter:
        ch_val = channel_filter.upper().strip()
        results = [c for c in results if c.get("channel", "").upper() == ch_val]

    if search:
        q = search.lower().strip()
        results = [
            c for c in results
            if q in c.get("name", "").lower()
            or q in c.get("code", "").lower()
            or q in (c.get("description") or "").lower()
        ]

    results.sort(key=lambda x: x["id"], reverse=True)
    return [_enrich_campaign_display(c) for c in results]


def update_campaign(campaign_id: int, data: dict, current_user: dict) -> dict:
    camp = None
    for c in FAKE_CAMPAIGNS:
        if c["id"] == campaign_id:
            camp = c
            break

    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy chiến dịch ID {campaign_id}",
        )

    if "code" in data and data["code"] is not None:
        new_code = str(data["code"]).strip().upper()
        if any(c["id"] != campaign_id and c["code"].upper() == new_code for c in FAKE_CAMPAIGNS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã chiến dịch '{new_code}' đã được sử dụng",
            )
        camp["code"] = new_code

    for k, v in data.items():
        if k not in ("id", "code") and v is not None:
            camp[k] = v

    camp["updated_at"] = datetime.now(timezone.utc)

    # Lưu DB
    try:
        db: Session = SessionLocal()
        try:
            m = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
            if m:
                for k, v in camp.items():
                    if hasattr(m, k) and k != "id":
                        setattr(m, k, v)
                db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return _enrich_campaign_display(camp)


def delete_campaign(campaign_id: int) -> bool:
    global FAKE_CAMPAIGNS
    initial_len = len(FAKE_CAMPAIGNS)
    FAKE_CAMPAIGNS = [c for c in FAKE_CAMPAIGNS if c["id"] != campaign_id]

    try:
        db: Session = SessionLocal()
        try:
            m = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
            if m:
                db.delete(m)
                db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return len(FAKE_CAMPAIGNS) < initial_len


# ==============================================================================
# S4-03: Campaign Performance Measurement (Metrics & ROI)
# ==============================================================================

def get_campaign_leads(campaign_id: int) -> List[dict]:
    """AC S4-03: Lấy danh sách Lead sinh ra từ chiến dịch."""
    from app.services.lead_service import lead_to_dict
    from app.models.lead import Lead
    try:
        db: Session = SessionLocal()
        try:
            leads = db.query(Lead).filter(
                Lead.campaign_id == campaign_id,
                Lead.status != "MERGED",
            ).all()
            return [lead_to_dict(l) for l in leads]
        finally:
            db.close()
    except Exception:
        return []


def get_campaign_metrics(campaign_id: int) -> dict:
    """
    AC S4-03: Xem được số lead, số cơ hội và giá trị đã chốt của từng chiến dịch.
    Đo được chiến dịch nào thực sự ra doanh thu chứ không chỉ ra nhiều lead.
    """
    camp = get_campaign_by_id(campaign_id)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy chiến dịch ID {campaign_id}",
        )

    # 1. Số lead liên kết với chiến dịch (loại trừ lead MERGED nếu có)
    from app.models.lead import Lead
    db_leads = []
    try:
        db: Session = SessionLocal()
        try:
            db_leads = db.query(Lead).filter(
                Lead.campaign_id == campaign_id,
                Lead.status != "MERGED",
            ).all()
        finally:
            db.close()
    except Exception:
        db_leads = []

    total_leads = len(db_leads)

    # 2. Số cơ hội liên kết với chiến dịch
    opps_in_camp = [
        o for o in FAKE_OPPORTUNITIES
        if o.get("campaign_id") == campaign_id
    ]
    total_opps = len(opps_in_camp)

    # 3. Cơ hội đã chốt (CLOSED_WON / WON)
    won_opps = [
        o for o in opps_in_camp
        if str(o.get("stage", "")).upper() in ("CLOSED_WON", "WON")
    ]
    won_opportunities = len(won_opps)

    # 4. Giá trị đã chốt (closed_won_value)
    closed_won_value = sum(float(o.get("value", 0.0)) for o in won_opps)

    # 5. Tỷ lệ chuyển đổi
    conv_lead_to_opp = round((total_opps / total_leads * 100), 2) if total_leads > 0 else 0.0
    conv_lead_to_won = round((won_opportunities / total_leads * 100), 2) if total_leads > 0 else 0.0

    # 6. ROI = ((Doanh thu đã chốt - Chi phí) / Chi phí) * 100
    base_cost = camp["actual_cost"] if camp.get("actual_cost") and camp["actual_cost"] > 0 else camp["budget"]
    roi = round(((closed_won_value - base_cost) / base_cost * 100), 2) if base_cost > 0 else 0.0

    return {
        "campaign_id": camp["id"],
        "campaign_name": camp["name"],
        "campaign_code": camp["code"],
        "channel": camp["channel"],
        "budget": camp["budget"],
        "actual_cost": camp.get("actual_cost", 0.0),
        "target_leads": camp.get("target_leads", 0),
        "total_leads": total_leads,
        "total_opportunities": total_opps,
        "won_opportunities": won_opportunities,
        "closed_won_value": closed_won_value,
        "conversion_rate_lead_to_opp": conv_lead_to_opp,
        "conversion_rate_lead_to_won": conv_lead_to_won,
        "roi": roi,
    }


def get_campaigns_summary_report() -> dict:
    """AC S4-03: Báo cáo tổng hợp hiệu quả của tất cả các chiến dịch."""
    all_metrics = [get_campaign_metrics(c["id"]) for c in FAKE_CAMPAIGNS]

    total_budget = sum(m["budget"] for m in all_metrics)
    total_actual_cost = sum(m["actual_cost"] for m in all_metrics)
    total_leads = sum(m["total_leads"] for m in all_metrics)
    total_opps = sum(m["total_opportunities"] for m in all_metrics)
    total_won = sum(m["won_opportunities"] for m in all_metrics)
    total_closed_won = sum(m["closed_won_value"] for m in all_metrics)

    base_cost = total_actual_cost if total_actual_cost > 0 else total_budget
    avg_roi = round(((total_closed_won - base_cost) / base_cost * 100), 2) if base_cost > 0 else 0.0

    return {
        "total_campaigns": len(all_metrics),
        "total_budget": total_budget,
        "total_actual_cost": total_actual_cost,
        "total_leads": total_leads,
        "total_opportunities": total_opps,
        "total_won_opportunities": total_won,
        "total_closed_won_value": total_closed_won,
        "average_roi": avg_roi,
        "campaign_metrics": all_metrics,
    }
