import re, sys

with open(r'C:\Users\Administrator\Desktop\世界杯赛程\worldcup.html', 'r', encoding='utf-8') as f:
    html = f.read()

fixes = {
    # === MD1 remaining 8 ===
    "FRA', away:'SEN', dateBJ:'2026-06-16T19:00": "FRA', away:'SEN', dateBJ:'2026-06-17T03:00",
    "IRQ', away:'NOR', dateBJ:'2026-06-16T22:00": "IRQ', away:'NOR', dateBJ:'2026-06-17T06:00",
    "ARG', away:'ALG', dateBJ:'2026-06-17T01:00": "ARG', away:'ALG', dateBJ:'2026-06-17T09:00",
    "AUT', away:'JOR', dateBJ:'2026-06-17T04:00": "AUT', away:'JOR', dateBJ:'2026-06-17T12:00",
    "POR', away:'COD', dateBJ:'2026-06-17T17:00": "POR', away:'COD', dateBJ:'2026-06-18T01:00",
    "ENG', away:'CRO', dateBJ:'2026-06-17T20:00": "ENG', away:'CRO', dateBJ:'2026-06-18T04:00",
    "GHA', away:'PAN', dateBJ:'2026-06-17T23:00": "GHA', away:'PAN', dateBJ:'2026-06-18T07:00",
    "UZB', away:'COL', dateBJ:'2026-06-18T02:00": "UZB', away:'COL', dateBJ:'2026-06-18T10:00",

    # === MD2 ===
    "A3', group:'A', home:'MEX', away:'KOR', dateBJ:'2026-06-15T22:00": "A3', group:'A', home:'MEX', away:'KOR', dateBJ:'2026-06-19T09:00",
    "A4', group:'A', home:'RSA', away:'CZE', dateBJ:'2026-06-16T01:00": "A4', group:'A', home:'RSA', away:'CZE', dateBJ:'2026-06-19T00:00",
    "B3', group:'B', home:'CAN', away:'QAT', dateBJ:'2026-06-16T22:00": "B3', group:'B', home:'CAN', away:'QAT', dateBJ:'2026-06-19T06:00",
    "B4', group:'B', home:'BIH', away:'SUI', dateBJ:'2026-06-17T01:00": "B4', group:'B', home:'BIH', away:'SUI', dateBJ:'2026-06-19T03:00",
    "C3', group:'C', home:'BRA', away:'HAI', dateBJ:'2026-06-17T22:00": "C3', group:'C', home:'BRA', away:'HAI', dateBJ:'2026-06-20T08:30",
    "C4', group:'C', home:'MAR', away:'SCO', dateBJ:'2026-06-18T01:00": "C4', group:'C', home:'MAR', away:'SCO', dateBJ:'2026-06-20T06:00",
    "D3', group:'D', home:'USA', away:'AUS', dateBJ:'2026-06-18T22:00": "D3', group:'D', home:'USA', away:'AUS', dateBJ:'2026-06-20T03:00",
    "D4', group:'D', home:'PAR', away:'TUR', dateBJ:'2026-06-19T01:00": "D4', group:'D', home:'PAR', away:'TUR', dateBJ:'2026-06-20T11:00",
    "E3', group:'E', home:'GER', away:'CIV', dateBJ:'2026-06-18T17:00": "E3', group:'E', home:'GER', away:'CIV', dateBJ:'2026-06-21T04:00",
    "E4', group:'E', home:'CUW', away:'ECU', dateBJ:'2026-06-18T20:00": "E4', group:'E', home:'CUW', away:'ECU', dateBJ:'2026-06-21T08:00",
    "F3', group:'F', home:'NED', away:'SWE', dateBJ:'2026-06-19T17:00": "F3', group:'F', home:'NED', away:'SWE', dateBJ:'2026-06-21T01:00",
    "F4', group:'F', home:'JPN', away:'TUN', dateBJ:'2026-06-19T20:00": "F4', group:'F', home:'JPN', away:'TUN', dateBJ:'2026-06-21T12:00",
    "G3', group:'G', home:'BEL', away:'IRN', dateBJ:'2026-06-19T22:00": "G3', group:'G', home:'BEL', away:'IRN', dateBJ:'2026-06-22T03:00",
    "G4', group:'G', home:'EGY', away:'NZL', dateBJ:'2026-06-20T01:00": "G4', group:'G', home:'EGY', away:'NZL', dateBJ:'2026-06-22T09:00",
    "H3', group:'H', home:'ESP', away:'KSA', dateBJ:'2026-06-20T16:00": "H3', group:'H', home:'ESP', away:'KSA', dateBJ:'2026-06-22T00:00",
    "H4', group:'H', home:'CPV', away:'URU', dateBJ:'2026-06-20T19:00": "H4', group:'H', home:'CPV', away:'URU', dateBJ:'2026-06-22T06:00",
    "I3', group:'I', home:'FRA', away:'IRQ', dateBJ:'2026-06-20T22:00": "I3', group:'I', home:'FRA', away:'IRQ', dateBJ:'2026-06-23T05:00",
    "I4', group:'I', home:'SEN', away:'NOR', dateBJ:'2026-06-21T01:00": "I4', group:'I', home:'SEN', away:'NOR', dateBJ:'2026-06-23T08:00",
    "J3', group:'J', home:'ARG', away:'AUT', dateBJ:'2026-06-21T22:00": "J3', group:'J', home:'ARG', away:'AUT', dateBJ:'2026-06-23T01:00",
    "J4', group:'J', home:'ALG', away:'JOR', dateBJ:'2026-06-22T01:00": "J4', group:'J', home:'ALG', away:'JOR', dateBJ:'2026-06-23T11:00",
    "K3', group:'K', home:'POR', away:'UZB', dateBJ:'2026-06-22T17:00": "K3', group:'K', home:'POR', away:'UZB', dateBJ:'2026-06-24T01:00",
    "K4', group:'K', home:'COD', away:'COL', dateBJ:'2026-06-22T20:00": "K4', group:'K', home:'COD', away:'COL', dateBJ:'2026-06-24T10:00",
    "L3', group:'L', home:'ENG', away:'GHA', dateBJ:'2026-06-22T22:00": "L3', group:'L', home:'ENG', away:'GHA', dateBJ:'2026-06-24T04:00",
    "L4', group:'L', home:'CRO', away:'PAN', dateBJ:'2026-06-23T01:00": "L4', group:'L', home:'CRO', away:'PAN', dateBJ:'2026-06-24T07:00",

    # === MD3 (groups A-F verified from Baidu) ===
    "A5', group:'A', home:'RSA', away:'KOR', dateBJ:'2026-06-23T22:00": "A5', group:'A', home:'RSA', away:'KOR', dateBJ:'2026-06-25T09:00",
    "A6', group:'A', home:'MEX', away:'CZE', dateBJ:'2026-06-23T22:00": "A6', group:'A', home:'MEX', away:'CZE', dateBJ:'2026-06-25T09:00",
    "B5', group:'B', home:'BIH', away:'QAT', dateBJ:'2026-06-24T01:00": "B5', group:'B', home:'BIH', away:'QAT', dateBJ:'2026-06-25T03:00",
    "B6', group:'B', home:'CAN', away:'SUI', dateBJ:'2026-06-24T01:00": "B6', group:'B', home:'CAN', away:'SUI', dateBJ:'2026-06-25T03:00",
    "C5', group:'C', home:'MAR', away:'HAI', dateBJ:'2026-06-24T22:00": "C5', group:'C', home:'MAR', away:'HAI', dateBJ:'2026-06-25T06:00",
    "C6', group:'C', home:'BRA', away:'SCO', dateBJ:'2026-06-24T22:00": "C6', group:'C', home:'BRA', away:'SCO', dateBJ:'2026-06-25T06:00",
}

count = 0
not_found = []
for old, new in fixes.items():
    if old in html:
        html = html.replace(old, new)
        count += 1
    else:
        not_found.append(old)

with open(r'C:\Users\Administrator\Desktop\世界杯赛程\worldcup.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Fixed: {count}')
if not_found:
    print(f'Not found ({len(not_found)}):')
    for nf in not_found:
        print(f'  {nf[:60]}')
