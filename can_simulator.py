#!/usr/bin/env python3
"""
can_simulator.py - SYMULATOR RAMEK CAN DO TESTOWANIA DASHBOARDU
================================================================

Osobny program, który udaje "żywy organizm" auta - wysyła na wybranym
interfejsie CAN (domyślnie can1) dokładnie takie ramki, jakich oczekuje
main.py (can_bus_reader). Uruchamiasz go RÓWNOLEGLE z main.py na tej samej
płytce (2 kanały CAN), żeby przetestować cały dashboard bez podpinania auta.

WYMAGANIE SPRZĘTOWE: drugi kanał CAN (can1) musi być fizycznie spięty
z pierwszym (can0) - CANH-CANH, CANL-CANL (plus wspólna masa GND), tak jak
zwykły odcinek magistrali CAN. Oba końce najlepiej zaterminować rezystorem
120 Ohm (większość płytek 2-kanałowych ma to już na pokładzie/przełącznikiem).

URUCHOMIENIE:
    python3 can_simulator.py                      # domyślnie interfejs can1
    python3 can_simulator.py --interface can1
    python3 can_simulator.py --interface can1 --setup   # sam podniesie interfejs

W TRAKCIE DZIAŁANIA wpisujesz komendy (Enter zatwierdza):
    help                 - lista komend
    status               - pokazuje aktualny stan symulowanych danych
    rpm sweep on|off     - włącz/wyłącz automatyczne "falowanie" obrotów 0->7500->0
    rpm <wartosc>        - ustaw obroty ręcznie (działa gdy "rpm sweep" jest off)
    speed <wartosc>      - ustaw prędkość [km/h]
    water <wartosc>      - ustaw temperaturę wody [°C]
    fuel <wartosc>       - ustaw poziom paliwa [%]
    dist <wartosc>       - ustaw przebieg (np. 123456.7)
    check on|off         - Check Engine
    battery on|off       - alarm akumulatora/ładowania
    oil on|off           - alarm ciśnienia oleju
    overheat on|off      - alarm przegrzania silnika
    left on|off          - lewy kierunkowskaz
    right on|off         - prawy kierunkowskaz
    lights off|low|high  - światła: brak / mijania / drogowe
    quit                 - koniec programu
"""

import argparse
import os
import sys
import threading
import time

from socketcan import CanRawSocket, CanFrame


# ============================================================
# STAN SYMULOWANEGO "AUTA" (współdzielony między wątkami)
# ============================================================
class SimState:
    def __init__(self):
        self.lock = threading.Lock()

        self.rpm = 800
        self.rpm_sweep = True       # automatyczne falowanie 0 -> 7500 -> 0
        self.speed = 0

        self.water_temp = 90
        self.dist = "123456.7"      # przebieg jako string, tak jak w main.py

        self.fuel = 55

        self.lights_on = False      # mijania
        self.high_beam = False      # drogowe
        self.left_turn = False
        self.right_turn = False

        self.check_engine = False
        self.battery_alert = False
        self.oil_alert = False
        self.overheat_alert = False

        self.running = True


STATE = SimState()


# ============================================================
# KODOWANIE RAMEK (odwrotność parsowania z main.py -> can_bus_reader)
# ============================================================
def encode_rpm_speed(rpm, speed):
    # main.py: rpm = int(d[0:2],16) * 32.45 | speed = int(d[4:8],16) / 95
    byte0 = max(0, min(255, int(round(rpm / 32.45))))
    speed_raw = max(0, min(0xFFFF, int(round(speed * 95))))
    b2 = (speed_raw >> 8) & 0xFF
    b3 = speed_raw & 0xFF
    return bytes([byte0, 0x00, b2, b3, 0x00, 0x00, 0x00, 0x00])


def encode_water_dist(water_temp, dist_str):
    # main.py: water_temp = int(d[2:4],16) - 39 | dist z 3 bajtów (d[4:10])
    byte1 = max(0, min(255, int(round(water_temp)) + 39))
    digits = dist_str.replace(".", "").lstrip("0") or "0"
    try:
        dist_int = int(digits) & 0xFFFFFF
    except ValueError:
        dist_int = 0
    b2 = (dist_int >> 16) & 0xFF
    b3 = (dist_int >> 8) & 0xFF
    b4 = dist_int & 0xFF
    return bytes([0x00, byte1, b2, b3, b4, 0x00, 0x00, 0x00])


