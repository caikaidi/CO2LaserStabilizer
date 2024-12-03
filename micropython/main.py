#  -*- coding: UTF-8 -*-
#
#  main.py
#
#  Created by Diego on 2024/12/03 15:55:48.
#  Copyright © Diego. All rights reserved.

if __name__ == "__main__":
    pass

import json
import machine
import select
import sys
import time
import _thread
from _thread import allocate_lock

from _display import Display


class MCmd:
    def __init__(self, rendered: bool, title: str, message: str, time_ms: int) -> None:
        self.rendered = rendered
        self.title = title
        self.message = message
        self.time = time_ms


def monitor(display: Display, time_interval: int, lock: allocate_lock) -> None:
    global monitor_cmd
    while True:
        try:
            with lock:
                if not monitor_cmd.rendered:
                    display.draw_message(monitor_cmd.title, monitor_cmd.message)
                    monitor_cmd.rendered = True
                    time.sleep_ms(monitor_cmd.time + 1)
            time.sleep_ms(time_interval)
        except Exception as e:
            with lock:
                monitor_cmd = MCmd(
                    rendered=False,
                    title="M Error",
                    message=str(e),
                    time_ms=1000,
                )
            time.sleep_ms(1000)
            continue


def load_cmd(message: str) -> dict | None:
    try:
        cmd = json.loads(message)
        return cmd
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    # 初始化显示屏
    display = Display()
    display.draw_init()

    # 初始化PWM
    laser_pwm = machine.PWM(machine.Pin(0))
    laser_pwm.duty_u16(0)

    # 初始化串口
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)

    # 屏幕线程
    lock = allocate_lock()
    monitor_cmd = MCmd(
        rendered=False,
        title="init",
        message="init success, starting main loop...",
        time_ms=1000,
    )
    _thread.start_new_thread(monitor, (display, 20, lock))  # 20 ms 刷新一次显示

    while True:
        try:
            message = poll.poll(1000)
        except Exception as e:
            monitor_cmd = MCmd(
                rendered=False,
                title="P Error",
                message=str(e),
                time_ms=1000,
            )
            continue
        if message:
            try:
                message = message[0][0].readline().strip()
                cmd = load_cmd(message)
                if not cmd:
                    raise ValueError("invalid cmd")
                if "freq" not in cmd or "duty" not in cmd:
                    raise KeyError("missing freq or duty")
                freq = int(cmd["freq"])
                duty = int(cmd["duty"])
                if freq < 1000 or freq > 1000000 or duty < 0 or duty > 65535:
                    raise ValueError("invalid freq or duty")

                with lock:
                    monitor_cmd = MCmd(
                        rendered=False,
                        title=f"PWM {time.time()}",
                        message=f"FREQ: {freq}\nDUTY: {duty*100/65535:.2f}%",
                        time_ms=10,
                    )
                laser_pwm.freq(freq)
                laser_pwm.duty_u16(duty)
            except Exception as e:
                with lock:
                    monitor_cmd = MCmd(
                        rendered=False,
                        title="C Error",
                        message=str(e),
                        time_ms=1000,
                    )
        else:
            with lock:
                monitor_cmd = MCmd(
                    rendered=False,
                    title=f"no cmd {time.time()}",
                    message="waiting for cmd...",
                    time_ms=10,
                )
