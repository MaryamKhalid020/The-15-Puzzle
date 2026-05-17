import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import threading
import time
import hashlib
import csv
from collections import deque
from copy import deepcopy

# 1. CORE PROCESS MODEL COMPONENT

class Process:
    def __init__(self, pid, arrival_time, burst_time, priority=0):
        self.pid = pid
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.priority = priority  # Lower value = Higher Urgency

        # Simulation tracking parameters
        self.remaining_time = burst_time
        self.completion_time = 0
        self.turnaround_time = 0
        self.waiting_time = 0
        self.response_time = -1
        self.mlfq_level = 0  # Tracks current queue level inside MLFQ
        # I/O Simulation Variables
        self.process_type = "CPU"      # CPU or IO
        self.cpu_executed = 0          # how much CPU time used
        self.io_frequency = 3          # request IO every 3 ticks
        self.io_duration = 2           # stay blocked for 2 ticks
        self.blocked_until = -1
        self.process_type = "CPU"   # or "IO"
        self.io_frequency = 3
        self.io_duration = 2
        self.blocked_until = -1

    def __repr__(self):
        return f"Process({self.pid}, AT={self.arrival_time}, BT={self.burst_time}, Priority={self.priority})"


# 2. STATE MACHINE SCHEDULER ENGINE WITH DYNAMIC ARCHITECTURE

