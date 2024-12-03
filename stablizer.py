#  -*- coding: UTF-8 -*-
#
#  stablizer.py
#
#  Created by Diego on 2024/12/03 15:56:46.
#  Copyright © Diego. All rights reserved.


import json
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from io import BytesIO
import pyvisa
import serial
import serial.tools.list_ports
import streamlit as st

DEFAULT_PID_VALUES = (150000.0, 7000.0, 0.0, 0.0)
POWER_INTERVAL = 0.05  # 功率测量间隔（秒）
TIME_RANGE = 30  # 功率曲线显示时间范围（秒）

st.title("功率稳定器")

st.header("1. 连接功率计")


# 定义 PID 控制器
class Pid:
    def __init__(
        self,
        partial: float,
        integral: float,
        derivative: float,
        target: float,
        i_min: float = -100,  # 考虑是否合适
        i_max: float = 100,
    ) -> None:
        super().__init__()
        self.target: float = target
        self.last_error: float = 0
        self.accumulate_error_min: float = i_min
        self.accumulate_error_max: float = i_max
        self.accumulate_error: float = 0
        self.output: float = 0
        self.partial: float = partial
        self.integral: float = integral
        self.derivative: float = derivative

        self.p_err: float = 0
        self.i_err: float = 0
        self.d_err: float = 0

    def set_target(self, target: float) -> None:
        self.target = target

    def set_pidt(self, pidt: tuple[float, ...]) -> None:
        assert len(pidt) == 4, "p, i, d, t value invalid"
        self.partial = pidt[0]
        self.integral = pidt[1]
        self.derivative = pidt[2]
        self.target = pidt[3]

    def pid(self, feedback: float) -> float:
        error = self.target - feedback
        self.accumulate_error = self.accumulate_error + error
        if self.accumulate_error < self.accumulate_error_min:
            self.accumulate_error = self.accumulate_error_min
        if self.accumulate_error > self.accumulate_error_max:
            self.accumulate_error = self.accumulate_error_max

        p = self.partial * error
        i = self.integral * self.accumulate_error
        d = self.derivative * (error - self.last_error)
        self.output = p + i + d

        self.p_err = p
        self.i_err = i
        self.d_err = d

        self.last_error = error
        return self.output


def set_pwm(freq: float, duty: float, micro_controller: serial.Serial) -> None:
    pwm_cmd = {"freq": freq, "duty": duty}
    pwm_str = json.dumps(pwm_cmd)
    byte_message = bytes(pwm_str + "\n", "utf-8")
    micro_controller.write(byte_message)


# 初始化 session state
if "micro_controller_connected" not in st.session_state:
    st.session_state.micro_controller_connected = False
if "micro_controller" not in st.session_state:
    st.session_state.micro_controller = None
if "power_meter_connected" not in st.session_state:
    st.session_state.power_meter_connected = False
if "power_meter" not in st.session_state:
    st.session_state.power_meter = None
if "pid_controller" not in st.session_state:
    st.session_state.pid_controller = Pid(*DEFAULT_PID_VALUES)
if "time_list" not in st.session_state:
    st.session_state.time_list = []
if "power_list" not in st.session_state:
    st.session_state.power_list = []
if "current_pwm_duty" not in st.session_state:
    st.session_state.current_pwm_duty = 0

# 连接功率计
rm = pyvisa.ResourceManager()
available_devices = rm.list_resources()
available_devices = [d for d in available_devices if d.startswith("USB")]

# 创建一个字典，将设备地址映射到识别信息
device_info = {}
for addr in available_devices:
    try:
        idn = rm.open_resource(addr).query("*IDN?").strip()
        device_info[idn] = addr
    except Exception as e:
        st.warning(f"无法获取设备 {addr} 的识别信息: {e}")
# 设备多于一个时，选择设备
# 使用设备识别信息在 selectbox 中展示
if len(device_info) == 1:
    device_name = list(device_info.keys())[0]
