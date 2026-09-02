from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

# --- ПОДКЛЮЧЕНИЕ К ANDROID BLUETOOTH (Оставляем) ---
try:
    from jnius import autoclass

    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothSocket = autoclass('android.bluetooth.BluetoothSocket')
    UUID = autoclass('java.util.UUID')
    BufferedReader = autoclass('java.io.BufferedReader')
    InputStreamReader = autoclass('java.io.InputStreamReader')
    OutputStream = autoclass('java.io.OutputStream')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')

    from android.permissions import request_permissions, Permission, check_permission

    permissions = [Permission.BLUETOOTH_CONNECT, Permission.BLUETOOTH_SCAN, Permission.ACCESS_FINE_LOCATION]
    request_permissions(permissions)

    BLUETOOTH_UUID = "00001101-0000-1000-8000-00805F9B34FB"


    def get_socket(device):
        socket = device.createRfcommSocketToServiceRecord(UUID.fromString(BLUETOOTH_UUID))
        socket.connect()
        return socket

except ImportError:
    def get_socket(device):
        return None


    BluetoothAdapter = None


# --- ТРЕНДЫ ---
class TrendAnalyzer:
    def __init__(self):
        self.history = {'rpm': [], 'temp': [], 'pressure': []}
        self.max_len = 20

    def add_reading(self, rpm, temp, pressure):
        self.history['rpm'].append(rpm)
        self.history['temp'].append(temp)
        self.history['pressure'].append(pressure)
        for key in self.history:
            if len(self.history[key]) > self.max_len:
                self.history[key].pop(0)

    def analyze_trends(self):
        result = []
        if len(self.history['temp']) >= 5:
            temp_slope = self.history['temp'][-1] - self.history['temp'][-5]
            if temp_slope > 3:
                result.append("🚨 ТРЕНД: Температура резко растет! Риск перегрева!")
            elif temp_slope < -2:
                result.append("⚠ ТРЕНД: Температура падает!")
        if len(self.history['rpm']) >= 5:
            rpm_spread = max(self.history['rpm'][-5:]) - min(self.history['rpm'][-5:])
            if rpm_spread > 300:
                result.append("⚠ ТРЕНД: Обороты скачут!")
        return result


# --- ЛОГИКА ---
def intelligent_diagnosis(rpm, temp, pressure, throttle):
    diagnosis_list = []
    if 700 < rpm < 900:
        if throttle < 5:
            diagnosis_list.append("Режим ХХ: Параметры в норме.")
        else:
            diagnosis_list.append("⚠ Проверьте ДПДЗ.")
    elif rpm > 1100 and throttle < 5:
        diagnosis_list.append("⚠ Плавающие обороты. РХХ.")
    if temp > 105:
        diagnosis_list.append("🚨 Перегрев!")
    elif temp < 70:
        diagnosis_list.append("⚠ Не прогревается.")
    if pressure > 500 and rpm < 1000:
        diagnosis_list.append("⚠ Подсос воздуха.")
    if not diagnosis_list:
        return "✅ Нарушений не выявлено."
    return "\n".join(diagnosis_list)


