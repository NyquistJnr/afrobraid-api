from types import SimpleNamespace

from app.shared import links


def test_builds_app_specific_frontend_urls(monkeypatch):
    monkeypatch.setattr(
        links,
        "settings",
        SimpleNamespace(
            frontend_url="https://fallback.example.com/",
            customer_frontend_url="https://customer.example.com/",
            braider_frontend_url="https://braider.example.com",
            admin_frontend_url="https://admin.example.com/",
        ),
    )

    assert (
        links.build_customer_frontend_url(locale="fr", path="/bookings/booking-1")
        == "https://customer.example.com/fr/bookings/booking-1"
    )
    assert (
        links.build_braider_frontend_url(locale="de", path="chat/thread-1")
        == "https://braider.example.com/de/chat/thread-1"
    )
    assert (
        links.build_admin_frontend_url(path="/admin/invite/accept?token=raw-token")
        == "https://admin.example.com/admin/invite/accept?token=raw-token"
    )


def test_app_specific_frontend_urls_fall_back_to_frontend_url(monkeypatch):
    monkeypatch.setattr(
        links,
        "settings",
        SimpleNamespace(
            frontend_url="https://fallback.example.com",
            customer_frontend_url="",
            braider_frontend_url="",
            admin_frontend_url="",
        ),
    )

    assert (
        links.build_customer_frontend_url(locale="en", path="bookings/booking-1")
        == "https://fallback.example.com/en/bookings/booking-1"
    )
    assert (
        links.build_braider_frontend_url(locale="en", path="bookings/booking-1")
        == "https://fallback.example.com/en/bookings/booking-1"
    )
    assert (
        links.build_admin_frontend_url(path="admin/invite/accept?token=raw-token")
        == "https://fallback.example.com/admin/invite/accept?token=raw-token"
    )