elif len(device_info) > 1:
    device_name = st.selectbox("选择功率计设备", list(device_info.keys()))
else:
    st.warning("未找到可用的功率计设备")
    device_name = None
device_addr = device_info.get(device_name, None)

if device_addr:  # 选择设备后，尝试连接
    st.session_state.power_meter = rm.open_resource(device_addr)
    st.session_state.power_meter_connected = True
    st.session_state.power_meter.write("SENS:RANGE:AUTO ON")
    st.session_state.power_meter.write("SENS:POW:UNIT W")
    st.session_state.power_meter.write("correction:wavelength 10600")
    st.success(f"已连接到设备：{device_name}")

if st.session_state.power_meter_connected:
    st.header("2. 连接微控制器")
    # choose com port
    ports = serial.tools.list_ports.comports()
    micro_controller_col_1, micro_controller_col_2 = st.columns(2)
    with micro_controller_col_1:
        selected_port = st.selectbox("Select COM port", [p.device for p in ports])

    # connect to microcontroller
    with micro_controller_col_2:
        if st.button("Connect"):
            try:
                st.session_state.micro_controller = serial.Serial(
                    selected_port, 115200, timeout=1
                )
                st.session_state.micro_controller_connected = True
                st.success(f"Connected to {selected_port}")
            except Exception as e:
                st.error(f"Error connecting to {selected_port}: {e}")

    if st.session_state.micro_controller_connected:
        st.header("3. 开环控制")
        # 输入 PWM 频率和占空比
        col_freq, col_duty = st.columns(2)
        with col_freq:
            pwm_freq = st.slider(
                "PWM Frequency (Hz)",
                min_value=1000,
                max_value=100_000,
                step=1000,
                value=10000,
            )
        with col_duty:
            pwm_duty = int(
                st.slider("PWM Duty (%)", min_value=0, max_value=100, value=0)
                * 65535
                / 100
            )
        if st.button("设置 PWM"):
            set_pwm(
                pwm_freq,
                pwm_duty,
                st.session_state.micro_controller,
            )
            st.session_state.current_pwm_duty = pwm_duty
            st.success(f"已设置 PWM 频率 {pwm_freq} Hz 和占空比 {pwm_duty} (u16)")

    st.header("4. 实时功率曲线")
    if st.toggle("读取功率", value=False):
        st.session_state["power_stream"] = True
    else:
        st.session_state["power_stream"] = False

if (
    st.session_state.power_meter_connected
    and st.session_state.micro_controller_connected
):
    st.header("5. 闭环控制")
    # 输入 PID 参数和目标功率
    col_p, col_i, col_d, col_t = st.columns(4)
    with col_p:
        p_gain = st.number_input("P (比例增益)", value=DEFAULT_PID_VALUES[0])
    with col_i:
        i_gain = st.number_input("I (积分增益)", value=DEFAULT_PID_VALUES[1])
    with col_d:
        d_gain = st.number_input("D (微分增益)", value=DEFAULT_PID_VALUES[2])
    with col_t:
        target_power = st.number_input("目标功率 (W)", value=DEFAULT_PID_VALUES[3])

    # 更新 PID 控制器参数
    if st.button("设置 PID 参数"):
        st.session_state.pid_controller.set_pidt((p_gain, i_gain, d_gain, target_power))
        st.success("PID 参数已更新")

    # 添加闭环控制按钮
    if st.toggle("启动闭环控制", value=False):
        st.session_state["closed_loop_running"] = True
    else:
        st.session_state["closed_loop_running"] = False

