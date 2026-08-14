"""Localized (en/de/fr) HTML receipt rendering. Rendered once at issuance
and stored immutably on `Receipt.html` - see that model's docstring for
why. Deliberately plain, printable HTML (no external assets, no JS) since
this is a document, not an app page.
"""

import html as html_lib
from datetime import datetime
from decimal import Decimal

from app.core.config import get_settings
from app.core.i18n import localize_field, t
from app.modules.bookings.enums import BraiderVatStatus, ReceiptType
from app.modules.bookings.models import BookingItem

settings = get_settings()


def _line_rows(items: list[BookingItem], *, locale: str, currency: str) -> str:
    rows = []
    for item in items:
        name = localize_field(item, "name", locale) or item.name_en or ""
        rows.append(
            f'<tr><td style="padding:6px 0;color:#3f3f46;">{html_lib.escape(name)}</td>'
            f'<td style="padding:6px 0;text-align:right;color:#3f3f46;">'
            f"{item.line_amount} {currency}</td></tr>"
        )
    return "".join(rows)


def render_receipt_html(
    *,
    receipt_type: ReceiptType,
    receipt_number: str,
    issued_at: datetime,
    locale: str,
    reference: str,
    customer_name: str,
    customer_email: str,
    braider_name: str,
    braider_vat_status: BraiderVatStatus,
    braider_vat_number: str | None,
    items: list[BookingItem],
    amount_total: Decimal,
    prior_receipts_total: Decimal,
    prior_receipt_number: str | None,
    currency: str,
    credit_note_for_receipt_number: str | None,
) -> str:
    is_credit_note = receipt_type == ReceiptType.CREDIT_NOTE
    title = t(
        "receipt.title_credit_note" if is_credit_note else "receipt.title_invoice", locale
    )
    number_label = t("receipt.number_label", locale)
    date_label = t("receipt.date_label", locale)
    reference_label = t("receipt.reference_label", locale)
    seller_label = t("receipt.seller_label", locale)
    buyer_label = t("receipt.buyer_label", locale)
    provider_label = t("receipt.provider_label", locale)
    vat_note = (
        t("receipt.vat_status_small_business", locale)
        if braider_vat_status == BraiderVatStatus.SMALL_BUSINESS
        else (
            t("receipt.vat_status_unconfirmed", locale)
            if braider_vat_status == BraiderVatStatus.UNKNOWN
            else ""
        )
    )
    vat_number_line = (
        f"<div>{t('receipt.vat_number_label', locale)}: {html_lib.escape(braider_vat_number)}</div>"
        if braider_vat_number
        else ""
    )

    rows_html = _line_rows(items, locale=locale, currency=currency)

    prior_row = ""
    amount_label = t("receipt.amount_credited_label" if is_credit_note else "receipt.amount_due_label", locale)
    if not is_credit_note and prior_receipts_total > 0:
        prior_note = t(
            "receipt.prior_receipts_note", locale, prior_receipt_number=prior_receipt_number or ""
        )
        prior_row = (
            f'<tr><td style="padding:6px 0;color:#71717a;">{html_lib.escape(prior_note)}</td>'
            f'<td style="padding:6px 0;text-align:right;color:#71717a;">'
            f"-{prior_receipts_total} {currency}</td></tr>"
        )

    credit_note_ref_row = ""
    if is_credit_note and credit_note_for_receipt_number:
        credit_note_ref_label = t("receipt.credit_note_reference_label", locale)
        credit_note_ref_row = (
            f"<div>{credit_note_ref_label}: "
            f"<strong>{html_lib.escape(credit_note_for_receipt_number)}</strong></div>"
        )

    when = issued_at.strftime("%d %B %Y")
    display_amount = f"-{amount_total}" if is_credit_note else f"{amount_total}"

    return f"""\
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>{html_lib.escape(title)} {html_lib.escape(receipt_number)}</title></head>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:40px;">
            <tr>
              <td style="font-size:22px;font-weight:700;color:#18181b;padding-bottom:4px;">
                {html_lib.escape(title)}
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#71717a;padding-bottom:24px;">
                <div>{number_label}: <strong style="color:#18181b;">{html_lib.escape(receipt_number)}</strong></div>
                <div>{date_label}: {when}</div>
                <div>{reference_label}: {html_lib.escape(reference)}</div>
                {credit_note_ref_row}
              </td>
            </tr>
            <tr>
              <td style="padding-bottom:24px;border-top:1px solid #e4e4e7;padding-top:16px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td width="50%" style="font-size:13px;color:#3f3f46;vertical-align:top;">
                      <div style="color:#71717a;padding-bottom:4px;">{seller_label}</div>
                      <div>{html_lib.escape(settings.company_legal_name)}</div>
                      <div>{html_lib.escape(settings.company_address)}</div>
                      <div>{t('receipt.vat_number_label', locale)}: {html_lib.escape(settings.company_vat_number)}</div>
                    </td>
                    <td width="50%" style="font-size:13px;color:#3f3f46;vertical-align:top;">
                      <div style="color:#71717a;padding-bottom:4px;">{buyer_label}</div>
                      <div>{html_lib.escape(customer_name)}</div>
                      <div>{html_lib.escape(customer_email)}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;color:#3f3f46;padding-bottom:16px;">
                <div style="color:#71717a;padding-bottom:4px;">{provider_label}</div>
                <div>{html_lib.escape(braider_name)}</div>
                {vat_number_line}
                {f'<div style="color:#a16207;">{html_lib.escape(vat_note)}</div>' if vat_note else ''}
              </td>
            </tr>
            <tr>
              <td>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="font-size:13px;border-top:1px solid #e4e4e7;padding-top:12px;">
                  {rows_html}
                  {prior_row}
                  <tr>
                    <td style="padding-top:12px;border-top:1px solid #e4e4e7;font-weight:700;color:#18181b;">
                      {amount_label}
                    </td>
                    <td style="padding-top:12px;border-top:1px solid #e4e4e7;text-align:right;font-weight:700;color:#18181b;">
                      {display_amount} {currency}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
