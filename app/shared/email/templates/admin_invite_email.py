import html as html_lib

from app.core.i18n import t


def render_admin_invite_email(*, accept_url: str, minutes: int, locale: str) -> tuple[str, str]:
    hours = max(minutes // 60, 1)
    subject = t("email.admin_invite_subject", locale)
    safe_url = html_lib.escape(accept_url)
    body = t("email.admin_invite_body", locale, hours=hours)
    cta_label = t("email.admin_invite_cta", locale)
    ignore_note = t("email.admin_invite_ignore_note", locale)
    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;padding:32px;">
            <tr><td style="font-size:14px;color:#52525b;line-height:1.5;padding-bottom:24px;">{body}</td></tr>
            <tr>
              <td align="center" style="padding-bottom:24px;">
                <a href="{safe_url}" style="display:inline-block;background:#18181b;color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;">{cta_label}</a>
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
    return subject, html
