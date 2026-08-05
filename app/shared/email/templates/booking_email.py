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