if st.session_state.power_meter_connected:
    # 初始化图表，只执行一次
    if "fig" not in st.session_state:
        # 创建 matplotlib 图形
        st.session_state["fig"], st.session_state["ax"] = plt.subplots()
        (st.session_state["line"],) = st.session_state["ax"].plot([], [], lw=2)
        st.session_state["ax"].set_xlim(-TIME_RANGE, 0)  # 横轴显示最近 30 秒数据
        st.session_state["ax"].grid()
        st.session_state["ax"].set_xlabel("Time (s)")
        st.session_state["ax"].set_ylabel("Power (W)")

    # 动态读取数据并更新图表
    metric_1, metric_2 = st.columns(2)
    with metric_1:
        closed_loop_duty = st.empty()
    with metric_2:
        closed_loop_power = st.empty()
    power_chart_placeholder = st.empty()
    if st.session_state.get("power_stream", False):
        for _ in range(10**8):  # 无限循环，直到手动停止
            try:
                # 读取功率数据
                power_value = float(
                    st.session_state.power_meter.query("measure:power?").strip()
                )
                current_time = time.time()
                st.session_state["time_list"].append(current_time)
                st.session_state["power_list"].append(power_value)

                # plot length
                plot_length = int(
                    min(len(st.session_state["time_list"]), TIME_RANGE / POWER_INTERVAL)
                )
                plot_time = (
                    np.array(st.session_state["time_list"])[-plot_length:]
                    - current_time
                )
                plot_power = np.array(st.session_state["power_list"])[-plot_length:]
                st.session_state["line"].set_data(plot_time, plot_power)
                st.session_state["ax"].set_ylim(
                    min(plot_power) * 0.9, max(plot_power) * 1.1
                )
                st.session_state["ax"].figure.canvas.draw()
                st.session_state["ax"].figure.canvas.flush_events()
                power_chart_placeholder.pyplot(st.session_state["fig"])

                if st.session_state.get("closed_loop_running", False):
                    # 通过 PID 控制器计算新的占空比
                    new_duty_cycle = (
                        st.session_state.current_pwm_duty
                        + st.session_state.pid_controller.pid(power_value)
                    )
                    new_duty_cycle = max(
                        0, min(65535, new_duty_cycle)
                    )  # 限制占空比范围

                    # 发送占空比到微控制器
                    set_pwm(pwm_freq, new_duty_cycle, st.session_state.micro_controller)

                    # 显示实时数据
                    closed_loop_duty.metric(
                        label="输出占空比",
                        value=f"{new_duty_cycle / 65535 * 100:.2f} %",
                        delta=f"{(new_duty_cycle - st.session_state.current_pwm_duty)/65535 * 100:.2f} %",
                    )
                    closed_loop_power.metric(
                        label="输出功率",
                        value=f"{power_value:.2f} W",
                        delta=f"{(power_value - st.session_state.pid_controller.target):.2f} W",
                    )
                time.sleep(POWER_INTERVAL)  # 控制读取频率

                if not st.session_state.get("power_stream", False):
                    break

            except Exception as e:
                st.error(e)
                break

st.header("6. 保存数据")
if st.session_state.get("time_list") and st.session_state.get("power_list"):
    if st.button("保存本次测量数据"):
        df = pd.DataFrame(
            {
                "Time (s)": st.session_state["time_list"],
                "Power (W)": st.session_state["power_list"],
            }
        )

        # 将数据保存为 pkl 格式到内存中
        buffer = BytesIO()
        df.to_pickle(buffer)
        buffer.seek(0)  # 重置缓冲区的指针

        # 文件名带时间戳
        file_name = f"power_data_{time.strftime('%Y%m%d_%H%M%S')}.pkl"

        # 下载按钮
        st.download_button(
            label="下载数据",
            data=buffer,
            file_name=file_name,
            mime="application/octet-stream",
        )  # 创建保存按钮

st.header("7. 断开连接")
col_disconnect_1, col_disconnect_2 = st.columns(2)
with col_disconnect_1:
    if st.session_state.micro_controller_connected:
        if st.button("微控制器"):
            st.session_state.micro_controller.close()
            st.session_state.micro_controller_connected = False
            st.success(f"Disconnected from {selected_port}")
with col_disconnect_2:
    if st.session_state.power_meter_connected:
        if st.button("功率计"):
            st.session_state.power_meter.close()
            st.session_state.power_meter_connected = False
            st.success(f"Disconnected from {device_name}")
