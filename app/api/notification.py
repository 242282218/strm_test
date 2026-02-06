from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.notification import NotificationChannel, NotificationRule, NotificationLog
from app.services.notification_service import get_notification_service, NotificationService, NotificationType, NotificationMessage
from app.core.dependencies import require_api_key

router = APIRouter(prefix="/api/notification", tags=["notification"])

# ==================== Pydantic Models ====================

class ChannelConfig(BaseModel):
    """渠道配置"""
    model_config = ConfigDict(extra="allow")

    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    device_key: Optional[str] = None
    send_key: Optional[str] = None
    webhook_url: Optional[str] = None

class ChannelCreate(BaseModel):
    channel_type: str = Field(..., pattern="^(telegram|bark|serverchan|webhook)$")
    channel_name: str
    config: dict

class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    config: Optional[dict] = None
    is_enabled: Optional[bool] = None

class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_type: str
    channel_name: str
    is_enabled: bool
    config: dict

class RuleCreate(BaseModel):
    channel_id: int
    event_type: str
    keywords: Optional[str] = None

class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    event_type: str
    keywords: Optional[str]
    is_enabled: bool

class LogResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            # simple string conversion
        },
    )

    id: int
    channel_id: Optional[int]
    channel_name: Optional[str]
    event_type: str
    title: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: str # DateTime needed specialized handling or just default str

# ==================== Channels ====================

@router.post("/channels", response_model=ChannelResponse)
def create_channel(
    channel: ChannelCreate,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    """创建通知渠道"""
    db_channel = NotificationChannel(
        channel_type=channel.channel_type,
        channel_name=channel.channel_name,
        config=channel.config
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    return db_channel

@router.get("/channels", response_model=List[ChannelResponse])
def list_channels(db: Session = Depends(get_db)):
    """获取所有渠道"""
    return db.query(NotificationChannel).all()

@router.put("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int, 
    channel: ChannelUpdate, 
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service)
):
    """更新渠道"""
    db_channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    if channel.channel_name is not None:
        db_channel.channel_name = channel.channel_name
    if channel.config is not None:
        db_channel.config = channel.config
    if channel.is_enabled is not None:
        db_channel.is_enabled = channel.is_enabled
        
    db.commit()
    db.refresh(db_channel)
    
    # 只要有更新，就重载服务配置
    await service.reload()
    
    return db_channel

@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int, 
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service)
):
    """删除渠道"""
    db_channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    db.delete(db_channel)
    db.commit()
    
    await service.reload()
    return {"status": "ok"}

@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: int, 
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service)
):
    """测试渠道发送"""
    db_channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not db_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # 手动创建 Handler 并发送
    handler = service._create_handler(db_channel)
    if not handler:
        raise HTTPException(status_code=400, detail="Failed to instantiate handler")
        
    msg = NotificationMessage(
        type=NotificationType.SYSTEM_ALERT,
        title="测试通知",
        content="这是一条测试消息，如果您收到它，说明配置正确。",
    )
    
    success = await handler.send(msg)
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test message")

# ==================== Rules ====================

@router.post("/rules", response_model=RuleResponse)
async def create_rule(
    rule: RuleCreate, 
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service)
):
    """创建通知规则"""
    db_rule = NotificationRule(
        channel_id=rule.channel_id,
        event_type=rule.event_type,
        keywords=rule.keywords
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    await service.reload()
    return db_rule

@router.get("/rules", response_model=List[RuleResponse])
def list_rules(db: Session = Depends(get_db)):
    """获取所有规则"""
    return db.query(NotificationRule).all()

@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int, 
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
    service: NotificationService = Depends(get_notification_service)
):
    """删除规则"""
    db_rule = db.query(NotificationRule).filter(NotificationRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    db.delete(db_rule)
    db.commit()
    
    await service.reload()
    return {"status": "ok"}

# ==================== Logs ====================

@router.get("/logs", response_model=List[LogResponse])
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    """获取通知日志"""
    return db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit).all()
