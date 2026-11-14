"""Build a SAMPLE bus timetable in GTFS format (made-up stops, made-up times).

One rural route, "42", between a village and a hospital, with few buses a day,
and request stops (the passenger must signal the driver). Real GTFS data can
replace these files later: app/load_gtfs.py reads standard GTFS file names.

Run:  python data/build_gtfs_sample.py
"""
import csv
from pathlib import Path

OUT = Path(__file__).with_name("gtfs_sample")
OUT.mkdir(exist_ok=True)

# stop_id, name, lat, lon, request_stop (GTFS has no such column; it is an extra column)
STOPS = [
    ("GLN_HALL", "Glenarran Village Hall", 56.4000, -5.4000, 1),
    ("GLN_STN", "Glenarran Station Road", 56.4040, -5.3900, 1),
    ("KLN_COOP", "Kilnair Co-op", 56.4150, -5.3700, 0),
    ("COR_PIER", "Corrieden Pier", 56.4300, -5.3400, 1),
    ("FRN_XRD", "Fernside Crossroads", 56.4450, -5.3100, 1),
    ("DUN_HOSP", "Dunmore Community Hospital", 56.4600, -5.2800, 0),
]
OUTBOUND_OFFSETS = [0, 6, 15, 27, 38, 50]  # minutes after the first stop
INBOUND_OFFSETS = [0, 12, 23, 35, 44, 50]  # same road, other direction

WEEKDAY_OUT = ["07:10", "09:40", "12:15", "15:30", "17:45"]
SATURDAY_OUT = ["09:40", "15:30"]
WEEKDAY_IN = ["08:30", "11:00", "13:40", "16:30", "18:30"]
SATURDAY_IN = ["11:00", "16:30"]

PLACES = [
    # name, address, stop_id: where a clinic is, and the nearest bus stop
    ("Dunmore Community Hospital", "Harbour Road, Dunmore, PA99 1AB", "DUN_HOSP"),
    ("Glenarran Village Hall", "Station Road, Glenarran, PH99 2PQ", "GLN_HALL"),
    ("Kilnair Co-op", "Main Road, Kilnair, ML99 2XY", "KLN_COOP"),
]


def hhmm_to_min(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def fmt(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def write(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


write("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon", "request_stop"], STOPS)
write("routes.txt", ["route_id", "route_short_name", "route_long_name"], [("R42", "42", "Glenarran - Dunmore")])
write(
    "calendar.txt",
    ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"],
    [
        ("WEEKDAY", 1, 1, 1, 1, 1, 0, 0, "20261101", "20270331"),
        ("SATURDAY", 0, 0, 0, 0, 0, 1, 0, "20261101", "20270331"),
    ],
)
write("places.txt", ["name", "address", "stop_id"], PLACES)

trips, stop_times = [], []
n = 0
for service, outs, ins in (("WEEKDAY", WEEKDAY_OUT, WEEKDAY_IN), ("SATURDAY", SATURDAY_OUT, SATURDAY_IN)):
    for direction, starts, offsets, stops, headsign in (
        (0, outs, OUTBOUND_OFFSETS, STOPS, "Dunmore Community Hospital"),
        (1, ins, INBOUND_OFFSETS, STOPS[::-1], "Glenarran"),
    ):
        for start in starts:
            n += 1
            trip_id = f"T{n:02d}_{service[:3]}_{'OUT' if direction == 0 else 'IN'}_{start.replace(':', '')}"
            trips.append(("R42", service, trip_id, headsign, direction))
            for seq, (stop, off) in enumerate(zip(stops, offsets), start=1):
                t = fmt(hhmm_to_min(start) + off)
                stop_times.append((trip_id, t, t, stop[0], seq))

write("trips.txt", ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id"], trips)
write("stop_times.txt", ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"], stop_times)
print(f"wrote sample GTFS to {OUT}: {len(STOPS)} stops, {len(trips)} trips, {len(stop_times)} stop times")
