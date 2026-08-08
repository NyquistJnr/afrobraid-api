from app.modules.chat.moderation import detect_violations


def test_clean_message_has_no_violations():
    assert detect_violations("Looking forward to my appointment, thank you!") == []


def test_detects_email():
    assert "email" in detect_violations("Reach me at jane.doe@example.com anytime")


def test_detects_phone_number():
    violations = detect_violations("You can call me on 555-867-5309 tonight")
    assert "phone_or_account_number" in violations


def test_detects_long_account_number_even_with_punctuation():
    violations = detect_violations("My IBAN is DE89 3704 0044 0532 0130 00")
    assert "phone_or_account_number" in violations


def test_short_digit_runs_are_not_flagged():
    # A time range like "5-6pm" or a small quantity shouldn't trip the filter.
    assert detect_violations("I'm free 5-6pm, bring 2 packs of hair") == []


def test_detects_url():
    assert "url" in detect_violations("Check my portfolio at myinstaportfolio.com for more")


def test_detects_messaging_app_keyword():
    violations = detect_violations("Just WhatsApp me instead")
    assert "messaging_app" in violations


def test_detects_off_platform_payment_keyword():
    violations = detect_violations("Send it via cashapp instead of the app")
    assert "off_platform_payment" in violations


def test_detects_off_platform_contact_keyword():
    violations = detect_violations("Let's talk off the app from now on")
    assert "off_platform_contact" in violations


def test_case_insensitive():
    assert detect_violations("CALL ME on my number") != []
