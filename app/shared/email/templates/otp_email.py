import html as html_lib

from app.core.i18n import t


def render_verification_email(
    *, first_name: str, code: str, minutes: int, locale: str
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    subject = t("email.verify_subject", locale)
    html = _otp_html(
        greeting=t("email.verify_greeting", locale, first_name=safe_name),
        body=t("email.verify_body", locale, minutes=minutes),
        code_label=t("email.verify_code_label", locale),
        code=code,
        ignore_note=t("email.verify_ignore_note", locale),
    )
    return subject, html


def render_password_reset_email(
    *, first_name: str, code: str, minutes: int, locale: str
) -> tuple[str, str]:
    safe_name = html_lib.escape(first_name)
    subject = t("email.reset_subject", locale)
    html = _otp_html(
        greeting=t("email.reset_greeting", locale, first_name=safe_name),
        body=t("email.reset_body", locale, minutes=minutes),
        code_label=t("email.reset_code_label", locale),
        code=code,
        ignore_note=t("email.reset_ignore_note", locale),
    )
    return subject, html


def _otp_html(*, greeting: str, body: str, code_label: str, code: str, ignore_note: str) -> str:
    return f"""\
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
              <td align="center" style="padding-bottom:24px;">
                <div style="font-size:12px;color:#71717a;text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;">{code_label}</div>
                <div style="font-size:36px;font-weight:700;letter-spacing:0.2em;color:#18181b;">{code}</div>
              </td>
            </tr>
            <tr><td style="font-size:12px;color:#a1a1aa;border-top:1px solid #e4e4e7;padding-top:16px;">{ignore_note}</td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
