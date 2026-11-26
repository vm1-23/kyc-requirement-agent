from kyc_re.speakers import split_speakers


def labels(text):
    return [(s.label, s.role) for s in split_speakers(text)]


def test_one_line_per_person_with_designations():
    out = split_speakers(
        "Priya (Product Owner): Customers must open accounts on the mobile app.\n"
        "Arjun, Chief Compliance Officer: Every applicant must be screened against sanctions lists.\n"
        "Meera - CISO said that biometric data must be encrypted at rest.\n"
        "Priya (Product Owner): We also need Hindi support.")
    assert [(s.label, s.role, s.turns) for s in out] == [
        ("Priya (Product Owner)", "product_owner", 2),
        ("Arjun (Chief Compliance Officer)", "compliance", 1),
        ("Meera (CISO)", "security", 1)]
    assert "Hindi" in out[0].text and out[2].text.startswith("biometric")


def test_single_paragraph_with_inline_attribution():
    assert labels("In the workshop, Priya (Product Owner): we want onboarding under 5 minutes. "
                  "Arjun (CCO) said that all customers must be screened. "
                  "We spoke to Lena, Head of Sales: merchants must go live in 24 hours. "
                  "Then Marco (Platform team) said the API must respond within 800 ms.") == [
        ("Priya (Product Owner)", "product_owner"), ("Arjun (CCO)", "compliance"),
        ("Lena (Head of Sales)", "product_owner"), ("Marco (Platform team)", "architect")]


def test_interviewer_questions_stay_with_the_answer_and_labels_are_not_people():
    out = split_speakers("Interviewer: How long do we keep records?\nDana (BSA Officer): Records must be kept 5 years.\n"
                         "Note: follow up on Friday.\nSummary: done.")
    assert [s.label for s in out] == ["Dana (BSA Officer)"]
    assert out[0].text.startswith("Interviewer: How long") and "Note: follow up" in out[0].text


def test_no_names_gives_one_unattributed_input_and_role_from_bare_titles():
    out = split_speakers("The system must screen every customer. Retention must be 5 years: no exceptions.")
    assert len(out) == 1 and not out[0].attributed and out[0].role is None
    assert labels("CISO: Admin access must use MFA.\nCustomer: I want to finish in one go.") == [
        ("CISO", "security"), ("Customer", "customer")]
    frm = split_speakers("From: Arjun Mehta <a@b.c>\nSubject: KYC\nThe system must screen everyone.")
    assert [s.label for s in frm] == ["Arjun Mehta"]


def test_sentence_end_is_not_glued_onto_the_next_name():
    out = split_speakers("Meera - CISO said that all staff access must use MFA.\n"
                         "Rahul (KYC Operations Lead): Analysts must review referrals within 4 hours. "
                         "J. Smith (Head of Risk): Limits must be reviewed yearly.")
    assert [s.label for s in out] == ["Meera (CISO)", "Rahul (KYC Operations Lead)", "J. Smith (Head of Risk)"]
    assert out[0].text.endswith("must use MFA.")


def test_initial_only_counts_at_a_sentence_start():
    assert [s.label for s in split_speakers("Priya (Product Owner): we need X. Arjun, CCO: all must be screened.")] == [
        "Priya (Product Owner)", "Arjun (CCO)"]