def encode_fuel(fuel_percent):
    # main.py: fuel = int(d[6:8],16)  -> bajt nr 3
    b3 = max(0, min(255, int(round(fuel_percent))))
    return bytes([0x00, 0x00, 0x00, b3, 0x00, 0x00, 0x00, 0x00])


def encode_lights_turn(lights_on, high_beam, left_turn, right_turn):
    # main.py (po naprawie) odtwarza dokładnie stary, sprawdzony na aucie
    # mechanizm z main_old.py + renderer.js:
    #   lights_str = bin(lights_nibble)[2:]   (string binarny BEZ zer wiodących)
    #   lights_str[1] == '1'  -> światła mijania
    #   lights_str[2] == '1'  -> światła drogowe (tylko gdy [1] nie jest '1')
    # Wartości nibble dobrane tak, żeby dawały jednoznaczny, przewidywalny wynik:
    #   0  -> "0"   -> brak świateł (za krótki string, nic nie pasuje)
    #   3  -> "11"  -> [1]=='1' -> światła mijania
    #   5  -> "101" -> [1]=='0', [2]=='1' -> światła drogowe
    if high_beam:
        lights_nibble = 5
    elif lights_on:
        lights_nibble = 3
    else:
        lights_nibble = 0

    # Kierunkowskazy - logika bez zmian (main.py: turn_nibble==2/4/6),
    # to było zgodne ze starym kodem od samego początku.
    if left_turn and right_turn:
        turn_nibble = 0x6
    elif left_turn:
        turn_nibble = 0x2
    elif right_turn:
        turn_nibble = 0x4
    else:
        turn_nibble = 0x0

    byte4 = ((lights_nibble & 0xF) << 4) | (turn_nibble & 0xF)
    return bytes([0x00, 0x00, 0x00, 0x00, byte4, 0x00, 0x00, 0x00])


def encode_alerts(check_engine, battery_alert, oil_alert, overheat_alert):
    # main.py (po naprawie) odtwarza dokładnie stary main_old.py: testuje,
    # czy dany nibble jest RÓŻNY OD ZERA (a nie konkretny bit), na tych
    # samych pozycjach co stary kod:
    #   bajt0 górny nibble (d[0:1]) != 0  -> OVERHEAT
    #   bajt0 dolny nibble (d[1:2]) != 0  -> OIL
    #   bajt3 dolny nibble (d[7:8]) != 0  -> CHECK ENGINE
    #   bajt4 dolny nibble (d[9:10]) != 0 -> BATTERY (AKU)
    # Więc każda niezerowa wartość nibble włącza dany alarm - używamy 0x1.
    overheat_nibble = 0x1 if overheat_alert else 0x0
    oil_nibble = 0x1 if oil_alert else 0x0
    check_nibble = 0x1 if check_engine else 0x0
    battery_nibble = 0x1 if battery_alert else 0x0

    byte0 = (overheat_nibble << 4) | oil_nibble
    byte3 = check_nibble          # dolny nibble bajtu3 (górny nibble = 0, nieużywany)
    byte4 = battery_nibble        # dolny nibble bajtu4 (górny nibble = 0 = "check_f", zawsze martwy w main_old.py)
    return bytes([byte0, 0x00, 0x00, byte3, byte4, 0x00, 0x00, 0x00])


# ============================================================
# WĄTEK: AUTOMATYCZNE "FALOWANIE" OBROTÓW 0 -> 7500 -> 0
# ============================================================
def rpm_sweep_thread():
    RPM_MIN = 0
    RPM_MAX = 7500
    STEP = 60          # o ile zmieniamy obroty co "tick"
    TICK = 0.03         # 30 ms -> płynny ruch wskazówki

    direction = 1  # 1 = w górę, -1 = w dół

    while STATE.running:
        with STATE.lock:
            if STATE.rpm_sweep:
                STATE.rpm += direction * STEP
                if STATE.rpm >= RPM_MAX:
                    STATE.rpm = RPM_MAX
                    direction = -1
                elif STATE.rpm <= RPM_MIN:
                    STATE.rpm = RPM_MIN
                    direction = 1
        time.sleep(TICK)


