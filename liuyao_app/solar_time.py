"""Local apparent solar clock, computed offline from an instant and east longitude.

Equation of time follows NOAA's Julian-century/Meeus solar equations:
https://gml.noaa.gov/grad/solcalc/calcdetails.html
Positive equation of time means apparent solar time is ahead of mean solar time.
Solar clock values are wall clocks, deliberately without a civil timezone suffix.
"""
from datetime import datetime, timedelta, timezone
import math


def equation_of_time(instant):
    utc = instant.astimezone(timezone.utc)
    jd = (utc - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400 + 2451545
    t = (jd - 2451545) / 36525
    longitude = math.radians((280.46646 + t * (36000.76983 + t * .0003032)) % 360)
    anomaly = math.radians(357.52911 + t * (35999.05029 - .0001537 * t))
    eccentricity = .016708634 - t * (.000042037 + .0000001267 * t)
    obliquity = 23 + (26 + (21.448 - t * (46.815 + t * (.00059 - t * .001813))) / 60) / 60
    obliquity += .00256 * math.cos(math.radians(125.04 - 1934.136 * t))
    y = math.tan(math.radians(obliquity) / 2) ** 2
    value = (y * math.sin(2 * longitude) - 2 * eccentricity * math.sin(anomaly)
             + 4 * eccentricity * y * math.sin(anomaly) * math.cos(2 * longitude)
             - .5 * y * y * math.sin(4 * longitude)
             - 1.25 * eccentricity * eccentricity * math.sin(2 * anomaly))
    return 4 * math.degrees(value)


def solar_clock(instant, longitude):
    equation = equation_of_time(instant)
    clock = instant.astimezone(timezone.utc).replace(tzinfo=None) + timedelta(minutes=4 * longitude + equation)
    return clock, equation
