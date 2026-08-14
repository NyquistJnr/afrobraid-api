import html as html_lib
from datetime import datetime
from decimal import Decimal

from app.core.i18n import t


def render_booking_confirmed_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    starts_at: datetime,
    total: Decimal,
    currency: str,
    locale: str,
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    when = starts_at.strftime("%A, %d %B %Y - %H:%M UTC")

    subject = t("email.booking_confirmed_subject", locale, reference=reference)
    greeting = t("email.booking_confirmed_greeting", locale, first_name=safe_name)
    body = t(
        "email.booking_confirmed_body",
        locale,
        style_name=safe_style,
        braider_name=safe_braider,
        when=when,
    )
    total_label = t("email.booking_confirmed_total_label", locale)
    reference_label = t("email.booking_confirmed_reference_label", locale)

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;border-bottom:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
                <div>{total_label}: <strong style="color:#18181b;">{total} {currency}</strong></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html


def render_booking_rescheduled_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    old_starts_at: datetime,
    new_starts_at: datetime,
    locale: str,
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    old_when = old_starts_at.strftime("%A, %d %B %Y - %H:%M UTC")
    new_when = new_starts_at.strftime("%A, %d %B %Y - %H:%M UTC")

    subject = t("email.booking_rescheduled_subject", locale, reference=reference)
    greeting = t("email.booking_rescheduled_greeting", locale, first_name=safe_name)
    body = t(
        "email.booking_rescheduled_body",
        locale,
        style_name=safe_style,
        braider_name=safe_braider,
        old_when=old_when,
        new_when=new_when,
    )
    reference_label = t("email.booking_rescheduled_reference_label", locale)

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html


def render_balance_payment_failed_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    starts_at: datetime,
    amount: Decimal,
    currency: str,
    reason: str,
    needs_action: bool,
    pay_url: str,
    locale: str,
) -> tuple[str, str]:
    """`needs_action=True` (the `authentication_required` decline code)
    means the ladder will keep retrying but it will keep failing the same
    way until the customer confirms via `pay_url` themselves - so that
    variant reads as a required action, not a heads-up."""
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    safe_reason = html_lib.escape(reason)
    when = starts_at.strftime("%A, %d %B %Y - %H:%M UTC")

    subject = t("email.balance_payment_failed_subject", locale, reference=reference)
    greeting = t("email.balance_payment_failed_greeting", locale, first_name=safe_name)
    body_key = (
        "email.balance_payment_failed_body_auth_required"
        if needs_action
        else "email.balance_payment_failed_body_retry"
    )
    body = t(
        body_key,
        locale,
        amount=amount,
        currency=currency,
        style_name=safe_style,
        braider_name=safe_braider,
        when=when,
        reason=safe_reason,
    )
    cta_label = t("email.balance_payment_failed_cta_label", locale)
    reference_label = t("email.balance_payment_failed_reference_label", locale)

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="padding-bottom:24px;">
                <a href="{pay_url}" style="display:inline-block;background:#18181b;color:#ffffff;
                   font-size:14px;font-weight:600;text-decoration:none;padding:12px 20px;border-radius:8px;">
                  {cta_label}
                </a>
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html


def render_booking_cancelled_by_customer_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    starts_at: datetime,
    locale: str,
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    when = starts_at.strftime("%A, %d %B %Y - %H:%M UTC")

    subject = t("email.booking_cancelled_by_customer_subject", locale, reference=reference)
    greeting = t("email.booking_cancelled_by_customer_greeting", locale, first_name=safe_name)
    body = t(
        "email.booking_cancelled_by_customer_body",
        locale,
        style_name=safe_style,
        braider_name=safe_braider,
        when=when,
    )
    reference_label = t("email.booking_cancelled_by_customer_reference_label", locale)

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html


def render_booking_cancelled_by_braider_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    starts_at: datetime,
    refund_amount: Decimal,
    currency: str,
    locale: str,
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    when = starts_at.strftime("%A, %d %B %Y - %H:%M UTC")

    subject = t("email.booking_cancelled_by_braider_subject", locale, reference=reference)
    greeting = t("email.booking_cancelled_by_braider_greeting", locale, first_name=safe_name)
    body = t(
        "email.booking_cancelled_by_braider_body",
        locale,
        style_name=safe_style,
        braider_name=safe_braider,
        when=when,
    )
    reference_label = t("email.booking_cancelled_by_braider_reference_label", locale)
    refund_label = t("email.booking_cancelled_by_braider_refund_label", locale)

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
                <div>{refund_label}: <strong style="color:#18181b;">{refund_amount} {currency}</strong></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html


def render_dispute_admin_alert_email(
    *, reference: str, dispute_id: str, total: Decimal, currency: str
) -> tuple[str, str]:
    """Internal ops alert, not a customer/braider-facing template - always
    English regardless of who's on the admin team, unlike every other
    template in this module."""
    subject = t("email.dispute_admin_alert_subject", "en", reference=reference)
    body = t(
        "email.dispute_admin_alert_body",
        "en",
        reference=reference,
        dispute_id=dispute_id,
        total=total,
        currency=currency,
    )

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;">{body}</td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html


def render_booking_cancelled_no_payment_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    starts_at: datetime,
    locale: str,
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    when = starts_at.strftime("%A, %d %B %Y - %H:%M UTC")

    subject = t("email.booking_cancelled_no_payment_subject", locale, reference=reference)
    greeting = t("email.booking_cancelled_no_payment_greeting", locale, first_name=safe_name)
    body = t(
        "email.booking_cancelled_no_payment_body",
        locale,
        style_name=safe_style,
        braider_name=safe_braider,
        when=when,
    )
    reference_label = t("email.booking_cancelled_no_payment_reference_label", locale)

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html
