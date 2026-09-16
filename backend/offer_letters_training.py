"""
Generate synthetic offer-letter training data.
Produces 200 rows: 100 scam (label=1), 100 legit (label=0).
Run once: python offer_letters_training.py
Output: offer_letters_dataset.csv
"""

import csv
import random

random.seed(42)

# ── Scam offer letter templates ───────────────────────────────────────────────
SCAM_TEMPLATES = [
    "Dear Candidate, Congratulations! You have been selected for the post of {role} at {co}. "
    "Your salary will be Rs. {sal} per month. To confirm your appointment, kindly pay a registration fee of Rs. {fee} "
    "to our HR department within {hours} hours. Contact us immediately at {email}.",

    "Dear Applicant, We are glad to inform you that you have been selected without interview for {role} at {co}. "
    "Guaranteed job with salary {sal} per month. Please pay a security deposit of Rs. {fee} before joining. "
    "This offer expires in {hours} hours. Respond today at {email}.",

    "Dear Candidate, Instant joining opportunity! {co} is hiring for {role}. "
    "Salary: Rs. {sal} per month. To activate your offer, transfer the amount of Rs. {fee} as onboarding fee. "
    "Act now - limited positions available. WhatsApp only: {phone}. Contact {email} immediately.",

    "Congratulations! You are selected for {role} position at {co}. "
    "No interview required. Start immediately. Please pay training fee of Rs. {fee} to confirm. "
    "Salary Rs. {sal}/month guaranteed. Respond within {hours} hours at {email}.",

    "Dear Job Seeker, {co} has selected you for the role of {role}. "
    "Annual CTC: Rs. {sal}. To proceed with your joining formalities, pay the processing fee of Rs. {fee} urgently. "
    "This is a final deadline offer. Contact: {email}. Respond today itself.",

    "URGENT HIRING - {co} requires {role} immediately. Selected candidates earn Rs. {sal}/month. "
    "Pay registration amount Rs. {fee} to confirm your seat. Limited time offer. "
    "Kindly pay and confirm within {hours} hours. Contact {email} or telegram {phone}.",

    "Dear Applicant, Your resume was shortlisted for {role} at {co}. "
    "Salary package Rs. {sal} per annum. Kindly deposit Rs. {fee} as refundable security deposit to our account. "
    "Offer valid for next {hours} hours only. Pay immediately to {email}.",

    "Congratulations! {co} is pleased to offer you {role} with salary Rs. {sal} per month. "
    "As per company policy, all new hires must pay a laptop fee of Rs. {fee} before joining. "
    "Pay before {hours} hours or offer will be cancelled. Contact {email}.",

    "Dear Candidate, You have been selected for {role} at {co} through our recruitment drive. "
    "Salary: Rs. {sal} CTC per annum. Please transfer the advance fee of Rs. {fee} to confirm your appointment letter. "
    "Contact us at {email}. This offer is valid today itself only.",

    "SELECTED! {co} wants you as {role}. Salary Rs. {sal}/month. "
    "To receive your offer letter, pay Rs. {fee} screening fee. No interview needed. "
    "Respond within {hours} hours. Pay and confirm at {email}. Whatsapp only.",
]

