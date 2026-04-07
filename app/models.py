from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RouterSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    host: str = Field(default="192.168.88.1")
    port: int = Field(default=8728)
    username: str = Field(default="admin")
    password: str = Field(default="")
    use_plaintext_login: bool = Field(default=True)
    api_enabled: bool = Field(default=False)


class VoucherProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    duration_seconds: int = Field(description="Total connected time per voucher (uptime limit)")
    price_egp: Optional[float] = None
    mikrotik_hotspot_profile: str = Field(
        default="default",
        description="Name of /ip hotspot profile on the router (rate limits, etc.)",
    )
    allowed_domains: str = Field(
        default="",
        description="Comma-separated domains to allow; used for exported firewall hints",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Voucher(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password: str = Field()
    profile_id: int = Field(foreign_key="voucherprofile.id")
    status: str = Field(default="created", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    synced_to_router: bool = Field(default=False)
    mikrotik_comment: str = Field(default="wifisystem")
