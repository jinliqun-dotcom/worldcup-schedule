import re
with open(r'C:\Users\Administrator\Desktop\世界杯赛程\worldcup.html', encoding='utf-8') as f:
    c = f.read()
print(f'braces: {c.count("{")} / {c.count("}")}  ({ "OK" if c.count("{")==c.count("}") else "MISMATCH" })')
print(f'lines: {c.count(chr(10))}')
print(f'COUNTRY_CODES: {c.count("COUNTRY_CODES")}')
print(f'flagcdn: {c.count("flagcdn.com")}')
print(f'FLAGS (old): {len(re.findall(r"\bFLAGS\b", c))}')
print(f'.team .flag css: {c.count(".team .flag")}')
