#  -*- coding: UTF-8 -*-
#
#  display.py
#
#  Created by Diego on 2023/04/07 19:37:42.
#  Copyright © Diego. All rights reserved.

import math

import utime
from machine import I2C
from sh1106 import SH1106_I2C

TEXT_SIZE = 8


class Display:
    def __init__(self, width: int = 128, height: int = 64, fps=25):
        self._width = width
        self._height = height
        self.fps = fps

        i2c = I2C(
            0
        )  # Init I2C using I2C0 defaults, SCL=Pin(GP9), SDA=Pin(GP8), freq=400000
        # For ESP32 PICO, SCL=Pin(GP18), SDA=Pin(GP19), freq=400000

        self.display = SH1106_I2C(self._width, self._height, i2c, rotate=180)
        self.display.fill(0)

        self.buttons: list[Button] = []
        self.button_positons = [(16, 20), (16, 30), (16, 40), (16, 50)]
        self.pointer = Pointer(self.display, style="*")

        self._period_us = 1e6 / self.fps
        self._last_us = utime.ticks_us()

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def show(self):
        self.display.show()

    def text(self, *args, **kwargs):
        return self.display.text(*args, **kwargs)

    def add_button(self, name: str, start_position: tuple[int, int]):
        button = Button(self.display, name, start_position)
        self.buttons.append(button)

    def draw_border(self, linewidth: int = 1):
        """画出边框"""
        self.display.rect(0, 0, self._width, self._height, linewidth)

    def draw_header(
        self,
        title: str,
        linewidth: int = 1,
        with_border: bool = True,
        refresh: bool = False,
    ):
        """15 chars capacity

        Args:
            title (str): _description_
            linewidth (int, optional): _description_. Defaults to 1.
            with_border (bool, optional): _description_. Defaults to True.
            refresh (bool, optional): _description_. Defaults to False.
        """
        text_position = int(self._height * 0.06)
        self.display.text(title, text_position, text_position)
        line_height = int(self._height * 0.22)
        self.display.hline(0, line_height, self._width, linewidth)
        if with_border:
            self.draw_border()
        if refresh:
            self.show()

    def draw_frame(self, title: str):
        self.display.fill(0)
        self.draw_header(title)
        for b in self.buttons:
            b.draw()
        self.pointer.draw()
        self.show()

    def draw_init(self):
        """启动画面，持续3秒钟，可以用来初始化一些参数。"""
        self.display.fill(0)

        self.display.text("Super Macro", 20, 4)
        self.display.text("Created by Diego", 1, 44)
        self.show()
        utime.sleep(2)

        self.display.fill(1)
        self.show()
        utime.sleep(1)

        self.display.fill(0)
        self.show()

    def draw_message(self, title: str, message: str):
        if len(message) > 60:
            return self.draw_message(title, "message too long")
        self.display.fill(0)
        self.draw_header(title)

        if "\n" in message:
            formated_message = message.split("\n")
            rows = len(formated_message)
            y_position = [int(70 * (r + 1) / (rows + 1)) for r in range(rows)]
            x_position = [int((15 - len(m)) / 2) * 8 + 3 for m in formated_message]
            for i, m in enumerate(formated_message):
                self.display.text(m, x_position[i], y_position[i])
            self.show()
        else:
            rows = math.ceil(len(message) / 15)  # 一行最多15个字母
            formated_message = [message[15 * i : 15 * (i + 1)] for i in range(rows)]
            y_position = [int(70 * (r + 1) / (rows + 1)) for r in range(rows)]
            x_position = [int((15 - len(m)) / 2) * 8 + 3 for m in formated_message]
            for i, m in enumerate(formated_message):
                self.display.text(m, x_position[i], y_position[i])
            self.show()

    def draw_pwm(self, pwm, title: str = "PWM"):
        duty = pwm.duty_u16()
        freq = pwm.freq()
        self.display.fill(0)

        self.draw_header(title)

        self.display.text("Duty", 4, 18)
        self.display.text(f"{duty / 65535 * 100:<5.2f}%", 32, 29)
        self.display.text("Pulse frequency", 4, 40)
        self.display.text(f"{freq:<7.2f} Hz", 32, 51)
        self.show()

    def draw_rpm_and_freq(self, motor_rpm: float, motor_freq: float):
        """显示电机参数
            <弃用>
        Args:
            motor_rpm (float): 电机转速
            motor_freq (float): PWM脉冲频率
        """

        self.draw_header("Super Macro")

        self.display.text("Motor speed", 4, 18)
        self.display.text(f"{motor_rpm} rpm", 32, 29)
        self.display.text("Pulse frequency", 4, 40)

        self.display.text(f"{motor_freq:.2f} Hz", 32, 51)
        self.show()

    def draw_motor(self, motor, title="Super Macro"):
        now = utime.ticks_us()
        if now - self._last_us < self._period_us:
            return

        self.display.fill(0)
        self.draw_header(title)

        self.display.text("Motor speed", 4, 18)
        self.display.text(f"{motor.adjust_rpm():<7.2f} rpm", 32, 29)
        self.display.text("Pulse frequency", 4, 40)
        self.display.text(f"{motor.frequency:<8.2f} Hz", 32, 51)
        self.show()

        self._last_us = utime.ticks_us()


