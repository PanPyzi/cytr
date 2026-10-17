import sys
import threading
import time
import os
import csv
from datetime import datetime
import socketcan
import signal
import RPi.GPIO as GPIO
import subprocess
import re
import pty
import select
import socket
import asyncio
from bless import BlessServer
import obd  # biblioteka do obsługi ELM327

from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

PROGRAM_RUNNING = True

# Ustaw na True, żeby w konsoli wypisywały się surowe wartości ramki 0x128
# (światła/kierunkowskazy) przy każdym odczycie - przydatne do sprawdzenia
# w PRAWDZIWYM aucie, jaki nibble odpowiada za jaki stan świateł.
DEBUG_LIGHTS = False

# --- KONFIGURACJA BLE (UUID usług i charakterystyk) ---

DASH_SERVICE_UUID  = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
TELEMETRY_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # TX (Pi -> telefon, notify)
COMMAND_CHAR_UUID   = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # RX (telefon -> Pi, write)

# --- KONFIGURACJA TRIP-COMPUTERA (CZAS + DYSTANS OD SYGNAŁU 3V) ---
# Numer pinu GPIO (numeracja BCM!) na którym pojawia się ok. 3V sygnalizujące start.
# USTAW TU WŁAŚCIWY NUMER PINU zgodnie z Twoim podłączeniem.
TRIP_TRIGGER_PIN = 13

