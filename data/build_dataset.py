"""Build data/letters.json: 20 MADE-UP appointment letters and SMS messages.

No real patient data. Names, clinics, addresses and postcodes are invented.
Weekday names are computed so every message is internally consistent.

Run:  python data/build_dataset.py
"""
import json
from datetime import date
from pathlib import Path


def wd(d):  # Tuesday
    return d.strftime("%A")


def wds(d):  # Tue
    return d.strftime("%a")


def long(d):  # 24 November 2026
    return f"{d.day} {d.strftime('%B %Y')}"


def iso(d):
    return d.isoformat()


def exp(d=None, time=None, clinic=None, address=None):
    return {"date": iso(d) if d else None, "time": time, "clinic": clinic, "address": address}


samples = []


def add(kind, ref, text, expected):
    samples.append(
        {
            "id": len(samples) + 1,
            "kind": kind,
            "reference_date": iso(ref),
            "text": text.strip(),
            "expected": expected,
        }
    )


# 1. Formal letter, 12-hour time, department + hospital in a letter head
d = date(2026, 11, 24)
add("letter", date(2026, 11, 2), f"""
Ophthalmology Outpatients
Dunmore Community Hospital
Harbour Road, Dunmore, PA99 1AB

Date of letter: 2 November 2026

Dear Mr Campbell,

We are pleased to offer you an appointment at the Ophthalmology Outpatient Clinic on {wd(d)} {long(d)}, at 10:30 am.

Please arrive 15 minutes before your appointment time and bring your current glasses. Parking is limited.

Yours sincerely,
Outpatient Booking Team
""", exp(d, "10:30", "Dunmore Community Hospital", "Harbour Road, Dunmore, PA99 1AB"))

# 2. Short SMS, no year
d = date(2026, 11, 12)
add("sms", date(2026, 11, 10),
    f"Glenview Medical Practice: Reminder - you have an appointment on {wds(d)} {d.day} Nov at 2:40pm. "
    "Reply C to cancel. 4 Mill Lane, Glenview, KY99 2CD",
    exp(d, "14:40", "Glenview Medical Practice", "4 Mill Lane, Glenview, KY99 2CD"))

# 3. 24-hour time
d = date(2026, 12, 1)
add("letter", date(2026, 11, 20), f"""
Dear patient,

Your appointment with the practice nurse is on {long(d)} at 09:15.
Location: Strathmore Health Centre, Bridge Street, Strathmore, DD99 4EF.

If you cannot attend, please let us know as early as possible.
""", exp(d, "09:15", "Strathmore Health Centre", "Bridge Street, Strathmore, DD99 4EF"))

# 4. Rescheduled: the NEW date and time are the right answer
old = date(2026, 11, 10)
d = date(2026, 11, 17)
add("letter", date(2026, 11, 6), f"""
Important change to your appointment

Your appointment at Ardgour General Hospital (Station Road, Ardgour, PH99 7GH) on {old.day} November at 14:00 has been cancelled because of staff illness.
We have rebooked you for {wd(d)} {d.day} November at 11:00 at the same location.
We are sorry for the inconvenience.
""", exp(d, "11:00", "Ardgour General Hospital", "Station Road, Ardgour, PH99 7GH"))

# 5. Several dates; only one is the appointment
d = date(2026, 11, 19)
add("letter", date(2026, 11, 3), f"""
Date of letter: 3 November 2026

Dear patient,

You were last seen at our surgery on 15 September 2026. We would now like to see you again.
Your appointment is on {wd(d)} {long(d)} at 3:20 pm at Rowan Surgery, 12 Church Square, Kinloch, IV99 5JK.
""", exp(d, "15:20", "Rowan Surgery", "12 Church Square, Kinloch, IV99 5JK"))

# 6. Numeric UK date, dot time
d = date(2026, 11, 23)
add("letter", date(2026, 11, 5),
    "Appointment: 23/11/2026 at 1.30pm. Location: Birchwood Dental Practice, 8 High Street, Birchwood, G99 3KL.",
    exp(d, "13:30", "Birchwood Dental Practice", "8 High Street, Birchwood, G99 3KL"))

# 7. Time in words
d = date(2026, 12, 3)
add("letter", date(2026, 11, 18),
    f"Your appointment is on the 3rd of December 2026 at half past two in the afternoon, "
    "at Lochview Health Centre, Pier Road, Lochview, PH99 6LM.",
    exp(d, "14:30", "Lochview Health Centre", "Pier Road, Lochview, PH99 6LM"))

# 8. No exact date or time: model must NOT invent them
add("letter", date(2026, 11, 9), """
Dear Mrs Rahman,

You are due a blood pressure check at Elmbank Surgery, 21 Station Road, Elmbank, FK99 8NP, in the week of 7 December 2026.
We will text you with the exact day and time.
""", exp(None, None, "Elmbank Surgery", "21 Station Road, Elmbank, FK99 8NP"))

# 9. No address in the message
d = date(2026, 11, 16)
add("sms", date(2026, 11, 12),
    f"Hi, this is Rosemount Physio. Your session is booked for {wds(d)} {d.day} Nov at 4pm. See you then!",
    exp(d, "16:00", "Rosemount Physio", None))