# ── Legit offer letter templates ──────────────────────────────────────────────
LEGIT_TEMPLATES = [
    "Dear {name}, We are pleased to offer you the position of {role} at {co}, {city}. "
    "Your annual compensation will be INR {sal} per annum, subject to standard payroll deductions and company policy. "
    "Your tentative date of joining is {date}. Please review the attached offer details and confirm your acceptance by {deadline}. "
    "For any questions, contact us at {email}. Best regards, {hr}, HR Team, {co}.",

    "Dear {name}, On behalf of {co}, I am delighted to extend this offer of employment for the role of {role}. "
    "Your compensation will be INR {sal} per annum as per our salary structure, subject to payroll deductions. "
    "Your reporting manager will be {manager} and your joining date is {date}. "
    "Please sign and return this letter by {deadline}. Human resources contact: {email}. Regards, Talent Acquisition, {co}.",

    "Dear {name}, Following your successful interview process, we are pleased to offer you the position of {role} "
    "at {co}, {city} with a CTC of INR {sal} per annum. This offer is contingent upon satisfactory background verification. "
    "Joining date: {date}. Please confirm by {deadline}. For any questions, reach our HR at {email}. "
    "Sincerely, {hr}, HR Manager, {co}.",

    "Dear {name}, {co} is happy to confirm your selection as {role} at our {city} office. "
    "The annual compensation package is INR {sal}, subject to company policy and payroll deductions. "
    "Your employment is contingent upon successful completion of background checks. "
    "Joining date: {date}. Confirm acceptance by {deadline}. Contact: {email}. Best regards, Recruitment Team, {co}.",

    "Dear {name}, We are pleased to inform you that you have been selected for the position of {role} at {co}. "
    "Your annual salary will be INR {sal} as per the offer letter enclosed herewith. "
    "Reporting manager: {manager}. Date of joining: {date}. "
    "Kindly acknowledge by {deadline}. HR contact: {email}. Regards, {hr}, Human Resources, {co}.",

    "Dear {name}, This is to formally offer you the position of {role} at {co}, {city}, effective {date}. "
    "Total annual compensation: INR {sal} subject to standard deductions. "
    "Benefits include health insurance, PF, and gratuity as per company policy. "
    "Please review and sign the enclosed documents by {deadline}. For queries: {email}. "
    "Warm regards, {hr}, Talent Acquisition, {co}.",

    "Dear {name}, Following your interview on the date mentioned above, we are glad to offer you "
    "the role of {role} at {co} with an annual CTC of INR {sal}. "
    "Your tentative joining date is {date}. This offer of employment is subject to company policy. "
    "Please confirm your acceptance by signing and returning this letter by {deadline}. "
    "For any questions please contact {email}. Sincerely, {hr}, HR Department, {co}.",

    "Dear {name}, On behalf of the leadership team at {co}, I am pleased to confirm your appointment "
    "as {role} at our {city} office. Your compensation will be INR {sal} per annum. "
    "Joining date: {date}. You will report to {manager}. "
    "Subject to company policy and payroll deductions. Confirm by {deadline} via {email}. "
    "Best regards, {hr}, Hiring Team, {co}.",

    "Dear {name}, This letter confirms the offer of employment extended to you by {co} for the "
    "position of {role} at {city}. Annual gross salary: INR {sal}, inclusive of all components. "
    "Employment is contingent upon successful background verification and document submission. "
    "Joining date: {date}. Please respond by {deadline}. HR contact: {email}. "
    "Sincerely, {hr}, Human Resources, {co}.",

    "Dear {name}, It is with great pleasure that we offer you the position of {role} at {co}, {city}. "
    "Your annual CTC will be INR {sal} per annum. Your reporting manager will be {manager}. "
    "We request you to please review the offer carefully and report for joining on {date}. "
    "Please confirm your acceptance of this offer by {deadline}. "
    "Should you have any questions, please do not hesitate to contact us at {email}. "
    "Best regards, {hr}, Talent Acquisition Team, {co}.",
]

# ── Field pools ───────────────────────────────────────────────────────────────
SCAM_ROLES = ["Data Entry Executive", "Back Office Associate", "Work From Home Operator",
              "Online Data Entry Specialist", "Home Based Computer Operator", "Office Assistant",
              "Customer Support Executive", "Typist", "Content Writer", "Form Filling Executive"]

LEGIT_ROLES = ["Software Engineer", "Senior Developer", "Data Analyst", "Product Manager",
               "UX Designer", "DevOps Engineer", "Business Analyst", "QA Engineer",
               "Cloud Architect", "Frontend Developer", "Backend Developer", "Data Scientist",
               "Marketing Manager", "Finance Analyst", "HR Executive", "Operations Manager"]

SCAM_COS  = ["TechGrow Solutions", "QuickHire India", "GlobalWork Services", "EasyJob Network",
             "FastTrack Careers", "HomeWork Pvt Ltd", "DigiWork India", "RapidHire Solutions",
             "OpportunityHub", "CareerBoost India", "WorkFromHome Inc", "InstantJobs Ltd"]

LEGIT_COS = ["Infosys Limited", "Wipro Technologies", "HCL Technologies", "Tech Mahindra",
             "Tata Consultancy Services", "NexaSoft Technologies", "Capgemini India",
             "Accenture India", "IBM India", "Cognizant Technology", "Mphasis Limited",
             "Hexaware Technologies", "Mindtree Ltd", "Persistent Systems", "Zensar Technologies"]