# --- КРУГЛЫЙ ИНДИКАТОР ---
class CircleIndicator(Widget):
    def __init__(self, title, value_range, unit, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.value_range = value_range
        self.unit = unit
        self.current_value = 0
        self.size_hint = (None, None)
        self.size = (dp(150), dp(150))

        # Настройка подписи
        self.label = Label(
            text=f"{self.title}: 0 {self.unit}",
            font_size=dp(14),
            halign="center",
            valign="middle",
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.add_widget(self.label)

        # Начальный цвет
        self.ring_color = get_color_from_hex('#4CAF50')  # Зеленый по умолчанию
        self.status_text = "Норма"

    def update_value(self, value):
        self.current_value = value
        self.label.text = f"{self.title}: {value:.0f} {self.unit}\n[{self.get_status()}]"

        # Меняем цвет в зависимости от значения
        if self.value_range[0] <= value <= self.value_range[1]:
            self.ring_color = get_color_from_hex('#4CAF50')  # Зеленый
            self.status_text = "Норма"
        elif value < self.value_range[0] or value > self.value_range[1] * 1.2:
            self.ring_color = get_color_from_hex('#F44336')  # Красный
            self.status_text = "Критично"
        else:
            self.ring_color = get_color_from_hex('#FFC107')  # Желтый
            self.status_text = "Внимание"

        self.canvas.before.clear()
        with self.canvas.before:
            # Рисуем круг (кольцо)
            Color(*self.ring_color)
            Line(circle=(self.center_x, self.center_y, dp(60)), width=dp(8))
            # Внутренний фон
            Color(0.1, 0.1, 0.1, 1)
            Ellipse(pos=(self.center_x - dp(55), self.center_y - dp(55)), size=(dp(110), dp(110)))

    def get_status(self):
        return self.status_text


# --- ПРИЛОЖЕНИЕ ---
class VazBluetoothApp(App):
    def build(self):
        self.title = "ВАЗ Диагностика"
        self.trend_analyzer = TrendAnalyzer()
        self.socket = None
        self.reader = None

        self.root_layout = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(8))

        # Заголовок
        self.header = Label(
            text="🚗 HUD Диагностика ВАЗ",
            font_size=dp(28),
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=0.1
        )
        self.root_layout.add_widget(self.header)

        # Кнопка Bluetooth
        self.bt_status = Label(text="Bluetooth: Выключен", color=(0.5, 0.5, 0.5, 1), size_hint_y=0.05)
        self.bt_button = Button(
            text="🔵 Подключить OBD",
            size_hint_y=0.08,
            background_normal='',
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        self.bt_button.bind(on_press=self.show_bt_devices)
        self.root_layout.add_widget(self.bt_status)
        self.root_layout.add_widget(self.bt_button)

        # Панель с круговыми индикаторами
        self.circle_layout = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=0.4)

        # Создаем индикаторы
        self.rpm_indicator = CircleIndicator("Обороты", (700, 3000), "RPM")
        self.temp_indicator = CircleIndicator("Температура", (70, 105), "°C")
        self.pressure_indicator = CircleIndicator("Давление", (200, 500), "мБар")

        self.circle_layout.add_widget(self.rpm_indicator)
        self.circle_layout.add_widget(self.temp_indicator)
        self.circle_layout.add_widget(self.pressure_indicator)

        self.root_layout.add_widget(self.circle_layout)

        # Кнопка диагностики
        self.diag_button = Button(
            text="🔍 Интеллектуальная диагностика",
            size_hint_y=0.08,
            background_color=(0.3, 0.7, 0.3, 1),
            color=(1, 1, 1, 1)
        )
        self.diag_button.bind(on_press=self.run_diagnosis)
        self.root_layout.add_widget(self.diag_button)

        # Случайные данные для начала (тест на ПК)
        Clock.schedule_interval(self.update_real_data, 2)

        return self.root_layout

    def show_bt_devices(self, instance):
        if not BluetoothAdapter:
            self.bt_status.text = "Bluetooth недоступен (вы на ПК)"
            return

        adapter = BluetoothAdapter.getDefaultAdapter()
        if not adapter:
            self.bt_status.text = "Bluetooth выключен"
            return

        if not adapter.isEnabled():
            activity = PythonActivity.mActivity
            intent = Intent("android.bluetooth.adapter.action.REQUEST_ENABLE")
            activity.startActivityForResult(intent, 1)

        devices = adapter.getBondedDevices().toArray()
        if not devices:
            self.bt_status.text = "Нет сопряженных OBD адаптеров"
            return

        from kivy.uix.popup import Popup
        from kivy.uix.scrollview import ScrollView

        content = BoxLayout(orientation='vertical')
        scroll = ScrollView()
        list_layout = BoxLayout(orientation='vertical', size_hint_y=None)
        list_layout.bind(minimum_height=list_layout.setter('height'))

        for device in devices:
            btn = Button(
                text=device.getName(),
                size_hint_y=None,
                height=dp(50),
                background_normal='',
                background_color=(0.3, 0.3, 0.3, 1)
            )
            btn.bind(on_press=lambda x, dev=device: self.connect_to_device(dev, popup))
            list_layout.add_widget(btn)

        scroll.add_widget(list_layout)
        content.add_widget(scroll)

        popup = Popup(title="Выберите устройство", content=content, size_hint=(0.9, 0.9))
        popup.open()

    def connect_to_device(self, device, popup):
        popup.dismiss()
        try:
            self.socket = get_socket(device)
            self.reader = BufferedReader(InputStreamReader(self.socket.getInputStream()))
            self.bt_status.text = f"Подключено: {device.getName()}"
            self.send_command("ATZ")
            self.send_command("ATSP0")
            self.send_command("ATE0")
        except Exception as e:
            self.bt_status.text = f"Ошибка: {str(e)}"

    def send_command(self, cmd):
        if self.socket:
            output = OutputStream(self.socket.getOutputStream())
            output.write((cmd + "\r").encode())
            output.flush()

    def read_response(self):
        if self.reader:
            try:
                return self.reader.readLine()
            except:
                return None
        return None

    def update_real_data(self, dt):
        # На ПК: используем случайные данные для демонстрации
        import random
        rpm = random.randint(750, 950)
        temp = random.randint(70, 110)
        pressure = random.randint(250, 450)

        # Обновляем индикаторы
        self.rpm_indicator.update_value(rpm)
        self.temp_indicator.update_value(temp)
        self.pressure_indicator.update_value(pressure)

        # Сохраняем в тренды
        self.trend_analyzer.add_reading(rpm, temp, pressure)

    def run_diagnosis(self, instance):
        try:
            rpm = self.rpm_indicator.current_value
            temp = self.temp_indicator.current_value
            pressure = self.pressure_indicator.current_value

            result = intelligent_diagnosis(rpm, temp, pressure, 0)
            trends = self.trend_analyzer.analyze_trends()

            if trends:
                result += "\n\n" + "\n".join(trends)

            # Создаем попап с результатом
            from kivy.uix.popup import Popup
            popup = Popup(
                title='Результат диагностики',
                content=Label(text=result, halign='center', valign='middle'),
                size_hint=(0.9, 0.9)
            )
            popup.open()

        except Exception as e:
            from kivy.uix.popup import Popup
            popup = Popup(
                title='Ошибка',
                content=Label(text=str(e), halign='center', valign='middle'),
                size_hint=(0.9, 0.5)
            )
            popup.open()


if __name__ == '__main__':
    VazBluetoothApp().run()