class SimulatorEngine:
    def __init__(self, process_list, algorithm="Round Robin", time_quantum=3, aging_interval=5):
        self.master_process_list = deepcopy(process_list)
        # Fully Configurable MLFQ Queue Levels Structure Matrix
        self.mlfq_configs = [
            {"type": "RR", "quantum": 4},
            {"type": "RR", "quantum": 8},
            {"type": "FCFS", "quantum": float('inf')}
        ]
        self.reset_simulation(algorithm, time_quantum, aging_interval)

    def reset_simulation(self, algorithm=None, time_quantum=None, aging_interval=None):
        self.processes = deepcopy(self.master_process_list)
        if algorithm: self.algorithm = algorithm
        if time_quantum is not None: self.time_quantum = time_quantum
        if aging_interval is not None: self.aging_interval = aging_interval
        
        self.clock = 0
        self.gantt_chart = []
        self.completion_order = []
        self.current_running_process = None
        self.context_switches = 0
        
        # Explicit Ready Queues Structures
        self.fifo_ready_queue = deque()
        self.mlfq_queues = [deque() for _ in self.mlfq_configs]
        self.blocked_queue = []
        self.tracked_arrivals = set()

        self.rr_quantum_left = self.time_quantum
        self.mlfq_quantum_left = self.mlfq_configs[0]["quantum"] if self.mlfq_configs else 0
        
        self.last_aging_time = {p.pid: p.arrival_time for p in self.processes}
        self.prev_pid_segment = None
        self.segment_start_time = 0

    def add_process_dynamic(self, pid, arrival_time, burst_time, priority=0):
        if arrival_time < self.clock: arrival_time = self.clock 
        
        new_p = Process(pid, arrival_time, burst_time, priority)
        self.master_process_list.append(deepcopy(new_p))
        self.processes.append(new_p)
        self.last_aging_time[new_p.pid] = new_p.arrival_time

    def modify_process_live(self, pid, new_at, new_bt, new_priority):
        """FIXED: Allows live runtime modification of arrival times alongside BT and Priority."""
        for p in self.processes:
            if p.pid == pid and p.remaining_time > 0:
                # If changing arrival time of a process currently running on CPU, reject to maintain state integrity
                if self.current_running_process and self.current_running_process.pid == pid:
                    return False
                
                diff = new_bt - p.burst_time
                p.burst_time = new_bt
                p.remaining_time = max(1, p.remaining_time + diff)
                p.priority = new_priority
                
                old_at = p.arrival_time
                p.arrival_time = new_at
                
                # Edge Case Handling: If it was tracking in a queue, check if it needs to be repositioned
                if p.pid in self.tracked_arrivals and p.arrival_time > self.clock:
                    # Moved to the future: pull out of immediate queues
                    self.tracked_arrivals.remove(p.pid)
                    if p in self.fifo_ready_queue: self.fifo_ready_queue.remove(p)
                    for q in self.mlfq_queues:
                        if p in q: q.remove(p)
                elif p.pid not in self.tracked_arrivals and p.arrival_time <= self.clock:
                    # Moved into the past/present: trigger execution processing capture loops on the very next tick
                    pass 
                return True
        return False

    def remove_process_live(self, pid):
        target = None
        for p in self.processes:
            if p.pid == pid and p.remaining_time > 0:
                if self.current_running_process and self.current_running_process.pid == pid:
                    return False
                target = p
                break
                
        if target:
            target.remaining_time = 0  
            if target in self.fifo_ready_queue: self.fifo_ready_queue.remove(target)
            for q in self.mlfq_queues:
                if target in q: q.remove(target)
            return True
        return False

    def get_ready_processes_pool(self):
        return [p for p in self.processes if p.arrival_time <= self.clock and p.remaining_time > 0]

    def _apply_priority_aging(self, ready_pool):
        for p in ready_pool:
            if self.current_running_process and p.pid == self.current_running_process.pid:
                continue
            time_spent_waiting = self.clock - self.last_aging_time.get(p.pid, p.arrival_time)
            if time_spent_waiting >= self.aging_interval and p.priority > 0:
                p.priority -= 1
                self.last_aging_time[p.pid] = self.clock

    def _update_gantt_chart(self, active_pid):
        if active_pid != self.prev_pid_segment:
            if self.prev_pid_segment is not None:
                label = "Idle" if self.prev_pid_segment == "Idle" else self.prev_pid_segment
                self.gantt_chart.append(f"{label}({self.segment_start_time}-{self.clock})")
                if label != "Idle" and active_pid != "Idle":
                    self.context_switches += 1
            self.segment_start_time = self.clock
            self.prev_pid_segment = active_pid

    def _handle_new_arrivals(self):
        new_arrivals = sorted(
            [p for p in self.processes if p.arrival_time <= self.clock and p.remaining_time > 0 and p.pid not in self.tracked_arrivals],
            key=lambda p: (p.arrival_time, p.pid)
        )
        for p in new_arrivals:
            self.fifo_ready_queue.append(p)
            # Ensure index safety constraints if queues are changed dynamically
            lvl = min(p.mlfq_level, len(self.mlfq_configs) - 1)
            p.mlfq_level = lvl
            self.mlfq_queues[lvl].append(p)
            self.tracked_arrivals.add(p.pid)

    def step_one_tick(self):
        incomplete_processes = [p for p in self.processes if p.remaining_time > 0]
        # Check blocked processes
        for p in self.blocked_queue[:]:
            if self.clock >= p.blocked_until:
                self.blocked_queue.remove(p)
        
                if self.algorithm == "MLFQ":
                    lvl = min(p.mlfq_level, len(self.mlfq_configs)-1)
                    self.mlfq_queues[lvl].append(p)
        
                else:
                    self.fifo_ready_queue.append(p)

        if not incomplete_processes:
            if self.prev_pid_segment is not None:
                label = "Idle" if self.prev_pid_segment == "Idle" else self.prev_pid_segment
                self.gantt_chart.append(f"{label}({self.segment_start_time}-{self.clock})")
                self.prev_pid_segment = None
            return False

        if self.algorithm in ["Round Robin", "MLFQ"]:
            self._handle_new_arrivals()
            
           
            # Round Robin Engine
           
            if self.algorithm == "Round Robin":
                if self.current_running_process and self.current_running_process.remaining_time > 0 and self.rr_quantum_left == 0:
                    self.fifo_ready_queue.append(self.current_running_process)
                    self.current_running_process = None

                if not self.current_running_process or self.current_running_process.remaining_time == 0:
                    if self.fifo_ready_queue:
                        self.current_running_process = self.fifo_ready_queue.popleft()
                        self.rr_quantum_left = self.time_quantum
                    else:
                        self.current_running_process = None

                if not self.current_running_process:
                    self._update_gantt_chart("Idle")
                    self.clock += 1
                    return True

                self.rr_quantum_left -= 1

            # Multilevel Feedback Queue (MLFQ) Engine
          
            elif self.algorithm == "MLFQ":
                current_q_limit = len(self.mlfq_configs)
                
                # Check quantum expiration based on the process's active tier level config
                if self.current_running_process and self.current_running_process.remaining_time > 0 and self.mlfq_quantum_left == 0:
                    current_level = self.current_running_process.mlfq_level
                    if current_level < current_q_limit - 1:
                        self.current_running_process.mlfq_level += 1
                    
                    target_lvl = min(self.current_running_process.mlfq_level, current_q_limit - 1)
                    self.mlfq_queues[target_lvl].append(self.current_running_process)
                    self.current_running_process = None

                highest_available_level = -1
                for lvl in range(current_q_limit):
                    if self.mlfq_queues[lvl]:
                        highest_available_level = lvl
                        break

                if self.current_running_process and self.current_running_process.remaining_time > 0 and highest_available_level != -1:
                    if highest_available_level < self.current_running_process.mlfq_level:
                        target_lvl = min(self.current_running_process.mlfq_level, current_q_limit - 1)
                        self.mlfq_queues[target_lvl].append(self.current_running_process)
                        self.current_running_process = None

                if not self.current_running_process or self.current_running_process.remaining_time == 0:
                    if highest_available_level != -1:
                        self.current_running_process = self.mlfq_queues[highest_available_level].popleft()
                        q_type = self.mlfq_configs[highest_available_level]["type"]
                        self.mlfq_quantum_left = (self.mlfq_configs[highest_available_level]["quantum"] 
                                                  if q_type == "RR" else float('inf'))
                    else:
                        self.current_running_process = None

                if not self.current_running_process:
                    self._update_gantt_chart("Idle")
                    self.clock += 1
                    return True

                if self.mlfq_quantum_left != float('inf'):
                    self.mlfq_quantum_left -= 1

        else:
            ready_pool = self.get_ready_processes_pool()
            if not ready_pool:
                self._update_gantt_chart("Idle")
                self.current_running_process = None
                self.clock += 1
                return True

            if self.algorithm == "FCFS":
                ready_pool.sort(key=lambda p: p.arrival_time)
                self.current_running_process = ready_pool[0]

            elif self.algorithm == "SJF":
                if self.current_running_process and self.current_running_process.remaining_time > 0:
                    pass
                else:
                    ready_pool.sort(key=lambda p: (p.burst_time, p.arrival_time))
                    self.current_running_process = ready_pool[0]

            elif self.algorithm == "SRTF":
                ready_pool.sort(key=lambda p: (p.remaining_time, p.arrival_time))
                self.current_running_process = ready_pool[0]

            elif self.algorithm == "Priority Non-Preemptive":
                self._apply_priority_aging(ready_pool)
                if self.current_running_process and self.current_running_process.remaining_time > 0:
                    pass
                else:
                    ready_pool.sort(key=lambda p: (p.priority, p.arrival_time))
                    self.current_running_process = ready_pool[0]

            elif self.algorithm == "Priority Preemptive":
                self._apply_priority_aging(ready_pool)
                ready_pool.sort(key=lambda p: (p.priority, p.arrival_time))
                self.current_running_process = ready_pool[0]

        p = self.current_running_process
        if p.response_time == -1:
            p.response_time = self.clock - p.arrival_time

        self._update_gantt_chart(p.pid)
        p.remaining_time -= 1
        # Track CPU usage
        p.cpu_executed += 1
        
        # Simulate I/O request
        if (
            p.process_type == "IO"
            and p.remaining_time > 0
            and p.cpu_executed % p.io_frequency == 0
        ):
            p.blocked_until = self.clock + p.io_duration
            self.blocked_queue.append(p)
            self.current_running_process = None
        self.clock += 1

        if p.remaining_time == 0:
            p.completion_time = self.clock
            self.completion_order.append(p.pid)

        return True


# 3. ADAPTIVE LOGIC EXPERT SYSTEM MODULE

class AdaptiveFeedbackAdvisor:
    @staticmethod
    def analyze_workload_and_recommend(engine):
        incomplete = [p for p in engine.processes if p.remaining_time > 0]
        ready_pool = [p for p in engine.processes if p.arrival_time <= engine.clock and p.remaining_time > 0]
        
        if not incomplete:
            return "FCFS", "No demanding process threads located. Standard baseline strategy applied."

        bursts = [p.remaining_time for p in incomplete]
        avg_burst = sum(bursts) / len(bursts)
        variance = sum((b - avg_burst) ** 2 for b in bursts) / len(bursts) if len(bursts) > 0 else 0
        
        starvation_flag = False
        for p in ready_pool:
            if engine.current_running_process and p.pid == engine.current_running_process.pid:
                continue
            if (engine.clock - p.arrival_time) >= 18:
                starvation_flag = True
                break

        if starvation_flag:
            return "MLFQ", "CRITICAL STATE: High starvation detected. MLFQ scheduling is recommended to protect low-priority processes."
        if variance > 16.0:
            return "SRTF", f"WORKLOAD PROFILE: High variance detected ({round(variance, 1)}). SRTF will minimize Average Waiting Time."
        if len(ready_pool) > 4 and variance <= 4.0:
            return "FCFS", f"WORKLOAD PROFILE: Homogeneous load detected ({round(variance, 1)}). FCFS avoids context-switch penalties."
        return "Round Robin", "WORKLOAD PROFILE: Stable mixed load. Round Robin ensures fair time slice distribution."


