"""Push hotspot users to MikroTik with limit-uptime (cumulative connected time)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models import RouterSettings, Voucher, VoucherProfile


def seconds_to_routeros_uptime(seconds: int) -> str:
    """RouterOS accepts suffixes s, m, h, d, w."""
    if seconds <= 0:
        return "1s"
    if seconds % 604800 == 0:
        return f"{seconds // 604800}w"
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


@dataclass
class MikrotikResult:
    ok: bool
    message: str


def sync_voucher(
    settings: RouterSettings,
    voucher: Voucher,
    profile: VoucherProfile,
) -> MikrotikResult:
    try:
        import routeros_api
    except ImportError:
        return MikrotikResult(False, "routeros-api package not installed")

    pool = routeros_api.RouterOsApiPool(
        settings.host,
        username=settings.username,
        password=settings.password,
        port=settings.port,
        plaintext_login=settings.use_plaintext_login,
    )
    try:
        api = pool.get_api()
        users = api.get_resource("/ip/hotspot/user")
        limit_uptime = seconds_to_routeros_uptime(profile.duration_seconds)
        users.add(
            name=voucher.username,
            password=voucher.password,
            profile=profile.mikrotik_hotspot_profile,
            limit_uptime=limit_uptime,
            comment=voucher.mikrotik_comment or "wifisystem",
        )
        return MikrotikResult(True, f"Added {voucher.username} ({limit_uptime} uptime limit)")
    except Exception as exc:
        return MikrotikResult(False, str(exc))
    finally:
        try:
            pool.disconnect()
        except Exception:
            pass


def test_connection(settings: RouterSettings) -> MikrotikResult:
    try:
        import routeros_api
    except ImportError:
        return MikrotikResult(False, "routeros-api package not installed")

    pool = routeros_api.RouterOsApiPool(
        settings.host,
        username=settings.username,
        password=settings.password,
        port=settings.port,
        plaintext_login=settings.use_plaintext_login,
    )
    try:
        api = pool.get_api()
        ident = api.get_resource("/system/identity").get()
        name = ident[0].get("name", "router") if ident else "router"
        return MikrotikResult(True, f"Connected: {name}")
    except Exception as exc:
        return MikrotikResult(False, str(exc))
    finally:
        try:
            pool.disconnect()
        except Exception:
            pass


def remove_hotspot_user(settings: RouterSettings, username: str) -> MikrotikResult:
    try:
        import routeros_api
    except ImportError:
        return MikrotikResult(False, "routeros-api package not installed")

    pool = routeros_api.RouterOsApiPool(
        settings.host,
        username=settings.username,
        password=settings.password,
        port=settings.port,
        plaintext_login=settings.use_plaintext_login,
    )
    try:
        api = pool.get_api()
        users = api.get_resource("/ip/hotspot/user")
        rows = [r for r in users.get() if r.get("name") == username]
        if not rows:
            return MikrotikResult(True, "User not on router (already removed)")
        users.remove(id=rows[0]["id"])
        return MikrotikResult(True, f"Removed {username}")
    except Exception as exc:
        return MikrotikResult(False, str(exc))
    finally:
        try:
            pool.disconnect()
        except Exception:
            pass