# 10. Rural outreach clinic in a village hall
d = date(2026, 12, 8)
add("letter", date(2026, 11, 25), f"""
Blood test booked

Time: 8:00 am
Day: {wd(d)} {long(d)}
Location: Glenarran Village Hall (outreach clinic), Station Road, Glenarran, PH99 2PQ

You do not need to fast for this test.
""", exp(d, "08:00", "Glenarran Village Hall", "Station Road, Glenarran, PH99 2PQ"))

# 11. Address split over several lines
d = date(2026, 11, 26)
add("letter", date(2026, 11, 8), f"""
Physiotherapy Department
Corrieden Cottage Hospital
Pier Street
Corrieden
PA99 9QR

Appointment: {wd(d)} {long(d)} at 11:45am

Please wear loose clothing.
""", exp(d, "11:45", "Corrieden Cottage Hospital", "Pier Street, Corrieden, PA99 9QR"))

# 12. Casual SMS with @ and no minutes
d = date(2026, 11, 18)
add("sms", date(2026, 11, 16),
    f"Reminder from Tarbet Dental Care, 14 Shore Road, Tarbet, G99 1RS: see you {wds(d)} {d.day} Nov @ 4pm",
    exp(d, "16:00", "Tarbet Dental Care", "14 Shore Road, Tarbet, G99 1RS"))

# 13. Relative date resolved with the reference date
add("sms", date(2026, 11, 9),
    "Reminder: your appointment at Dalry Medical Centre, 2 Kirk Brae, Dalry, KA99 4ST is tomorrow at 3pm.",
    exp(date(2026, 11, 10), "15:00", "Dalry Medical Centre", "2 Kirk Brae, Dalry, KA99 4ST"))

# 14. Directions, bus number and phone number are distractors
d = date(2026, 12, 4)
add("letter", date(2026, 11, 20), f"""
Outpatient appointment

Date: {wd(d)} {long(d)}
Time: 10:00

Please report to Reception Desk B on Level 2 of the Outpatient Building at Fernhill General Hospital, Hospital Drive, Fernhill, AB99 5UV.
Parking is limited. The number 42 bus stops outside the main entrance.
If you cannot attend, please call 01234 000000.
""", exp(d, "10:00", "Fernhill General Hospital", "Hospital Drive, Fernhill, AB99 5UV"))

# 15. Time in words
d = date(2026, 12, 15)
add("letter", date(2026, 12, 1),
    f"Audiology appointment: {wd(d)} {long(d)} at quarter past ten in the morning. "
    "Place: Bellmouth Health Centre, Quay Lane, Bellmouth, EH99 3VW.",
    exp(d, "10:15", "Bellmouth Health Centre", "Quay Lane, Bellmouth, EH99 3VW"))

# 16. Mobile unit in a car park
d = date(2026, 12, 14)
add("letter", date(2026, 11, 27), f"""
Diabetic eye screening - mobile unit

Your screening is on {long(d)} at 1:10 pm.
The Mobile Eye Screening Unit will be parked in the Co-op car park, Main Road, Kilnair, ML99 2XY.
Please bring a list of your medicines.
""", exp(d, "13:10", "Mobile Eye Screening Unit", "Co-op car park, Main Road, Kilnair, ML99 2XY"))

# 17. SMS with phone numbers as distractors
d = date(2026, 12, 3)
add("sms", date(2026, 11, 30),
    f"Burnside Surgery: Appt {wds(d)} {d.day} Dec 09:40 with Dr Moore. To change call 01234 567890 or text 07700 900123. "
    "Burnside Surgery, 5 Glebe Road, Burnside, G99 6YZ",
    exp(d, "09:40", "Burnside Surgery", "5 Glebe Road, Burnside, G99 6YZ"))

# 18. No year, ordinal day
d = date(2026, 12, 18)
add("letter", date(2026, 11, 30),
    f"Dear patient, your appointment is on {wd(d)}, {d.day}th December at 2.15pm at Muirhead Clinic, "
    "9 Park Terrace, Muirhead, DG99 7AA.",
    exp(d, "14:15", "Muirhead Clinic", "9 Park Terrace, Muirhead, DG99 7AA"))

# 19. Capital letters SMS
d = date(2026, 12, 11)
add("sms", date(2026, 12, 2),
    f"APPT CONFIRMED: {d.day} DEC 10.05AM. MILLBANK HEALTH CENTRE, 3 CROFT ROAD, MILLBANK, FK99 1BC. TXT STOP TO OPT OUT",
    exp(d, "10:05", "Millbank Health Centre", "3 Croft Road, Millbank, FK99 1BC"))

# 20. Informal lower-case text
d = date(2026, 11, 25)
add("sms", date(2026, 11, 20),
    f"ur appt at mill road surgery {wds(d).lower()} {d.day}th nov 11am. 22 mill road, kirkhaven, ab99 2dd",
    exp(d, "11:00", "Mill Road Surgery", "22 Mill Road, Kirkhaven, AB99 2DD"))

assert len(samples) == 20

out = Path(__file__).with_name("letters.json")
out.write_text(json.dumps(samples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {len(samples)} samples to {out}")