# ============================================================
# WĄTEK: WYSYŁANIE RAMEK CAN
# ============================================================
def sender_thread(sock):
    last_send = {"0xb6": 0.0, "0xf6": 0.0, "0x161": 0.0, "0x128": 0.0, "0x168": 0.0}
    intervals = {"0xb6": 0.05, "0xf6": 0.5, "0x161": 1.0, "0x128": 0.2, "0x168": 0.5}

    while STATE.running:
        now = time.monotonic()

        with STATE.lock:
            rpm = STATE.rpm
            speed = STATE.speed
            water_temp = STATE.water_temp
            dist = STATE.dist
            fuel = STATE.fuel
            lights_on = STATE.lights_on
            high_beam = STATE.high_beam
            left_turn = STATE.left_turn
            right_turn = STATE.right_turn
            check_engine = STATE.check_engine
            battery_alert = STATE.battery_alert
            oil_alert = STATE.oil_alert
            overheat_alert = STATE.overheat_alert

        try:
            if now - last_send["0xb6"] >= intervals["0xb6"]:
                sock.send(CanFrame(can_id=0xb6, data=encode_rpm_speed(rpm, speed)))
                last_send["0xb6"] = now

            if now - last_send["0xf6"] >= intervals["0xf6"]:
                sock.send(CanFrame(can_id=0xf6, data=encode_water_dist(water_temp, dist)))
                last_send["0xf6"] = now

            if now - last_send["0x161"] >= intervals["0x161"]:
                sock.send(CanFrame(can_id=0x161, data=encode_fuel(fuel)))
                last_send["0x161"] = now

            if now - last_send["0x128"] >= intervals["0x128"]:
                sock.send(CanFrame(can_id=0x128, data=encode_lights_turn(
                    lights_on, high_beam, left_turn, right_turn)))
                last_send["0x128"] = now

            if now - last_send["0x168"] >= intervals["0x168"]:
                sock.send(CanFrame(can_id=0x168, data=encode_alerts(
                    check_engine, battery_alert, oil_alert, overheat_alert)))
                last_send["0x168"] = now

        except Exception as e:
            print(f"[BŁĄD WYSYŁANIA] {e}")
            time.sleep(0.5)

        time.sleep(0.01)


# ============================================================
# POMOCNICZE: parsowanie komend z konsoli
# ============================================================
def print_help():
    print(__doc__)


def print_status():
    with STATE.lock:
        print("---------------------------------------------")
        print(f" RPM            : {STATE.rpm}  (sweep: {'ON' if STATE.rpm_sweep else 'OFF'})")
        print(f" Prędkość       : {STATE.speed} km/h")
        print(f" Temp. wody     : {STATE.water_temp} °C")
        print(f" Przebieg       : {STATE.dist} km")
        print(f" Paliwo         : {STATE.fuel} %")
        print(f" Światła mijania: {STATE.lights_on}   drogowe: {STATE.high_beam}")
        print(f" Kierunkowskazy : lewy={STATE.left_turn}  prawy={STATE.right_turn}")
        print(f" Check Engine   : {STATE.check_engine}")
        print(f" Alarm baterii  : {STATE.battery_alert}")
        print(f" Alarm oleju    : {STATE.oil_alert}")
        print(f" Przegrzanie    : {STATE.overheat_alert}")
        print("---------------------------------------------")


def on_off(token):
    return token.strip().lower() in ("on", "1", "true", "tak")