# 4. INTERACTIVE ANALYTICAL UI DASHBOARD FRAMEWORK

class SimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Interactive CPU Scheduling Simulator Workbench")
        self.root.geometry("1260x890")
        self.root.configure(bg="#222222")
        self.dark_mode = True

        # Core Initial Dataset Configuration
        self.initial_batch = [
            Process("P1", 0, 8, priority=3),
            Process("P2", 2, 4, priority=1),
            Process("P3", 4, 9, priority=4),
            Process("P4", 5, 5, priority=2),
        ]
        # Mark some processes as I/O-bound
        self.initial_batch[1].process_type = "IO"
        self.initial_batch[3].process_type = "IO"
        self.engine = SimulatorEngine(self.initial_batch, algorithm="Round Robin")

        self.is_running = False
        self.simulation_thread = None
        self.simulation_speed = 1.0
        self.latest_recommendation = "Round Robin"

        self.setup_styles()
        self.create_control_panel()
        self.create_mlfq_modular_config_panel()  # FIXED: Expanded completely customizable layer panel frame housing
        self.create_status_and_metrics_and_adaptive_panel()
        self.create_ready_queue_and_completion_row()
        self.create_gantt_canvas_panel()
        self.create_table_view()

        self.update_ui_state()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=26)
        style.map("Treeview", background=[("selected", "#007acc")])
        
        self.tree_colors = {
            "running": {"bg": "#133c15", "fg": "#8be991"},
            "waiting": {"bg": "#443403", "fg": "#fadb66"},
            "completed": {"bg": "#1f1f1f", "fg": "#777777"},
            "future": {"bg": "#102a45", "fg": "#82b3e8"}
        }

    def get_process_color(self, pid):
        if pid == "Idle": return "#1a1a1a"
        sha = hashlib.sha256(pid.encode('utf-8')).hexdigest()
        r = int(sha[0:2], 16) % 120 + 30
        g = int(sha[2:4], 16) % 120 + 30
        b = int(sha[4:6], 16) % 120 + 30
        return f"#{r:02x}{g:02x}{b:02x}"

    def create_control_panel(self):
        control_frame = tk.LabelFrame(self.root, text="System Global Parameters", fg="white", bg="#222222", font=("Helvetica", 10, "bold"))
        control_frame.pack(fill="x", padx=15, pady=4)

        left_sub = tk.Frame(control_frame, bg="#222222")
        left_sub.pack(side="left", fill="y", padx=10)

        tk.Label(left_sub, text="Algorithm:", fg="white", bg="#222222").grid(row=0, column=0, padx=2, pady=3, sticky="e")
        self.algo_var = tk.StringVar(value="Round Robin")
        self.algo_menu = ttk.Combobox(left_sub, textvariable=self.algo_var, state="readonly", width=15)
        self.algo_menu['values'] = ("FCFS", "SJF", "SRTF", "Priority Non-Preemptive", "Priority Preemptive", "Round Robin", "MLFQ")
        self.algo_menu.grid(row=0, column=1, padx=4, pady=3)
        self.algo_menu.bind("<<ComboboxSelected>>", self.on_algorithm_change)

        tk.Label(left_sub, text="RR Quantum:", fg="white", bg="#222222").grid(row=0, column=2, padx=4, pady=3, sticky="e")
        self.entry_quantum = tk.Entry(left_sub, width=3, bg="#333333", fg="white", insertbackground="white")
        self.entry_quantum.grid(row=0, column=3, padx=2, pady=3)
        self.entry_quantum.insert(0, "3")

        tk.Label(left_sub, text="Aging Int:", fg="white", bg="#222222").grid(row=0, column=4, padx=4, pady=3, sticky="e")
        self.entry_aging = tk.Entry(left_sub, width=3, bg="#333333", fg="white", insertbackground="white")
        self.entry_aging.grid(row=0, column=5, padx=2, pady=3)
        self.entry_aging.insert(0, "5")

        self.btn_start_pause = tk.Button(left_sub, text="▶ Start", bg="#218838", fg="white", font=("Helvetica", 8, "bold"), width=7, command=self.toggle_simulation)
        self.btn_start_pause.grid(row=1, column=0, padx=2, pady=3)

        btn_reset = tk.Button(left_sub, text="🔄 Reset", bg="#c82333", fg="white", font=("Helvetica", 8, "bold"), width=7, command=self.reset_simulation)
        btn_reset.grid(row=1, column=1, padx=2, pady=3)

        btn_compare = tk.Button(left_sub, text="📊 Compare All", bg="#6f42c1", fg="white", font=("Helvetica", 8, "bold"), width=11, command=self.open_comparison_workspace)
        btn_compare.grid(row=1, column=2, columnspan=2, padx=2, pady=3)

        btn_export = tk.Button(left_sub, text="💾 Export", bg="#e0a800", fg="#111111", font=("Helvetica", 8, "bold"), width=7, command=self.export_to_csv)
        btn_export.grid(row=1, column=4, padx=2, pady=3)

        tk.Label(left_sub, text="Speed Delay:", fg="white", bg="#222222").grid(row=1, column=5, padx=2, pady=3, sticky="e")
        self.speed_slider = tk.Scale(left_sub, from_=0.1, to=2.0, resolution=0.1, orient="horizontal", showvalue=False, bg="#222222", fg="white", length=110, command=self.update_speed)
        self.speed_slider.set(1.0)
        self.speed_slider.grid(row=1, column=6, columnspan=3, padx=2, pady=0)

        right_sub = tk.LabelFrame(control_frame, text="Process Context Management Operations", fg="#00ffcc", bg="#222222", font=("Helvetica", 9, "bold"))
        right_sub.pack(side="right", fill="both", expand=True, padx=10, pady=2)

        tk.Label(right_sub, text="PID:", fg="white", bg="#222222").grid(row=0, column=0, padx=2, pady=2)
        self.entry_pid = tk.Entry(right_sub, width=4, bg="#333333", fg="white", insertbackground="white")
        self.entry_pid.grid(row=0, column=1, padx=2, pady=2)
        self.entry_pid.insert(0, "P5")

        tk.Label(right_sub, text="AT:", fg="white", bg="#222222").grid(row=0, column=2, padx=2, pady=2)
        self.entry_at = tk.Entry(right_sub, width=3, bg="#333333", fg="white", insertbackground="white")
        self.entry_at.grid(row=0, column=3, padx=2, pady=2)
        self.entry_at.insert(0, "0")

        tk.Label(right_sub, text="BT:", fg="white", bg="#222222").grid(row=0, column=4, padx=2, pady=2)
        self.entry_bt = tk.Entry(right_sub, width=3, bg="#333333", fg="white", insertbackground="white")
        self.entry_bt.grid(row=0, column=5, padx=2, pady=2)
        self.entry_bt.insert(0, "4")

        tk.Label(right_sub, text="PR:", fg="white", bg="#222222").grid(row=0, column=6, padx=2, pady=2)
        self.entry_pr = tk.Entry(right_sub, width=3, bg="#333333", fg="white", insertbackground="white")
        self.entry_pr.grid(row=0, column=7, padx=2, pady=2)
        self.entry_pr.insert(0, "2")

        tk.Button(right_sub, text="➕ Add", bg="#138496", fg="white", font=("Helvetica", 8, "bold"), width=6, command=self.inject_process).grid(row=0, column=8, padx=2)
        tk.Button(right_sub, text="✏️ Modify", bg="#0069d9", fg="white", font=("Helvetica", 8, "bold"), width=6, command=self.modify_process).grid(row=0, column=9, padx=2)
        tk.Button(right_sub, text="❌ Remove", bg="#a04040", fg="white", font=("Helvetica", 8, "bold"), width=6, command=self.remove_process).grid(row=0, column=10, padx=2)
        tk.Button(
                left_sub,
                text="Theme",
                bg="#444444",
                fg="white",
                font=("Helvetica", 8, "bold"),
                command=self.toggle_theme
            ).grid(row=1, column=9, padx=10 ,sticky="w")
    def create_mlfq_modular_config_panel(self):
        """FIXED: Creates a fully customizable MLFQ panel where queue levels and scheduling types can be added dynamically."""
        self.mlfq_panel = tk.LabelFrame(self.root, text="Fully Configurable MLFQ Queue Layer Pipeline Management", fg="#ffaa00", bg="#222222", font=("Helvetica", 9, "bold"))
        self.mlfq_panel.pack(fill="x", padx=15, pady=4)

        container = tk.Frame(self.mlfq_panel, bg="#222222")
        container.pack(fill="x", padx=10, pady=5)

        tk.Label(container, text="Queue Configurator Matrix:", fg="white", bg="#222222", font=("Helvetica", 8, "bold")).pack(side="left", padx=5)

        # Dropdown selection to adjust layer level counts
        tk.Label(container, text="Levels:", fg="#cccccc", bg="#222222").pack(side="left", padx=2)
        self.mlfq_levels_var = tk.StringVar(value="3")
        spin = ttk.Spinbox(container, from_=1, to=5, width=3, textvariable=self.mlfq_levels_var, command=self.sync_mlfq_gui_rows)
        spin.pack(side="left", padx=5)

        self.rows_frame = tk.Frame(self.mlfq_panel, bg="#222222")
        self.rows_frame.pack(fill="x", padx=10, pady=5)

        self.queue_ui_elements = []
        self.sync_mlfq_gui_rows()

    def sync_mlfq_gui_rows(self):
        """Dynamically builds input selector blocks for every designated MLFQ sub-queue level layer."""
        for f in self.rows_frame.winfo_children():
            f.destroy()
        self.queue_ui_elements.clear()

        try:
            target_count = int(self.mlfq_levels_var.get())
        except ValueError:
            target_count = 3

        # Default standard presets initialization handles context routing cleanly
        presets = [
            {"type": "RR", "quantum": "4"},
            {"type": "RR", "quantum": "8"},
            {"type": "FCFS", "quantum": "INF"},
            {"type": "FCFS", "quantum": "INF"},
            {"type": "FCFS", "quantum": "INF"}
        ]

        for i in range(target_count):
            row_frame = tk.Frame(self.rows_frame, bg="#2d2d2d", relief="groove", bd=1)
            row_frame.pack(side="left", padx=6, pady=2, fill="y")

            tk.Label(row_frame, text=f"Q{i}:", fg="#ffaa00", bg="#2d2d2d", font=("Helvetica", 8, "bold")).grid(row=0, column=0, padx=4, pady=4)
            
            type_var = tk.StringVar(value=presets[i]["type"])
            cmb = ttk.Combobox(row_frame, textvariable=type_var, values=("RR", "FCFS"), state="readonly", width=5)
            cmb.grid(row=0, column=1, padx=4, pady=4)

            tk.Label(row_frame, text="Quantum:", fg="white", bg="#2d2d2d", font=("Helvetica", 7)).grid(row=0, column=2, padx=2)
            ent_q = tk.Entry(row_frame, width=3, bg="#444444", fg="white", insertbackground="white")
            ent_q.insert(0, presets[i]["quantum"])
            ent_q.grid(row=0, column=3, padx=4, pady=4)

            # Bind dropdown event triggers to automatically mute the quantum field if FCFS is selected
            def toggle_ent(e, ent=ent_q, tv=type_var):
                if tv.get() == "FCFS":
                    ent.delete(0, tk.END)
                    ent.insert(0, "INF")
                    ent.config(state="disabled")
                else:
                    ent.config(state="normal")
                    ent.delete(0, tk.END)
                    ent.insert(0, "4")

            cmb.bind("<<ComboboxSelected>>", toggle_ent)
            if presets[i]["type"] == "FCFS": ent_q.config(state="disabled")

            self.queue_ui_elements.append({"type_var": type_var, "entry_q": ent_q})

    def read_mlfq_gui_configurations(self):
        """Parses the dynamically generated UI fields into engine configuration parameters."""
        new_configs = []
        try:
            for idx, el in enumerate(self.queue_ui_elements):
                q_type = el["type_var"].get()
                if q_type == "FCFS":
                    new_configs.append({"type": "FCFS", "quantum": float('inf')})
                else:
                    val = int(el["entry_q"].get())
                    if val <= 0: raise ValueError
                    new_configs.append({"type": "RR", "quantum": val})
            return new_configs
        except ValueError:
            messagebox.showerror("MLFQ Parameter Error", "MLFQ sub-queue quantum entries must be positive integers.")
            return None

    def create_status_and_metrics_and_adaptive_panel(self):
        dashboard_frame = tk.Frame(self.root, bg="#222222")
        dashboard_frame.pack(fill="x", padx=15, pady=2)

        state_container = tk.Frame(dashboard_frame, bg="#222222")
        state_container.pack(side="left")

        self.lbl_clock = tk.Label(state_container, text="System Clock: 0", fg="#00ff00", bg="#151515", font=("Consolas", 11, "bold"), width=16, anchor="w", padx=8, pady=4)
        self.lbl_clock.pack(anchor="w", pady=1)

        self.lbl_running_proc = tk.Label(state_container, text="CPU State: IDLE", fg="#ffcc00", bg="#151515", font=("Consolas", 11, "bold"), width=22, anchor="w", padx=8, pady=4)
        self.lbl_running_proc.pack(anchor="w", pady=1)

        metrics_container = tk.LabelFrame(dashboard_frame, text="Performance Telemetry Indicators", fg="white", bg="#222222", font=("Helvetica", 9, "bold"))
        metrics_container.pack(side="left", fill="both", padx=10)

        metric_labels_config = [
            ("Avg WT:", "0.00", 0, 0), ("Avg TAT:", "0.00", 0, 2),
            ("CPU Util:", "0.0 %", 1, 0), ("Throughput:", "0.000", 1, 2),
            ("Ctx Switches:", "0", 0, 4)
        ]
        
        self.metric_vars = {}
        for text, default, row, col in metric_labels_config:
            tk.Label(metrics_container, text=text, fg="#aaaaaa", bg="#222222", font=("Helvetica", 8, "bold")).grid(row=row, column=col, padx=4, pady=1, sticky="e")
            v = tk.StringVar(value=default)
            lbl = tk.Label(metrics_container, textvariable=v, fg="white", bg="#151515", font=("Consolas", 9, "bold"), width=8, relief="sunken")
            lbl.grid(row=row, column=col+1, padx=2, pady=1, sticky="w")
            self.metric_vars[text] = v

        adaptive_container = tk.LabelFrame(dashboard_frame, text="Adaptive Optimization Layer Feedback", fg="#00ffcc", bg="#222222", font=("Helvetica", 9, "bold"))
        adaptive_container.pack(side="right", fill="both", expand=True, padx=10)

        top_bar = tk.Frame(adaptive_container, bg="#222222")
        top_bar.pack(fill="x", padx=5, pady=2)

        self.lbl_adaptive_recommendation = tk.Label(top_bar, text="Adaptive Recommendation: Checking...", fg="#00ffcc", bg="#111111", font=("Helvetica", 9, "bold"), anchor="w", padx=5)
        self.lbl_adaptive_recommendation.pack(side="left", fill="x", expand=True)

        self.btn_apply_rec = tk.Button(top_bar, text="Apply Recommendation", bg="#17a2b8", fg="white", font=("Helvetica", 8, "bold"), padx=5, command=self.manually_apply_recommendation)
        self.btn_apply_rec.pack(side="right", padx=5)

        self.ai_auto_adopt_var = tk.BooleanVar(value=False)
        self.chk_auto_adopt = tk.Checkbutton(top_bar, text="Auto-Adopt Strategy", variable=self.ai_auto_adopt_var, fg="#00ffcc", bg="#222222", selectcolor="#111111", activebackground="#222222", activeforeground="#00ffcc", font=("Helvetica", 8, "bold"))
        self.chk_auto_adopt.pack(side="right", padx=5)

        self.txt_ai_reasoning = tk.Text(adaptive_container, height=2, bg="#111111", fg="#cccccc", font=("Consolas", 8), bd=0, padx=5, pady=1)
        self.txt_ai_reasoning.pack(fill="both", expand=True, padx=5, pady=1)
        self.txt_ai_reasoning.insert("1.0", "Analyzing workload requirements queue metrics maps context...")

    def create_ready_queue_and_completion_row(self):
        row_frame = tk.Frame(self.root, bg="#222222")
        row_frame.pack(fill="x", padx=15, pady=2)

        self.lbl_ready_queue = tk.Label(row_frame, text="Ready Queue: [ Empty ]", fg="#00ffcc", bg="#1a1a1a", font=("Consolas", 10, "bold"), anchor="w", padx=10, pady=4, relief="ridge")
        self.lbl_ready_queue.pack(fill="x", pady=1)

        self.lbl_completion_order = tk.Label(row_frame, text="Completion Order: [ None ]", fg="#ffaa00", bg="#1a1a1a", font=("Consolas", 10, "bold"), anchor="w", padx=10, pady=4, relief="ridge")
        self.lbl_completion_order.pack(fill="x", pady=1)

    def create_gantt_canvas_panel(self):
        gantt_frame = tk.LabelFrame(self.root, text="Dynamic Canvas Gantt Chart Progression Timeline View", fg="white", bg="#222222", font=("Helvetica", 10, "bold"))
        gantt_frame.pack(fill="x", padx=15, pady=4)

        hbar = tk.Scrollbar(gantt_frame, orient="horizontal")
        hbar.pack(side="bottom", fill="x")

        self.gantt_canvas = tk.Canvas(gantt_frame, height=65, bg="#111111", highlightthickness=0, xscrollcommand=hbar.set)
        self.gantt_canvas.pack(fill="x", padx=5, pady=2)
        hbar.config(command=self.gantt_canvas.xview)

        self.block_width_per_tick = 22
        self.block_height = 36
        self.start_y_offset = 10

    def create_table_view(self):
        table_frame = tk.LabelFrame(self.root, text="Process Context Telemetry Database Viewer Frame Sheet", fg="white", bg="#222222", font=("Helvetica", 10, "bold"))
        table_frame.pack(fill="both", expand=True, padx=15, pady=4)

        tree_scroll_y = tk.Scrollbar(table_frame, orient="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        
        tree_scroll_x = tk.Scrollbar(table_frame, orient="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        columns = ("pid", "at", "bt", "pr", "remaining", "ct", "tat", "wt", "rt")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        headers = {"pid": "PID", "at": "Arrival Time", "bt": "Burst Time", "pr": "Priority", "remaining": "Remaining Time", "ct": "CT", "tat": "TAT", "wt": "WT", "rt": "RT"}
        for col, txt in headers.items():
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=120, anchor="center")

        for tag_name, colors in self.tree_colors.items():
            self.tree.tag_configure(tag_name, background=colors["bg"], foreground=colors["fg"])

        self.tree.pack(fill="both", expand=True, padx=5, pady=2)
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select_populate)

    def validate_inputs(self, check_quantum=False, check_pid_exists=False):
        try:
            pid = self.entry_pid.get().strip()
            if not pid:
                messagebox.showerror("Validation Error", "Process ID field cannot be blank.")
                return None
            at = int(self.entry_at.get())
            if at < 0:
                messagebox.showerror("Validation Error", "Arrival Time cannot represent negative thresholds.")
                return None
            bt = int(self.entry_bt.get())
            if bt <= 0:
                messagebox.showerror("Validation Error", "Burst time requirements must exceed absolute zero.")
                return None
            pr = int(self.entry_pr.get())
            if pr < 0:
                messagebox.showerror("Validation Error", "Priority attributes cannot represent negative index metrics.")
                return None
            
            q = int(self.entry_quantum.get())
            aging = int(self.entry_aging.get())
            if q <= 0 or aging <= 0:
                messagebox.showerror("Validation Error", "Time Quantum and Aging Interval inputs must exceed absolute zero.")
                return None

            if check_pid_exists:
                if any(p.pid == pid for p in self.engine.processes if p.remaining_time > 0):
                    messagebox.showerror("Validation Error", "Duplicate Process ID detected inside the active registers.")
                    return None

            return pid, at, bt, pr
        except ValueError:
            messagebox.showerror("Validation Error", "Verify format inputs. Fields require valid integers.")
            return None

    def toggle_simulation(self):
        if self.is_running:
            self.is_running = False
            self.btn_start_pause.config(text="▶ Resume", bg="#218838")
        else:
            try:
                q = int(self.entry_quantum.get())
                aging = int(self.entry_aging.get())
                if q <= 0 or aging <= 0: raise ValueError
                
                # Fetch dynamically customized modular MLFQ settings fields on startup block trigger
                mlfq_res = self.read_mlfq_gui_configurations()
                if mlfq_res is None: return
                
                self.engine.time_quantum = q
                self.engine.aging_interval = aging
                self.engine.mlfq_configs = mlfq_res

            except ValueError:
                messagebox.showerror("Configuration Error", "Verify runtime allocation fields are positive non-zero integers.")
                return

            self.is_running = True
            self.btn_start_pause.config(text="⏸ Pause", bg="#e0a800")
            
            if self.simulation_thread is None or not self.simulation_thread.is_alive():
                self.simulation_thread = threading.Thread(target=self.simulation_worker_loop, daemon=True)
                self.simulation_thread.start()

    def simulation_worker_loop(self):
        while self.is_running:
            self.root.after(0, self.evaluate_intelligence_layer_recommendations)
            work_remaining = self.engine.step_one_tick()
            self.root.after(0, self.update_ui_state)
            
            if not work_remaining:
                self.is_running = False
                self.root.after(0, self.simulation_finished_notification)
                break
            time.sleep(self.simulation_speed)

    def update_speed(self, val):
        self.simulation_speed = float(val)

    def evaluate_intelligence_layer_recommendations(self):
        rec_algo, reasoning_txt = AdaptiveFeedbackAdvisor.analyze_workload_and_recommend(self.engine)
        self.latest_recommendation = rec_algo
        
        self.lbl_adaptive_recommendation.config(text=f"Adaptive Recommendation: {rec_algo}")
        self.txt_ai_reasoning.config(state="normal")
        self.txt_ai_reasoning.delete("1.0", tk.END)
        self.txt_ai_reasoning.insert("1.0", reasoning_txt)
        self.txt_ai_reasoning.config(state="disabled")

        if self.ai_auto_adopt_var.get() and self.engine.algorithm != rec_algo:
            self.apply_target_algorithm(rec_algo)

    def manually_apply_recommendation(self):
        if self.engine.algorithm == self.latest_recommendation:
            messagebox.showinfo("Adaptive Layer", f"System is already utilizing recommended strategy: {self.latest_recommendation}")
            return
        self.apply_target_algorithm(self.latest_recommendation)
        self.update_ui_state()
        messagebox.showinfo("Adaptive Layer Success", f"Successfully swapped execution context to: {self.latest_recommendation}")

    def apply_target_algorithm(self, target_algo):
        self.engine.algorithm = target_algo
        self.algo_var.set(target_algo)
        self.engine.rr_quantum_left = self.engine.time_quantum
        self.engine.mlfq_quantum_left = self.engine.mlfq_configs[0]["quantum"] if self.engine.mlfq_configs else 0

    def open_comparison_workspace(self):
        if not self.engine.master_process_list:
            messagebox.showerror("Error", "No process dataset found to execute comparison runs against.")
            return

        mlfq_res = self.read_mlfq_gui_configurations()
        if mlfq_res is None: return

        comparison_window = tk.Toplevel(self.root)
        comparison_window.title("Analytical Performance Evaluation Workloads Matrix")
        comparison_window.geometry("720x400")
        comparison_window.configure(bg="#1a1a1a")

        tk.Label(comparison_window, text="Comparative Analysis Framework Matrix", fg="#00ffcc", bg="#1a1a1a", font=("Helvetica", 12, "bold")).pack(pady=10)

        cols = ("algo", "avg_wt", "avg_tat", "ctx_switches", "util")
        tbl = ttk.Treeview(comparison_window, columns=cols, show="headings", height=8)
        tbl.heading("algo", text="Scheduling Strategy")
        tbl.heading("avg_wt", text="Avg Waiting Time")
        tbl.heading("avg_tat", text="Avg Turnaround Time")
        tbl.heading("ctx_switches", text="Context Switches")
        tbl.heading("util", text="CPU Utilization")

        for c in cols: tbl.column(c, width=135, anchor="center")
        tbl.pack(fill="both", expand=True, padx=20, pady=10)

        target_algos = ["FCFS", "SJF", "SRTF", "Priority Non-Preemptive", "Priority Preemptive", "Round Robin", "MLFQ"]
        
        for algo in target_algos:
            sandbox = SimulatorEngine(self.engine.master_process_list, algorithm=algo, time_quantum=self.engine.time_quantum, aging_interval=self.engine.aging_interval)
            sandbox.mlfq_configs = deepcopy(mlfq_res)
            sandbox.mlfq_quantum_left = mlfq_res[0]["quantum"] if mlfq_res else 0
            
            while sandbox.step_one_tick(): pass

            total_wt, total_tat = 0, 0
            n = len(sandbox.processes)
            for p in sandbox.processes:
                tat = p.completion_time - p.arrival_time
                wt = tat - p.burst_time
                total_tat += tat
                total_wt += wt

            first_arr = min(p.arrival_time for p in sandbox.processes)
            span = sandbox.clock - first_arr
            
            idle_duration = 0
            for entry in sandbox.gantt_chart:
                if entry.startswith("Idle"):
                    time_part = entry[entry.find("(") + 1 : entry.find(")")]
                    start, end = map(int, time_part.split("-"))
                    idle_duration += end - start

            cpu_util = ((span - idle_duration) / span) * 100 if span > 0 else 0
            
            tbl.insert("", "end", values=(
                algo, f"{round(total_wt / n, 2):.2f}", f"{round(total_tat / n, 2):.2f}",
                sandbox.context_switches, f"{round(cpu_util, 1):.1f} %"
            ))

    def update_ui_state(self):
        self.lbl_clock.config(text=f"System Clock: {self.engine.clock}")
        active_proc = self.engine.current_running_process
        if active_proc:
            self.lbl_running_proc.config(text=f"CPU State: RUNNING ({active_proc.pid})", fg="#85e68d")
        else:
            self.lbl_running_proc.config(text="CPU State: IDLE", fg="#ffe066")

        if self.engine.algorithm == "Round Robin":
            q_list = [p.pid for p in self.engine.fifo_ready_queue]
            self.lbl_ready_queue.config(text=f"Ready Queue (FIFO): [ {', '.join(q_list) if q_list else 'Empty'} ]")
        elif self.engine.algorithm == "MLFQ":
            levels_desc = []
            for idx, q in enumerate(self.engine.mlfq_queues):
                pids = [p.pid for p in q]
                levels_desc.append(f"Q{idx}:({', '.join(pids) if pids else 'Empty'})")
            self.lbl_ready_queue.config(text=f"MLFQ Layers Status -> {' | '.join(levels_desc)}")
        else:
            pool = [p.pid for p in self.engine.get_ready_processes_pool()]
            self.lbl_ready_queue.config(text=f"Ready Pool Context: [ {', '.join(pool) if pool else 'Empty'} ]")

        if self.engine.completion_order:
            self.lbl_completion_order.config(text=f"Completion Order: {' → '.join(self.engine.completion_order)}")
        else:
            self.lbl_completion_order.config(text="Completion Order: [ None Concluded Yet ]")
            
        # Blocked Queue Display
        blocked = [p.pid for p in self.engine.blocked_queue]
        
        if blocked:
            self.lbl_ready_queue.config(
                text=self.lbl_ready_queue.cget("text") +
                f"   |   Blocked Queue: [ {', '.join(blocked)} ]"
            )

        self.gantt_canvas.delete("all")
        for entry in self.engine.gantt_chart:
            label = entry[:entry.find("(")]
            time_part = entry[entry.find("(") + 1 : entry.find(")")]
            start_tick, end_tick = map(int, time_part.split("-"))

            x_start = start_tick * self.block_width_per_tick + 10
            x_end = end_tick * self.block_width_per_tick + 10
            fill_hex = self.get_process_color(label)

            self.gantt_canvas.create_rectangle(x_start, self.start_y_offset, x_end, self.start_y_offset + self.block_height, fill=fill_hex, outline="#555555", width=1)
            self.gantt_canvas.create_text((x_start + x_end) / 2, self.start_y_offset + (self.block_height / 2), text=label, fill="white", font=("Consolas", 9, "bold"))
            self.gantt_canvas.create_text(x_start, self.start_y_offset + self.block_height + 9, text=str(start_tick), fill="#777777", font=("Consolas", 8))
            self.gantt_canvas.create_text(x_end, self.start_y_offset + self.block_height + 9, text=str(end_tick), fill="#777777", font=("Consolas", 8))

        self.gantt_canvas.config(scrollregion=self.gantt_canvas.bbox("all"))
        self.gantt_canvas.xview_moveto(1.0)

        self.calculate_live_metrics()
        
        selected_items = self.tree.selection()
        selected_pid = self.tree.item(selected_items[0])['values'][0] if selected_items else None

        for item in self.tree.get_children():
            self.tree.delete(item)

        for p in self.engine.processes:
            tat = p.completion_time - p.arrival_time if p.remaining_time == 0 else ""
            wt = tat - p.burst_time if tat != "" else ""
            rt = p.response_time if p.response_time != -1 else ""
            ct = p.completion_time if p.remaining_time == 0 else ""

            if p.remaining_time == 0: row_tag = "completed"
            elif active_proc and p.pid == active_proc.pid: row_tag = "running"
            elif p.arrival_time <= self.engine.clock: row_tag = "waiting"
            else: row_tag = "future"

            inserted_item = self.tree.insert("", "end", values=(
                p.pid, p.arrival_time, p.burst_time, p.priority,
                p.remaining_time if p.remaining_time > 0 else "0 (Done)",
                ct, tat, wt, rt
            ), tags=(row_tag,))
            
            if selected_pid and p.pid == selected_pid: self.tree.selection_set(inserted_item)

    def calculate_live_metrics(self):
        total_wt, total_tat, total_rt = 0, 0, 0
        executed_count = 0
        n = len(self.engine.processes)

        for p in self.engine.processes:
            if p.response_time != -1: total_rt += p.response_time
            if p.remaining_time == 0:
                p_tat = p.completion_time - p.arrival_time
                p_wt = p_tat - p.burst_time
                total_tat += p_tat
                total_wt += p_wt
                executed_count += 1
            else:
                if p.arrival_time <= self.engine.clock:
                    approx_tat = self.engine.clock - p.arrival_time
                    approx_wt = approx_tat - (p.burst_time - p.remaining_time)
                    total_tat += approx_tat
                    total_wt += max(0, approx_wt)

        first_arrival = min(p.arrival_time for p in self.engine.processes)
        span = self.engine.clock - first_arrival

        idle_duration = 0
        for entry in self.engine.gantt_chart:
            if entry.startswith("Idle"):
                time_part = entry[entry.find("(") + 1 : entry.find(")")]
                start, end = map(int, time_part.split("-"))
                idle_duration += end - start

        cpu_util = ((span - idle_duration) / span) * 100 if span > 0 else 0
        throughput = executed_count / span if span > 0 else 0

        self.metric_vars["Avg WT:"].set(f"{round(total_wt / n, 2):.2f}")
        self.metric_vars["Avg TAT:"].set(f"{round(total_tat / n, 2):.2f}")
        self.metric_vars["CPU Util:"].set(f"{round(cpu_util, 1):.1f} %")
        self.metric_vars["Throughput:"].set(f"{round(throughput, 3):.3f}")
        self.metric_vars["Ctx Switches:"].set(str(self.engine.context_switches))

    def inject_process(self):
        res = self.validate_inputs(check_quantum=True, check_pid_exists=True)
        if res:
            pid, at, bt, pr = res
            self.engine.add_process_dynamic(pid, at, bt, priority=pr)
            self.entry_pid.delete(0, tk.END)
            self.entry_pid.insert(0, f"P{len(self.engine.processes)+1}")
            self.update_ui_state()

    def modify_process(self):
        """FIXED: Integrates modification parameter logic updates seamlessly across AT bounds."""
        res = self.validate_inputs(check_quantum=False, check_pid_exists=False)
        if res:
            pid, at, bt, pr = res
            success = self.engine.modify_process_live(pid, at, bt, pr)
            if success:
                self.update_ui_state()
                messagebox.showinfo("Success", f"Process {pid} properties updated successfully.")
            else:
                messagebox.showerror("Error", f"Could not modify {pid}. Process is currently running on CPU or has finished.")

    def remove_process(self):
        pid = self.entry_pid.get().strip()
        if not pid:
            messagebox.showerror("Error", "Specify valid process ID inside input field context to evict.")
            return
        success = self.engine.remove_process_live(pid)
        if success:
            self.update_ui_state()
            messagebox.showinfo("Success", f"Process {pid} evicted successfully from ready state queues.")
        else:
            messagebox.showerror("Failure", f"Eviction error. {pid} might be currently processing or already terminated.")

    def on_tree_select_populate(self, event):
        selected = self.tree.selection()
        if selected:
            vals = self.tree.item(selected[0])['values']
            self.entry_pid.delete(0, tk.END)
            self.entry_pid.insert(0, str(vals[0]))
            self.entry_at.delete(0, tk.END)
            self.entry_at.insert(0, str(vals[1]))
            self.entry_bt.delete(0, tk.END)
            self.entry_bt.insert(0, str(vals[2]))
            self.entry_pr.delete(0, tk.END)
            self.entry_pr.insert(0, str(vals[3]))

    def on_algorithm_change(self, event):
        selected_algo = self.algo_var.get()
        self.apply_target_algorithm(selected_algo)
        self.update_ui_state()

    def reset_simulation(self):
        self.is_running = False
        self.btn_start_pause.config(text="▶ Start", bg="#218838")
        self.engine.reset_simulation(algorithm=self.algo_var.get())
        self.entry_pid.delete(0, tk.END)
        self.entry_pid.insert(0, f"P{len(self.engine.processes)+1}")
        self.update_ui_state()

    def export_to_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["PID", "Arrival Time", "Burst Time", "Priority", "Completion Time", "Turnaround Time", "Waiting Time", "Response Time"])
                for p in self.engine.processes:
                    tat = p.completion_time - p.arrival_time if p.remaining_time == 0 else ""
                    wt = tat - p.burst_time if tat != "" else ""
                    writer.writerow([p.pid, p.arrival_time, p.burst_time, p.priority, p.completion_time, tat, wt, p.response_time])
            messagebox.showinfo("Export Complete", "Data metrics logs written successfully.")
        except Exception as e:
            messagebox.showerror("Export Failure", f"An error occurred while saving: {str(e)}")
    def toggle_theme(self):
    
        if self.dark_mode:
    
            # LIGHT MODE
            self.root.configure(bg="white")
    
            self.lbl_clock.config(bg="#eeeeee", fg="black")
            self.lbl_running_proc.config(bg="#eeeeee", fg="black")
            self.lbl_ready_queue.config(bg="#f5f5f5", fg="black")
            self.lbl_completion_order.config(bg="#f5f5f5", fg="black")
    
            self.gantt_canvas.config(bg="white")
    
            self.dark_mode = False
    
        else:
    
            # DARK MODE
            self.root.configure(bg="#222222")
    
            self.lbl_clock.config(bg="#151515", fg="#00ff00")
            self.lbl_running_proc.config(bg="#151515", fg="#ffcc00")
            self.lbl_ready_queue.config(bg="#1a1a1a", fg="#00ffcc")
            self.lbl_completion_order.config(bg="#1a1a1a", fg="#ffaa00")
    
            self.gantt_canvas.config(bg="#111111")
    
            self.dark_mode = True
    def simulation_finished_notification(self):
        self.btn_start_pause.config(text="▶ Start", bg="#218838")
        self.update_ui_state()
        
        summary_window = tk.Toplevel(self.root)
        summary_window.title(f"Final Report Results Summary")
        summary_window.geometry("600x380")
        summary_window.configure(bg="#1a1a1a")
        
        tk.Label(summary_window, text="Simulation Final Report Analysis", fg="#00ffcc", bg="#1a1a1a", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        box = tk.Text(summary_window, bg="#252525", fg="white", font=("Consolas", 9), bd=0, padx=10, pady=10)
        box.pack(fill="both", expand=True, padx=15, pady=10)
        
        auto_adopt_status = "ON" if self.ai_auto_adopt_var.get() else "OFF"
        
        report = []
        report.append(f"Selected Algorithm Strategy:    {self.engine.algorithm}")
        report.append(f"Suggested Adaptive Strategy:   {self.latest_recommendation}")
        report.append(f"Auto-Adopt Automation Toggle:   {auto_adopt_status}")
        report.append("-" * 65)
        report.append(f"Execution Span Timeline:        {self.engine.clock} ticks")
        report.append(f"Gantt Progression Block Map:    {' -> '.join(self.engine.gantt_chart)}")
        report.append(f"Completion Sequence Graph:      {' -> '.join(self.engine.completion_order)}")
        report.append(f"Average Waiting Duration:       {self.metric_vars['Avg WT:'].get()} ticks")
        report.append(f"Average Turnaround Duration:    {self.metric_vars['Avg TAT:'].get()} ticks")
        report.append(f"Context Switches Overhead:      {self.engine.context_switches} switches")
        report.append(f"CPU Utilization Coefficient:    {self.metric_vars['CPU Util:'].get()}")
        report.append(f"Throughput Efficiency Value:    {self.metric_vars['Throughput:'].get()} processes/tick")
        
        box.insert("1.0", "\n".join(report))
        box.config(state="disabled")


# APPLICATION EXECUTION ROOT

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorGUI(root)
    root.mainloop()