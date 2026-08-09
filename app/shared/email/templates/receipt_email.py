import html as html_lib
from datetime import datetime
from decimal import Decimal

from app.core.i18n import t
from app.modules.bookings.enums import PaymentPurpose

_PURPOSE_LABEL_KEYS = {
    PaymentPurpose.DEPOSIT: "email.receipt_payment_type_deposit",
    PaymentPurpose.FULL: "email.receipt_payment_type_full",
    PaymentPurpose.BALANCE: "email.receipt_payment_type_balance",
}


def render_payment_receipt_email(
    *,
    first_name: str,
    reference: str,
    style_name: str,
    braider_name: str,
    starts_at: datetime,
    purpose: PaymentPurpose,
    amount_paid: Decimal,
    total: Decimal,
    balance_amount: Decimal,
    currency: str,
    paid_at: datetime,
    locale: str,
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    safe_style = html_lib.escape(style_name)
    safe_braider = html_lib.escape(braider_name)
    when = starts_at.strftime("%A, %d %B %Y - %H:%M UTC")
    paid_when = paid_at.strftime("%d %B %Y - %H:%M UTC")

    payment_type = t(_PURPOSE_LABEL_KEYS[purpose], locale)

    subject = t("email.receipt_subject", locale, reference=reference)
    greeting = t("email.receipt_greeting", locale, first_name=safe_name)
    body = t(
        "email.receipt_body",
        locale,
        payment_type=payment_type,
        style_name=safe_style,
        braider_name=safe_braider,
        when=when,
    )
    payment_type_label = t("email.receipt_payment_type_label", locale)
    amount_paid_label = t("email.receipt_amount_paid_label", locale)
    date_label = t("email.receipt_date_label", locale)
    reference_label = t("email.receipt_reference_label", locale)
    total_label = t("email.receipt_total_label", locale)

    balance_row = ""
    if purpose == PaymentPurpose.DEPOSIT and balance_amount > 0:
        balance_due_label = t("email.receipt_balance_due_label", locale)
        balance_row = (
            f'<div>{balance_due_label}: '
            f'<strong style="color:#18181b;">{balance_amount} {currency}</strong></div>'
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
            <tr><td style="font-size:16px;color:#18181b;padding-bottom:8px;">{greeting}</td></tr>
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td style="font-size:13px;color:#71717a;border-top:1px solid #e4e4e7;border-bottom:1px solid #e4e4e7;padding:16px 0;">
                <div>{reference_label}: <strong style="color:#18181b;">{reference}</strong></div>
                <div>{payment_type_label}: <strong style="color:#18181b;">{payment_type}</strong></div>
                <div>{amount_paid_label}: <strong style="color:#18181b;">{amount_paid} {currency}</strong></div>
                <div>{date_label}: <strong style="color:#18181b;">{paid_when}</strong></div>
                {balance_row}
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