def handle_command(cmd):
    parts = cmd.strip().split()
    if not parts:
        return

    verb = parts[0].lower()

    try:
        if verb in ("help", "?"):
            print_help()

        elif verb == "status":
            print_status()

        elif verb == "quit" or verb == "exit":
            STATE.running = False

        elif verb == "rpm" and len(parts) >= 2 and parts[1].lower() == "sweep":
            with STATE.lock:
                STATE.rpm_sweep = on_off(parts[2]) if len(parts) >= 3 else not STATE.rpm_sweep
            print(f"RPM sweep: {'ON' if STATE.rpm_sweep else 'OFF'}")

        elif verb == "rpm" and len(parts) >= 2:
            with STATE.lock:
                STATE.rpm = max(0, min(8000, int(float(parts[1]))))
                if STATE.rpm_sweep:
                    print("UWAGA: 'rpm sweep' jest włączone, więc ta wartość zaraz zostanie nadpisana. Wpisz 'rpm sweep off' żeby ustawiać ręcznie.")

        elif verb == "speed" and len(parts) >= 2:
            with STATE.lock:
                STATE.speed = max(0, min(300, float(parts[1])))

        elif verb == "water" and len(parts) >= 2:
            with STATE.lock:
                STATE.water_temp = float(parts[1])

        elif verb == "fuel" and len(parts) >= 2:
            with STATE.lock:
                STATE.fuel = max(0, min(100, float(parts[1])))

        elif verb == "dist" and len(parts) >= 2:
            with STATE.lock:
                STATE.dist = parts[1]

        elif verb == "check" and len(parts) >= 2:
            with STATE.lock:
                STATE.check_engine = on_off(parts[1])

        elif verb == "battery" and len(parts) >= 2:
            with STATE.lock:
                STATE.battery_alert = on_off(parts[1])

        elif verb == "oil" and len(parts) >= 2:
            with STATE.lock:
                STATE.oil_alert = on_off(parts[1])

        elif verb == "overheat" and len(parts) >= 2:
            with STATE.lock:
                STATE.overheat_alert = on_off(parts[1])

        elif verb == "left" and len(parts) >= 2:
            with STATE.lock:
                STATE.left_turn = on_off(parts[1])

        elif verb == "right" and len(parts) >= 2:
            with STATE.lock:
                STATE.right_turn = on_off(parts[1])

        elif verb == "lights" and len(parts) >= 2:
            mode = parts[1].lower()
            with STATE.lock:
                if mode == "off":
                    STATE.lights_on = False
                    STATE.high_beam = False
                elif mode == "low":
                    STATE.lights_on = True
                    STATE.high_beam = False
                elif mode == "high":
                    STATE.lights_on = True
                    STATE.high_beam = True
                else:
                    print("Użycie: lights off|low|high")

        else:
            print(f"Nieznana komenda: '{cmd}'. Wpisz 'help' żeby zobaczyć listę.")

    except ValueError:
        print("Błędna wartość liczbowa w komendzie.")


# ============================================================
# GŁÓWNY PROGRAM
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Symulator ramek CAN do testowania dashboardu")
    parser.add_argument("--interface", default="can1", help="Interfejs CAN do wysyłania (domyślnie can1)")
    parser.add_argument("--bitrate", type=int, default=125000, help="Bitrate magistrali (domyślnie 125000, tak jak w main.py)")
    parser.add_argument("--setup", action="store_true", help="Automatycznie podnieś interfejs przed startem (wymaga sudo)")
    args = parser.parse_args()

    if args.setup:
        print(f"Podnoszę interfejs {args.interface} (bitrate {args.bitrate})...")
        os.system(f"sudo ip link set {args.interface} up type can bitrate {args.bitrate}")
        time.sleep(0.5)

    try:
        sock = CanRawSocket(interface=args.interface)
    except Exception as e:
        print(f"Nie udało się otworzyć interfejsu '{args.interface}': {e}")
        print("Sprawdź czy interfejs istnieje i jest podniesiony (ip link show), albo uruchom z flagą --setup.")
        sys.exit(1)

    print(f"Symulator CAN wystartował na interfejsie '{args.interface}'.")
    print("Wpisz 'help' żeby zobaczyć dostępne komendy, 'quit' żeby zakończyć.\n")

    t_sweep = threading.Thread(target=rpm_sweep_thread, daemon=True)
    t_send = threading.Thread(target=sender_thread, args=(sock,), daemon=True)
    t_sweep.start()
    t_send.start()

    try:
        while STATE.running:
            try:
                cmd = input("> ")
            except EOFError:
                break
            handle_command(cmd)
    except KeyboardInterrupt:
        print("\nPrzerwano (Ctrl+C).")
    finally:
        STATE.running = False
        time.sleep(0.2)
        print("Koniec symulatora.")


if __name__ == "__main__":
    main()