CITIES    = ["Bengaluru", "Mumbai", "Hyderabad", "Pune", "Chennai", "Gurugram", "Noida", "Delhi"]

HR_NAMES  = ["Priya Sharma", "Rahul Mehta", "Anjali Singh", "Suresh Kumar", "Nisha Patel",
             "Arjun Verma", "Pooja Nair", "Ravi Krishnan", "Deepa Iyer", "Anil Gupta"]

MANAGERS  = ["Vikram Shah", "Sunita Rao", "Manoj Tiwari", "Kavitha Menon", "Rajesh Pillai"]

NAMES     = ["Aditi Sharma", "Rohit Gupta", "Sneha Iyer", "Kiran Patel", "Meera Nair",
             "Suresh Verma", "Priya Singh", "Ankit Joshi", "Deepika Rao", "Varun Mehta",
             "Pooja Agarwal", "Nikhil Kumar", "Swati Mishra", "Arjun Bose", "Riya Dubey"]

SCAM_EMAILS   = ["quickhire.hr@gmail.com", "techgrow.jobs@yahoo.com", "hiringdesk@hotmail.com",
                 "globalwork.recruit@gmail.com", "easyjob.india@yahoo.com", "fasthire@gmail.com",
                 "opportunityhub.hr@gmail.com", "workfromhome.jobs@yahoo.com"]

LEGIT_EMAIL_TMPL = ["hr@{domain}", "careers@{domain}", "recruitment@{domain}", "talent@{domain}"]
LEGIT_DOMAINS    = ["infosys.com", "wipro.com", "hcltech.com", "techmahindra.com", "tcs.com",
                    "nexasofttech.com", "capgemini.com", "accenture.com", "ibm.com",
                    "cognizant.com", "mphasis.com", "hexaware.com", "mindtree.com"]

JOINING_DATES  = ["12 August 2026", "1 September 2026", "15 July 2026", "3 October 2026",
                  "18 August 2026", "5 September 2026", "22 July 2026", "10 October 2026"]

DEADLINES      = ["24 July 2026", "10 August 2026", "30 June 2026", "15 September 2026",
                  "25 August 2026", "20 July 2026", "5 August 2026"]

SCAM_SALARIES  = [str(random.randint(8, 25)) + ",000" for _ in range(20)]
LEGIT_SALARIES = [str(random.randint(5, 35)) + ",00,000" for _ in range(20)]
SCAM_FEES      = [str(random.randint(500, 5000)) for _ in range(20)]
HOURS_LIST     = ["2", "4", "6", "12", "24", "48"]
PHONES         = ["+91 9" + str(random.randint(100000000, 999999999)) for _ in range(10)]


def make_scam():
    tmpl = random.choice(SCAM_TEMPLATES)
    return tmpl.format(
        role=random.choice(SCAM_ROLES),
        co=random.choice(SCAM_COS),
        sal=random.choice(SCAM_SALARIES),
        fee=random.choice(SCAM_FEES),
        hours=random.choice(HOURS_LIST),
        email=random.choice(SCAM_EMAILS),
        phone=random.choice(PHONES),
    )


def make_legit():
    tmpl = random.choice(LEGIT_TEMPLATES)
    domain = random.choice(LEGIT_DOMAINS)
    email_tmpl = random.choice(LEGIT_EMAIL_TMPL)
    return tmpl.format(
        name=random.choice(NAMES),
        role=random.choice(LEGIT_ROLES),
        co=random.choice(LEGIT_COS),
        city=random.choice(CITIES),
        sal=random.choice(LEGIT_SALARIES),
        date=random.choice(JOINING_DATES),
        deadline=random.choice(DEADLINES),
        email=email_tmpl.format(domain=domain),
        hr=random.choice(HR_NAMES),
        manager=random.choice(MANAGERS),
    )


rows = []
for _ in range(100):
    rows.append({"text": make_scam(), "label": 1})
for _ in range(100):
    rows.append({"text": make_legit(), "label": 0})

random.shuffle(rows)

out_path = "offer_letters_dataset.csv"
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["text", "label"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows → {out_path}")
print(f"  Scam (1): {sum(1 for r in rows if r['label'] == 1)}")
print(f"  Legit (0): {sum(1 for r in rows if r['label'] == 0)}")