# --- KLASA DANYCH ---
class CarLogic(QObject):
    btPairingRequest = pyqtSignal(str, str)  # device_name, passkey/pin
    btPairingFinished = pyqtSignal(bool)
    def __init__(self):
        super().__init__()
        # CAN
        self._rpm = 0
        self._speed = 0
        self._water_temp = 0
        self._fuel = 0
        self._dist = "0.0"
        # Flagi
        self._left_turn = False
        self._right_turn = False
        self._lights_on = False
        self._high_beam = False
        self._no_beams = True
        self._oil_alert = False
        self._overheat_alert = False
        self._check_alert = False
        self._battery_alert = False
        #DATA BUS
        self._can_connected = False

        self._cpu_temp = 0.0
        self._time_str="00:00:00"

        # TRIP COMPUTER (start od sygnału 3V na pinie)
        self._trip_time_str = "0:00.000"
        self._trip_dist_str = "0.0"

        # Additional data
        self._bt_active = False
        self.update_bt_status()  # Sprawdź stan przy starcie
        self._bt_pin_code = ""
        self._bt_device_name = ""
        self._bt_pairing_active = False
        self._bt_agent_proc = None
        self._dtc_list = "Brak błędów"
        self._obd_conn = None



    # SYGNAŁY
    dataChanged = pyqtSignal()
    rpmChanged = pyqtSignal(int)
    sysChanged = pyqtSignal()  # zegar + CPU temp (niezależne od CAN/ADC)
    statusChanged = pyqtSignal()
    tripChanged = pyqtSignal()
    pageRequestChanged = pyqtSignal(int)  # 0=strona1, 1=strona2, 2=strona3 (wymuszone przez przełącznik GPIO)

    @pyqtProperty(bool, notify=statusChanged)
    def canConnected(self): return self._can_connected

    # PROPERTY
    @pyqtProperty(int, notify=rpmChanged)
    def rpm(self): return self._rpm

    @rpm.setter
    def rpm(self, v):
        if self._rpm != v: self._rpm = v; self.rpmChanged.emit(v)

    @pyqtProperty(int, notify=dataChanged)
    def speed(self): return self._speed

    @pyqtProperty(int, notify=dataChanged)
    def waterTemp(self): return self._water_temp

    @pyqtProperty(int, notify=dataChanged)
    def fuel(self): return self._fuel

    @pyqtProperty(str, notify=dataChanged)
    def dist(self): return self._dist

    # Flagi
    @pyqtProperty(bool, notify=dataChanged)
    def leftTurn(self): return self._left_turn

    @pyqtProperty(bool, notify=dataChanged)
    def rightTurn(self): return self._right_turn

    @pyqtProperty(bool, notify=dataChanged)
    def lightsOn(self): return self._lights_on

    @pyqtProperty(bool, notify=dataChanged)
    def highBeam(self): return self._high_beam

    @pyqtProperty(bool, notify=dataChanged)
    def noBeams(self): return self._no_beams

    @pyqtProperty(bool, notify=dataChanged)
    def oilAlert(self): return self._oil_alert

    @pyqtProperty(bool, notify=dataChanged)
    def overheatAlert(self): return self._overheat_alert

    @pyqtProperty(bool, notify=dataChanged)
    def checkAlert(self): return self._check_alert

    @pyqtProperty(bool, notify=dataChanged)
    def batteryAlert(self): return self._battery_alert

    @pyqtProperty(float, notify=sysChanged)
    def cpuTemp(self): return self._cpu_temp

    @pyqtProperty(str, notify=sysChanged)
    def time(self): return self._time_str

    # TRIP COMPUTER
    @pyqtProperty(str, notify=tripChanged)
    def tripTime(self): return self._trip_time_str

    @pyqtProperty(str, notify=tripChanged)
    def tripDist(self): return self._trip_dist_str

    @pyqtProperty(bool, notify=dataChanged)
    def btActive(self):
        return self._bt_active

    @pyqtProperty(bool, notify=dataChanged)
    def btPairingActive(self):
        return self._bt_pairing_active

    @pyqtProperty(str, notify=dataChanged)
    def btPinCode(self):
        return self._bt_pin_code

    @pyqtProperty(str, notify=dataChanged)
    def btDeviceName(self):
        return self._bt_device_name



    @pyqtSlot()
    def toggleBluetooth(self):
        try:
            if self._bt_active:
                subprocess.run(["bluetoothctl", "power", "off"], check=True)
                self._bt_active = False
            else:
                subprocess.run(["bluetoothctl", "power", "on"], check=True)
                self._bt_active = True
            self.dataChanged.emit()
        except Exception as e:
            print(f"Błąd toggle BT: {e}")

    def update_bt_status(self):
        try:
            res = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True, timeout=2)
            self._bt_active = "Powered: yes" in res.stdout
        except:
            self._bt_active = False

    @pyqtSlot()
    def startBtPairing(self):
        print("Bluetooth: Uruchamianie trybu parowania i Agenta...")
        self._bt_pairing_active = True
        self.dataChanged.emit()

        # Uruchamiamy w osobnym wątku interaktywny agent bluetoothctl
        threading.Thread(target=self._run_bt_agent, daemon=True).start()

    def _run_bt_agent(self):
        try:
            # 1. Czyszczenie starych procesów
            subprocess.run(["sudo", "killall", "bluetoothctl"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "killall", "bt-agent"], stderr=subprocess.DEVNULL)
            time.sleep(0.5)

            # Włączamy adapter i tryb parowania
            subprocess.run(["bluetoothctl", "power", "on"])
            subprocess.run(["bluetoothctl", "pairable", "on"])
            subprocess.run(["bluetoothctl", "discoverable", "on"])

            master_fd, slave_fd = pty.openpty()
            self._bt_master_fd = master_fd  # Zapisujemy deskryptor do użycia w confirmPairing

            self._bt_agent_proc = subprocess.Popen(
                ["bluetoothctl"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                close_fds=True
            )
            os.close(slave_fd)

            time.sleep(0.2)
            os.write(master_fd, b"default-agent\nagent DisplayYesNo\n")

            while self._bt_pairing_active and self._bt_agent_proc.poll() is None:
                rlist, _, _ = select.select([master_fd], [], [], 0.5)
                if master_fd in rlist:
                    try:
                        output = os.read(master_fd, 1024).decode("utf-8", errors="ignore")
                        if not output:
                            break

                        for line in output.splitlines():
                            clean_line = line.strip()
                            if clean_line:
                                print(f"[BT-PTY] {clean_line}")

                            match_passkey = re.search(r"(Passkey|PIN|Confirm passkey)[:\s]+(\d{6})", clean_line,
                                                      re.IGNORECASE)
                            match_device = re.search(r"Device\s+([0-9A-Fa-f:]+)", clean_line)

                            if match_passkey:
                                passkey = match_passkey.group(2)
                                dev_info = match_device.group(1) if match_device else "Telefon"
                                self._bt_pin_code = passkey
                                self._bt_device_name = dev_info
                                self.dataChanged.emit()
                                print(f"--> BŁYSKAWICZNY KOD PIN (PTY): {passkey}")

                            elif "Request authorization" in clean_line or "Confirm value" in clean_line:
                                self._bt_pin_code = "ZATWIERDŹ"
                                self._bt_device_name = "Telefon"
                                self.dataChanged.emit()

                            elif "Pairing successful" in clean_line:
                                print("Parowanie zakończone sukcesem!")
                                self._bt_pairing_active = False
                                self._bt_pin_code = ""
                                self._bt_device_name = ""
                                self.dataChanged.emit()

                            elif "Failed" in clean_line or "Canceled" in clean_line:
                                self._bt_pairing_active = False
                                self._bt_pin_code = ""
                                self._bt_device_name = ""
                                self.dataChanged.emit()

                    except OSError:
                        break

            try:
                os.close(master_fd)
            except:
                pass
        except Exception as e:
            print(f"Błąd bluetoothctl pty agent: {e}")
        finally:
            self._bt_pairing_active = False
            self._bt_pin_code = ""
            self._bt_device_name = ""
            self.dataChanged.emit()

    @pyqtSlot(bool)
    def confirmPairing(self, accept):
        cmd = b"yes\n" if accept else b"no\n"
        print(f"Wysyłanie odpowiedzi parowania do PTY: {'yes' if accept else 'no'}")

        # Wysyłamy bezpośrednio 'yes' lub 'no' do terminala bluetoothctl
        if hasattr(self, '_bt_master_fd') and self._bt_master_fd is not None:
            try:
                os.write(self._bt_master_fd, cmd)
            except Exception as e:
                print(f"Błąd zapisu do pty: {e}")

        # Dajemy chwilę na przetworzenie polecenia przez proces, potem zamykamy
        time.sleep(0.5)
        if self._bt_agent_proc and self._bt_agent_proc.poll() is None:
            try:
                self._bt_agent_proc.terminate()
            except:
                pass

        self._bt_pairing_active = False
        self._bt_pin_code = ""
        self._bt_device_name = ""
        self.dataChanged.emit()
        print("Stan parowania zresetowany na ekranie.")

    @pyqtProperty(str, notify=dataChanged)
    def dtcList(self):
        return self._dtc_list

    @pyqtSlot()
    def readDtcCodes(self):
        print("OBD: Odczyt błędów DTC...")
        threading.Thread(target=self._async_read_dtc, daemon=True).start()

    @pyqtSlot()
    def clearDtcCodes(self):
        print("OBD: Kasowanie błędów DTC (czyszczenie)...")
        threading.Thread(target=self._async_clear_dtc, daemon=True).start()

    def _get_obd_connection(self):
        if self._obd_conn and self._obd_conn.is_connected():
            return self._obd_conn
        try:
            # Próbujemy połączyć się przez wirtualny port Bluetooth RFCOMM
            print("OBD: Łączenie z ELM327 na /dev/rfcomm0...")
            connection = obd.OBD(port="/dev/rfcomm0", fast=False, timeout=3.0)
            if connection.is_connected():
                self._obd_conn = connection
                return connection
        except Exception as e:
            print(f"OBD Błąd połączenia: {e}")
        return None

    def _async_read_dtc(self):
        conn = self._get_obd_connection()
        if not conn or not conn.is_connected():
            self._dtc_list = "Brak połączenia z ELM!"
            self.dataChanged.emit()
            return

        response = conn.query(obd.commands.GET_DTC)
        if response.is_null() or not response.value:
            self._dtc_list = "Brak zapisanych błędów (Baton OK)"
        else:
            # response.value zwraca listę krotek np. ('P0300', 'Wypadanie zapłonu')
            dtcs = [f"{code}: {desc}" for code, desc in response.value]
            self._dtc_list = "\n".join(dtcs)
            print(f"OBD Odczytano błędy: {self._dtc_list}")

        self.dataChanged.emit()

    def _async_clear_dtc(self):
        conn = self._get_obd_connection()
        if not conn or not conn.is_connected():
            self._dtc_list = "Brak połączenia z ELM!"
            self.dataChanged.emit()
            return

        response = conn.query(obd.commands.CLEAR_DTC)
        # CLEAR_DTC zwraca True/False w zależności od powodzenia
        if response.value:
            self._dtc_list = "Wyczyszczono kody DTC pomyślnie!"
            print("OBD: Kody DTC zostały wyczyszczone.")
        else:
            self._dtc_list = "Nie udało się wyczyścić błędów."
            print("OBD: Błąd podczas czyszczenia DTC.")

        self.dataChanged.emit()





# --- WĄTEK STEROWANIA WIATRAKIEM (PWM) ---
def fan_control_thread():
    print("Start wątku WIATRAKA...")

    FAN_PIN = 18  # Używamy GPIO 18 (fizyczny pin 12)

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(FAN_PIN, GPIO.OUT)

        # Ustawiamy PWM na 100 Hz (częstotliwość)
        fan = GPIO.PWM(FAN_PIN, 100)
        fan.start(0)  # Start od 0%

        curr_speed = 0

        while PROGRAM_RUNNING:
            # 1. Odczyt temperatury (korzystamy z tej samej metody co w loggerze)
            temp = logic.cpuTemp

            # 2. Logika krzywej chłodzenia (Histereza)
            target_speed = 0

            if temp < 45:
                target_speed = 0  # Cisza
            elif temp < 50:
                target_speed = 30  # Minimum, żeby ruszył
            elif temp < 60:
                target_speed = 50  # Średnie obroty
            elif temp < 70:
                target_speed = 75  # Wysokie obroty
            else:
                target_speed = 100  # Pełna moc (Turbina)

            # Zmieniamy obroty tylko jeśli wymagana zmiana jest inna niż obecna
            if target_speed != curr_speed:
                fan.ChangeDutyCycle(target_speed)
                curr_speed = target_speed

            # Sprawdzamy temperaturę co 5 sekund (nie ma sensu częściej)
            time.sleep(5.0)

    except Exception as e:
        print(f"Błąd wiatraka: {e}")
    finally:
        # Na koniec (przy zamykaniu) zatrzymaj wiatrak i posprzątaj GPIO
        try:
            fan.stop()
            GPIO.cleanup()
        except:
            pass

# --- WĄTEK TRIP-COMPUTERA (RESET PRZYCISKIEM CHWILOWYM, START DOPIERO OD PRĘDKOŚCI > 2 KM/H) ---
def trip_thread(logic):
    print("Start wątku TRIP-COMPUTER...")

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIP_TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    except Exception as e:
        print(f"TRIP: Błąd inicjalizacji GPIO ({e})")
        return

    SPEED_THRESHOLD = 2  # km/h - próg, powyżej którego dopiero startuje pomiar

    armed = False        # przycisk naciśnięty, czekamy na prędkość > 2 km/h
    trip_active = False  # pomiar czasu/dystansu faktycznie trwa
    prev_pin_high = False
    start_time = 0.0
    start_dist = 0.0

    def parse_dist(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return 0.0

    while PROGRAM_RUNNING:
        try:
            pin_high = GPIO.input(TRIP_TRIGGER_PIN) == GPIO.HIGH
        except Exception as e:
            print(f"TRIP: Błąd odczytu pinu: {e}")
            time.sleep(1.0)
            continue

        # Przycisk chwilowy -> liczy się samo NACIŚNIĘCIE (zbocze narastające 0V -> 3V),
        # a nie to, czy sygnał jest cały czas obecny.
        if pin_high and not prev_pin_high:
            # Każde naciśnięcie robi pełny reset i ponownie uzbraja pomiar
            armed = True
            trip_active = False
            logic._trip_time_str = "0:00.000"
            logic._trip_dist_str = "0.0"
            logic.tripChanged.emit()
            print("TRIP: Naciśnięto przycisk - reset, czekam na prędkość > 2 km/h.")

        prev_pin_high = pin_high

        if armed and not trip_active and logic._speed > SPEED_THRESHOLD:
            # Dopiero teraz realny start: zerujemy stoper i zapamiętujemy przebieg startowy
            trip_active = True
            armed = False
            start_time = time.monotonic()
            start_dist = parse_dist(logic._dist)
            print("TRIP: Prędkość > 2 km/h - start pomiaru czasu i dystansu.")

        if trip_active:
            elapsed = time.monotonic() - start_time
            m, s = divmod(elapsed, 60)
            logic._trip_time_str = f"{int(m)}:{s:06.3f}"  # np. "1:23.456"

            current_dist = parse_dist(logic._dist)
            trip_dist = max(0.0, current_dist - start_dist)
            logic._trip_dist_str = f"{trip_dist:.1f}"

            logic.tripChanged.emit()

        time.sleep(0.05)

    print("Wątek TRIP-COMPUTER zakończony.")


# --- KONFIGURACJA PRZEŁĄCZNIKA STRON (PIN A / PIN B) ---
# USTAW TU WŁAŚCIWE PINY (numeracja BCM!) zgodnie z Twoim podłączeniem.
# Logika: Pin A = 3V -> strona 1 | oba piny 0V -> strona 2 | Pin B = 3V -> strona 3
PANEL_PIN_A = 5
PANEL_PIN_B = 6


# --- WĄTEK PRZEŁĄCZNIKA STRON ---
def panel_switch_thread(logic):
    print("Start wątku PRZEŁĄCZNIKA STRON...")

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PANEL_PIN_A, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(PANEL_PIN_B, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    except Exception as e:
        print(f"PANEL: Błąd inicjalizacji GPIO ({e})")
        return

    last_state = None  # None wymusza wysłanie strony startowej zaraz po uruchomieniu

    def read_state():
        a = GPIO.input(PANEL_PIN_A) == GPIO.HIGH
        b = GPIO.input(PANEL_PIN_B) == GPIO.HIGH
        return (a, b)

    while PROGRAM_RUNNING:
        try:
            state = read_state()
        except Exception as e:
            print(f"PANEL: Błąd odczytu pinów: {e}")
            time.sleep(1.0)
            continue

        if state != last_state:
            # Prosty debounce - potwierdzamy zmianę po krótkiej chwili,
            # żeby drgania styków przełącznika nie wywoływały fałszywych przełączeń
            time.sleep(0.05)
            try:
                confirm_state = read_state()
            except Exception:
                confirm_state = state

            if confirm_state == state:
                last_state = state
                a, b = state
                if a:
                    target_page = 0  # Pin A = 3V -> Strona 1 (bare bones)
                elif b:
                    target_page = 2  # Pin B = 3V -> Strona 3 (debug/tekst)
                else:
                    target_page = 1  # Żaden pin -> Strona 2 (dojazdówka)

                print(f"PANEL: Zmiana pozycji przełącznika -> strona {target_page + 1}")
                logic.pageRequestChanged.emit(target_page)

        time.sleep(0.1)

    print("Wątek PRZEŁĄCZNIKA STRON zakończony.")



def sys_info_thread(logic):
    print("Start wątku SYSTEM (zegar/CPU temp)...")
    temp_error_reported = False

    while PROGRAM_RUNNING:
        logic._time_str = datetime.now().strftime("%H:%M")

        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                logic._cpu_temp = int(f.read()) / 1000.0
                if temp_error_reported:
                    print("CPU Temp: Odczyt powrócił.")
                    temp_error_reported = False
        except Exception as e:
            if not temp_error_reported:
                print(f"BŁĄD ODCZYTU CPU: {e}")
                print("Sprawdzam alternatywną ścieżkę...")
                try:
                    with open("/sys/devices/virtual/thermal/thermal_zone0/temp", "r") as f2:
                        logic._cpu_temp = int(f2.read()) / 1000.0
                        print("Udało się z alternatywnej ścieżki!")
                except:
                    pass
                temp_error_reported = True

        logic.sysChanged.emit()
        time.sleep(1.0)

    print("Wątek SYSTEM zakończony.")


# --- WĄTEK LOGOWANIA DANYCH (CSV na USB) ---
def logger_thread(logic):
    print("Start wątku LOGGER...")

    # Ścieżka do pendrive'a (zdefiniowana w fstab)
    usb_path = "/mnt/pendrive"

    # Czekamy chwilę na zamontowanie napędu po starcie systemu
    time.sleep(5.0)

    # Sprawdzamy, czy pendrive jest dostępny (czy możemy tam pisać)
    # Prosty test: sprawdzamy czy folder jest zamontowany lub czy jest zapisywalny
    if not os.path.ismount(usb_path) and not os.path.exists(usb_path):
        print("LOGGER: Brak pendrive'a lub błąd montowania. Logowanie wyłączone.")
        return

    # Generujemy nazwę pliku z datą: log_2023-10-27_15-30-00.csv
    filename = f"{usb_path}/log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

    try:
        # Otwieramy plik w trybie 'append' z buforowaniem linii (buffering=1)
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)

            # 1. Zapisujemy nagłówek
            writer.writerow([
                "Timestamp", "RPM", "Speed", "Water Temp", "Fuel level", "Check Engine", "CPU temp"
            ])
            file.flush()  # Wymuszenie zapisu na dysk
            print(f"LOGGER: Rozpoczęto zapis do {filename}")

            while PROGRAM_RUNNING:
                # 2. Zapisujemy dane
                writer.writerow([
                    datetime.now().strftime('%H:%M:%S.%f')[:-3],  # Czas z ms
                    logic.rpm,
                    logic.speed,
                    logic.waterTemp,
                    logic.fuel,
                    1 if logic.checkAlert else 0,
                    logic.cpuTemp
                ])

                # WAŻNE: Flush co linię (lub co kilka), żeby nie stracić danych przy braku prądu
                file.flush()

                # Częstotliwość logowania (np. 2 razy na sekundę)
                time.sleep(0.5)

    except PermissionError:
        print("LOGGER: Brak uprawnień do zapisu (Pendrive Read-Only?)")
    except Exception as e:
        print(f"LOGGER: Błąd zapisu: {e}")

    print("Wątek LOGGER zakończony.")


def can_bus_reader(logic):
    print("Start wątku CAN (tryb Auto-Connect z automatycznym ponawianiem)...")
    socket = None

    while PROGRAM_RUNNING:
        # --- ETAP 1: Próba połączenia (jeśli nie połączono) ---
        if not logic._can_connected:
            try:
                # 1. Podnosimy interfejs (ignorujemy błąd, jeśli HAT jeszcze wstaje)
                os.system("sudo ip link set can0 up type can bitrate 125000")
                os.system("sudo ifconfig can0 txqueuelen 65536")

                # 2. Tworzymy socket
                socket = socketcan.CanRawSocket(interface="can0")
                socket._s.settimeout(0.5)  # Timeout

                # 3. Sukces!
                print("CAN: Połączono pomyślnie!")
                logic._can_connected = True
                logic.statusChanged.emit()

            except Exception as e:
                # Automatyczne ponowienie próby po 3 sekundach zamiast blokowania systemu
                time.sleep(3.0)
                continue

        # --- ETAP 2: Odczyt danych (jeśli połączono) ---
        try:
            if socket is None: raise OSError("Brak socketu")  # Zabezpieczenie

            frame = socket.recv()
            can_id = hex(frame.can_id)
            d = frame.data.hex()

            try:
                # 1. RPM i SPEED (0xb6)
                if can_id == '0xb6':
                    logic.rpm = int(int(d[0:2], 16) * 32.45)
                    logic._speed = int(int(d[4:8], 16) / 95)

                # 2. WODA i DIST (0xf6)
                elif can_id == '0xf6':
                    logic._water_temp = max(0, int(d[2:4], 16) - 39)
                    dst = int(d[4:10], 16)
                    s_dst = str(dst)
                    if len(s_dst) > 1:
                        logic._dist = s_dst[:-1] + "." + s_dst[-1:]
                    else:
                        logic._dist = s_dst

                # 3. PALIWO (0x161)
                elif can_id == '0x161':
                    logic._fuel = int(d[6:8], 16)

                # 4. ŚWIATŁA i KIERUNKI (0x128)
                elif can_id == '0x128':
                    if DEBUG_LIGHTS:
                        n8 = d[8:9] if len(d) > 8 else '?'
                        n9 = d[9:10] if len(d) > 9 else '?'
                        print(f"[0x128 RAW] len={len(d)} hex={d} nibble8={n8} nibble9={n9}")
                    lights_nibble = int(d[8:9], 16)
                    turn_nibble = int(d[9:10], 16)
                    logic._left_turn = (turn_nibble == 2 or turn_nibble == 6)
                    logic._right_turn = (turn_nibble == 4 or turn_nibble == 6)

                    lights_str = bin(lights_nibble)[2:]
                    char1 = lights_str[1] if len(lights_str) > 1 else ''
                    char2 = lights_str[2] if len(lights_str) > 2 else ''

                    logic._lights_on = False
                    logic._high_beam = False
                    logic._no_beams = False
                    if lights_str == "0000":
                        logic._no_beams = True
                    elif char1 == '1':
                        logic._lights_on = True
                    elif char2 == '1':
                        logic._high_beam = True
                    else:
                        logic._no_beams = True

                # 5. ALARMY (0x168)
                elif can_id == '0x168':
                    if len(d) >= 15:
                        b0 = bin(int(d[0:1], 16))
                        b1 = bin(int(d[1:2], 16))
                        b7 = bin(int(d[7:8], 16))
                        b8 = bin(int(d[8:9], 16))
                        b9 = bin(int(d[9:10], 16))
                        b14 = bin(int(d[14:15], 16))

                        overheat = (b0[2:3] == "1")
                        overheat_f = (b0[4:5] == "1")
                        oil = (b1[2:3] == "1")
                        oil_f = (b0[1:2] == "1")
                        check = (b7[2:3] == "1")
                        check_f = (b8[3:4] == "1")
                        battery = (b9[2:3] == "1")
                        battery_f = (b14[0:1] == "1")

                        logic._overheat_alert = overheat or overheat_f
                        logic._oil_alert = oil or oil_f
                        logic._check_alert = check or check_f
                        logic._battery_alert = battery or battery_f

                logic.dataChanged.emit()

            except (ValueError, IndexError) as parse_err:
                pass

        except (TimeoutError, OSError) as e:
            if isinstance(e, OSError) and e.errno == 100:  # Network is down
                print("CAN: Utracono połączenie! Przechodzę w tryb ponawiania...")
                logic._can_connected = False
                logic.statusChanged.emit()
                time.sleep(2.0)
            else:
                continue

        except Exception as e:
            print(f"Inny błąd CAN: {e}")
            logic._can_connected = False
            logic.statusChanged.emit()
            time.sleep(2.0)

    print("Wątek CAN zakończony.")

# --- OBSŁUGA ZAMYKANIA (CTRL+C) ---
def signal_handler(sig, frame):
    global PROGRAM_RUNNING
    print("\nZamykanie programu...")
    PROGRAM_RUNNING = False
    QGuiApplication.quit()


def ble_server_thread(logic):
    print("Start wątku BLE Server (Bless)...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def write_request(characteristic, value, expression):
        try:
            cmd = value.decode('utf-8').strip()
            print(f"BLE: Otrzymano komendę z telefonu: {cmd}")
        except Exception as e:
            print(f"BLE błąd zapisu: {e}")

    async def run_server():
        server = BlessServer(name="C2-Rally-Dash", loop=loop)
        server.read_request_func = lambda char: char.value

        await server.add_new_service(DASH_SERVICE_UUID)

        # Pobieramy flagi bezpośrednio z bless/bleak
        from bless.backends.characteristic import (
            GATTCharacteristicProperties as GProps,
            GATTAttributePermissions as GPerms
        )

        # Charakterystyka telemetrii (Read + Notify)
        await server.add_new_characteristic(
            DASH_SERVICE_UUID,
            TELEMETRY_CHAR_UUID,
            GProps.read | GProps.notify,
            b"START",
            GPerms.readable
        )

        # Charakterystyka komend (Write)
        await server.add_new_characteristic(
            DASH_SERVICE_UUID,
            COMMAND_CHAR_UUID,
            GProps.write | GProps.write_without_response,
            None,
            GPerms.writeable
        )

        server.write_request_func = write_request

        await server.start()
        print("BLE: Serwer uruchomiony i reklamuje się jako 'C2-Rally-Dash'...")

        while PROGRAM_RUNNING:
            if not logic._bt_active:
                break

            data_str = f"T:{logic._time_str}|C:{logic._cpu_temp:.1f}C\n"
            val = data_str.encode('utf-8')

            try:
                char = server.get_characteristic(TELEMETRY_CHAR_UUID)
                if char:
                    char.value = bytearray(val)
                    server.update_value(DASH_SERVICE_UUID, TELEMETRY_CHAR_UUID)
            except Exception as e:
                print(f"BLE błąd update_value: {e}")

            await asyncio.sleep(1.0)

        await server.stop()
        print("BLE: Serwer zatrzymany.")

    def write_request(characteristic, value, expression):
        try:
            cmd = value.decode('utf-8').strip().lower()
            print(f"BLE: Otrzymano komendę z telefonu: {cmd}")

            if cmd == "readdtc":
                logic.readDtcCodes()
            elif cmd == "cleardtc":
                logic.clearDtcCodes()

        except Exception as e:
            print(f"BLE błąd zapisu: {e}")

    try:
        loop.run_until_complete(run_server())
    except Exception as e:
        print(f"BLE błąd pętli: {e}")
    finally:
        loop.close()
    print("Wątek BLE zakończony.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    time.sleep(1.0)

    app = QGuiApplication(sys.argv)
    logic = CarLogic()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("CarData", logic)
    engine.load("Dashboard.qml")

    if not engine.rootObjects(): sys.exit(-1)

    t_can = threading.Thread(target=can_bus_reader, args=(logic,))
    t_sys = threading.Thread(target=sys_info_thread, args=(logic,))
    t_fan = threading.Thread(target=fan_control_thread)
    t_log = threading.Thread(target=logger_thread, args=(logic,))
    t_trip = threading.Thread(target=trip_thread, args=(logic,))
    t_panel = threading.Thread(target=panel_switch_thread, args=(logic,))
    t_bt_server = threading.Thread(target=ble_server_thread, args=(logic,), daemon=True)



    t_fan.start()
    t_can.start()
    t_sys.start()
    t_log.start()
    t_trip.start()
    t_panel.start()
    t_bt_server.start()

    exit_code = app.exec()

    print("Zamykanie wątków...")
    PROGRAM_RUNNING = False

    t_can.join(timeout=2.0)
    t_sys.join(timeout=2.0)
    t_log.join(timeout=2.0)
    t_fan.join(timeout=1.0)
    t_trip.join(timeout=1.0)
    t_panel.join(timeout=1.0)
    print("Gotowe.")
    sys.exit(exit_code)