"""Генерирует модель OWASP Threat Dragon (формат v2) для DFD варианта 29."""
import json, uuid
U = lambda: str(uuid.uuid5(uuid.NAMESPACE_URL, f"v29-{next(C)}"))
import itertools; C = itertools.count()
cells, num = [], itertools.count(1)
def threat(t, title, desc, mit, sev="High"):
    return {"id": U(), "title": title, "status": "Mitigated", "severity": sev, "type": t,
            "description": desc, "mitigation": mit, "modelType": "STRIDE", "new": False, "number": next(num), "score": ""}
def node(shape, typ, name, x, y, w=160, h=80, threats=()):
    i = U()
    data = {"type": typ, "name": name, "description": "", "outOfScope": False, "reasonOutOfScope": "",
            "hasOpenThreats": False, "threats": list(threats)}
    if typ == "tm.Process": data.update(handlesCardPayment=False, handlesGoodsOrServices=False, isWebApplication=False, privilegeLevel="")
    if typ == "tm.Actor": data.update(providesAuthentication=False)
    if typ == "tm.Store": data.update(isALog=False, storesCredentials=False, isEncrypted=True, isSigned=False)
    cells.append({"position": {"x": x, "y": y}, "size": {"width": w, "height": h},
                  "attrs": {"text": {"text": name}, "body": {"stroke": "#333333", "strokeWidth": 1.5, "strokeDasharray": None}},
                  "visible": True, "shape": shape, "id": i, "zIndex": len(cells) + 10, "data": data})
    return i
def flow(src, dst, name, threats=()):
    i = U()
    cells.append({"shape": "flow", "attrs": {"line": {"stroke": "#333333", "targetMarker": {"name": "block"}, "sourceMarker": {"name": ""}, "strokeDasharray": None}},
                  "width": 200, "height": 100, "zIndex": len(cells) + 10, "connector": "smooth", "id": i,
                  "data": {"type": "tm.Flow", "name": name, "description": "", "outOfScope": False, "reasonOutOfScope": "",
                           "protocol": "", "isEncrypted": True, "isPublicNetwork": False, "hasOpenThreats": False, "threats": list(threats)},
                  "labels": [name], "source": {"cell": src}, "target": {"cell": dst}, "vertices": []})
def boundary(name, x, y, w, h):
    cells.append({"position": {"x": x, "y": y}, "size": {"width": w, "height": h},
                  "attrs": {"label": {"text": name}, "body": {"stroke": "#d03b3b", "strokeDasharray": "10 5"}},
                  "visible": True, "shape": "trust-boundary-box", "id": U(), "zIndex": -1,
                  "data": {"type": "tm.BoundaryBox", "name": name, "description": "", "isTrustBoundary": True, "hasOpenThreats": False}})
boundary("OT-сеть диспетчерской", 300, 40, 620, 520)
boundary("Радиосеть и машины", 960, 300, 300, 260)
op = node("actor", "tm.Actor", "Оператор диспетчерской", 40, 330)
an = node("actor", "tm.Actor", "Аналитик / ERP", 40, 90)
p1 = node("process", "tm.Process", "P1 Сервис аварийных команд", 360, 400, 160, 160, [
    threat("Denial of service", "Нехватка памяти из-за отчётности", "Тяжёлые отчёты на общем узле задерживают аварийные команды (главный сценарий FAIR)", "Bulkhead: отдельные отсеки и узлы, лимиты памяти, PriorityClass"),
    threat("Repudiation", "Отрицание снятия аварийной остановки", "Оператор отрицает, что снял остановку", "Неизменяемый журнал команд (WORM) с подписью и временем", "Medium")])
p2 = node("process", "tm.Process", "P2 Диспетчеризация рейсов (FMS)", 360, 200, 160, 140)
p3 = node("process", "tm.Process", "P3 Сервис отчётности", 360, 60, 160, 110, [
    threat("Elevation of privilege", "Аналитик получает доступ к командному API", "Учётная запись отчётности используется для команд", "Сегментация OT/IT, чтение только реплики БД, минимальные права")])
ds1 = node("store", "tm.Store", "DS1 БД техники", 700, 120, 170, 70, [
    threat("Tampering", "Изменение карты зон в БД", "Неверные границы зон приводят к выдаче одного участка двум машинам", "RBAC, утверждение изменения вторым лицом, журнал изменений")])
ds2 = node("store", "tm.Store", "DS2 Журнал команд (аудит)", 700, 440, 170, 70)
tr = node("actor", "tm.Actor", "Бортовой контроллер самосвала", 1020, 400)
flow(op, p1, "F1 E-stop / возобновить", [threat("Spoofing", "Снятие остановки с захваченной рабочей станции", "Посторонний снимает аварийную остановку", "MFA и правило двух лиц для возобновления движения")])
flow(op, p2, "F2 задания")
flow(p1, tr, "F3 команда стоп (радио)", [threat("Spoofing", "Поддельная команда «возобновить»", "Злоумышленник передаёт команду по радио", "Подпись команд ECDSA со счётчиком против повтора"),
                                         threat("Denial of service", "Глушение радиосети", "Команда не доходит до машин", "Второй канал другой технологии, watchdog 2 с")])
flow(p2, tr, "F4 маршрут, зоны", [threat("Tampering", "Изменение маршрута в канале", "Подмена маршрута или зоны", "Подпись и проверка целостности на борту, mTLS")])
flow(tr, p2, "F5 телеметрия, heartbeat", [threat("Information disclosure", "Перехват позиций машин и людей", "Прослушивание радиоканала", "Шифрование канала, TLS, отдельная APN", "Medium")])
flow(p1, ds2, "F6 запись"); flow(p2, ds1, "F7"); flow(p3, ds1, "F8 запросы"); flow(an, p3, "F9 отчёты (HTTPS)")
model = {"version": "2.2.0",
         "summary": {"title": "Вариант 29 — автономные самосвалы на карьере", "owner": "Пара, вариант 29",
                     "description": "DFD и угрозы STRIDE для функции аварийной остановки", "id": 0},
         "detail": {"contributors": [], "diagrams": [{"id": 0, "title": "DFD: аварийная остановка и диспетчеризация",
                    "diagramType": "STRIDE", "placeholder": "New STRIDE diagram description",
                    "thumbnail": "./public/content/images/thumbnail.stride.jpg", "version": "2.2.0", "cells": cells}],
                    "diagramTop": 1, "reviewer": "", "threatTop": next(num) - 1}}
json.dump(model, open("report/threat-model/variant29-threat-dragon.json", "w"), ensure_ascii=False, indent=1)
print("threats:", model["detail"]["threatTop"], "cells:", len(cells))