class Components:
    def __init__(self):
        pass

    def position(self):
        pass

    def draw(self):
        pass


class Header(Components):
    def __init__(self, display: Display, title: str, linewidth: int = 1):
        self.display = display
        self.title = title
        self._position = (0, 0)
        self.linewidth = linewidth

    def position(self):
        return self._position

    def draw(self):
        text_position = int(self.display.height * 0.06)
        line_height = int(self.display.height * 0.22)
        self.display.text(self.title, text_position, text_position)
        self.display.display.hline(
            self._position[0],
            self._position[1] + line_height,
            self.display.width,
            self.linewidth,
        )
        self.display.display.rect(0, 0, self.display.width, self.display.height, 1)


class Button(Components):
    def __init__(self, display, name: str, _position: tuple[int, int]) -> None:
        self.display = display
        self.name = name
        self._position: tuple = _position
        self.lenth = self.name * TEXT_SIZE

    def __len__(self):
        return self.lenth

    @property
    def len(self):
        return self.lenth

    @property
    def position(self):
        return self._position

    def on_select(self):
        pass

    def on_click(self):
        pass

    def draw(self):
        self.display.text(self.name, *self._position)


class Pointer(Components):
    def __init__(self, display, style: str, point_at=None) -> None:
        self.display = display
        self.style = style
        self._position = (-100, -100)
        if point_at is not None:
            self.point_at(point_at)

    def point_at(self, position: tuple[int, int], x_bias=-10, y_bias=0):
        x, y = position
        self._position = (x + x_bias, y + y_bias)

    @property
    def position(self):
        return self._position

    def draw(self):
        self.display.text(self.style, *self._position)


class Graph(Components):
    pass


class Warning(Components):
    pass


class SubPage(Components):
    def __init__(self, display: Display, type, position) -> None:
        self.display: Display = display
        self.text_list: list = []
        if position == "left":
            self._position = (0, int(self.display.height * 0.22))
        if position == "right":
            self._position = (
                int(self.display.width / 2),
                int(self.display.height * 0.22),
            )

        if type == "Laser":
            self.init_laser_text()
            self.type = 0
        if type == "Motor":
            self.init_motor_text()
            self.type = 1

    @property
    def position(self):
        return self._position

    def init_laser_text(self):
        self.text_list.append(("Duty", (3, 20)))
        self.text_list.append(("Freq", (3, 40)))

    def init_motor_text(self):
        self.text_list.append(("M1 RPM", (64, 20)))
        self.text_list.append(("M2 RPM", (64, 40)))

    def update_laser(self, duty, freq):
        self.text_list.append((f"  {duty*100:.1f}%", (3, 30)))
        self.text_list.append((f"{freq:.0f}Hz", (3, 50)))

    def update_motor(self, rpm1, rpm2):
        self.text_list.append((f"  {rpm1:.2f}", (64, 30)))
        self.text_list.append((f"  {rpm2:.2f}", (64, 50)))

    def draw(self):
        for t, p in self.text_list:
            self.display.text(t, *p)
        self.display.display.vline(
            int(self.display.width / 2) - 1, 14, self.display.height - 14, 1
        )

    def update(self, data1, data2):
        if self.type == 0:
            self.update_laser(data1, data2)
        if self.type == 1:
            self.update_motor(data1, data2)


class Screen:
    def __init__(self, display: Display, title: str = None) -> None:
        self.display: Display = display
        self.content: list[Components] = []
        if title is not None:
            self.header = Header(self.display, title)
            self.content.append(self.header)

    def add(self, component: Components):
        self.content.append(component)

    def show(self):
        self.display.display.fill(0)
        for c in self.content:
            c.draw()
        self.display.show()
