from datetime import date

def get_sun_sign(d: date) -> str:
    m, day = d.month, d.day

    if   (m == 3 and day >= 21) or (m == 4 and day <= 19): return "Aries"
    if   (m == 4 and day >= 20) or (m == 5 and day <= 20): return "Taurus"
    if   (m == 5 and day >= 21) or (m == 6 and day <= 20): return "Gemini"
    if   (m == 6 and day >= 21) or (m == 7 and day <= 22): return "Cancer"
    if   (m == 7 and day >= 23) or (m == 8 and day <= 22): return "Leo"
    if   (m == 8 and day >= 23) or (m == 9 and day <= 22): return "Virgo"
    if   (m == 9 and day >= 23) or (m == 10 and day <= 22): return "Libra"
    if   (m == 10 and day >= 23) or (m == 11 and day <= 21): return "Scorpio"
    if   (m == 11 and day >= 22) or (m == 12 and day <= 21): return "Sagittarius"
    if   (m == 12 and day >= 22) or (m == 1 and day <= 19): return "Capricorn"
    if   (m == 1 and day >= 20) or (m == 2 and day <= 18): return "Aquarius"
    return "Pisces"
