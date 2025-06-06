import subprocess
import re
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import time
import psutil
import socket

def run_command(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    return result.stdout.splitlines()

def extract_proc():
    data = pd.DataFrame()
    for proc in psutil.process_iter(['pid', 'status', 'name', 'username', 'cpu_percent', 'memory_info', 'create_time']):
        try:
            data = pd.concat([data, pd.DataFrame([{
                "pid": proc.info['pid'],
                "status": proc.info['status'],
                "name": proc.info['name'],
                "user": proc.info['username'],
                "cpu": proc.info['cpu_percent'],
                "mem_mb": proc.info['memory_info'].rss / (1024 * 1024),
                "start_time": datetime.fromtimestamp(proc.info['create_time']) #.strftime("%Y-%m-%d %H:%M:%S")
            }])], ignore_index=True)
        except Exception as e:
            data = pd.concat([data, pd.DataFrame([{
                "pid": 'NAN' if 'pid' not in proc.info else proc.info['pid'],
                "status": 'NAN' if 'status' not in proc.info else proc.info['status'],
                "name": type(e).__name__,
                "user": 'NAN' if 'username' not in proc.info else proc.info['username'],
                "cpu": 'NAN' if 'cpu_percent' not in proc.info else proc.info['cpu_percent'],
                "mem_mb": 'NAN' if 'memory_info' not in proc.info else proc.info['memory_info'].rss / (1024 * 1024),
                "start_time": datetime.fromtimestamp(proc.info['create_time']) #.strftime("%Y-%m-%d %H:%M:%S")
            }])], ignore_index=True)

    return data

def categorize_process(row, pids_with_ip: pd.DataFrame, threshold: float):
    now = datetime.now()
    categories = []
    local_bytes = psutil.virtual_memory().total / (1024 * 1024)
    #local_gb = local_bytes / (1024 ** 3)
    #print(f"sonde : {row["mem_mb"]} > [{int((local_bytes * (threshold/100)))} = int(({local_bytes} * ({threshold}/100)))]")

    if row["status"] == psutil.STATUS_ZOMBIE:
        categories.append("🧟 zombie")
    elif row["status"] in [psutil.STATUS_STOPPED, psutil.STATUS_DEAD, psutil.STATUS_LOCKED, psutil.STATUS_WAITING, psutil.STATUS_TRACING_STOP]:
        categories.append("⛔ bloked")
    elif row["status"] in [psutil.STATUS_SLEEPING, psutil.STATUS_IDLE, psutil.STATUS_DISK_SLEEP, psutil.STATUS_WAKING]:
        categories.append("⏸️ standby")
    if (now - row["start_time"]) > timedelta(hours=24):
        categories.append("⏳ old")
    if row["cpu"] > int(threshold):
        categories.append("🔥 intensive CPU")
    if row["mem_mb"] > int((local_bytes * (threshold/100))):
        categories.append("🔥 intensive RAM")
    if row["pid"] in pids_with_ip:
        categories.append("🌍 connected")
    return categories

def parse_logs(logs, source, regex) -> pd.DataFrame:
    data = pd.DataFrame()
    for line in logs:
        if regex.search(line):
            timestamp = datetime.now()
            match = re.search(r'(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})', line)
            if match:
                try:
                    timestamp = datetime.strptime(match.group(1), "%b %d %H:%M:%S").replace(year=datetime.now().year)
                except:
                    pass
            data = pd.concat([data, pd.DataFrame([{
                'timestamp': timestamp,
                'source': source,
                'message': line
            }])], ignore_index=True)
    
    return data

def extract_dmesg():
    try:
        output = run_command("dmesg --color=never")
        if not output:
            raise PermissionError("dmesg empty or inaccessible")
        return output
    except Exception as e:
        return []

def extract_kern_log():
    path = Path("/var/log/kern.log")
    if not path.exists():
        print("File /var/log/kern.log not found")
        return []
    
    try:
        with open(path) as f:
            output = f.read()
        return output.splitlines()
    except Exception as e:
        print(f"kern.log read Exception : {e}")
        return []

def extract_logs(config) -> pd.DataFrame:
    keywords = config["keywords"]
    regex = re.compile('|'.join(keywords), re.IGNORECASE)
    data = pd.DataFrame()

    if "dmesg" in config["log_sources"]:
        logs = extract_dmesg()
        if len(logs) == 0:
            logs = extract_kern_log()
            tmp_data = parse_logs(logs, "kern.log", regex)
            data = pd.concat([data, tmp_data], ignore_index=True)
        else:
            tmp_data = parse_logs(logs, "dmesg", regex)
            data = pd.concat([data, tmp_data], ignore_index=True)

    if "journalctl" in config["log_sources"]:
        lines = config.get("journalctl_lines", 1000)
        logs = run_command(f"journalctl -k -n {lines}")
        tmp_data = parse_logs(logs, "journalctl", regex)
        data = pd.concat([data, tmp_data], ignore_index=True)

    return data

def read_rapl_energy_uj() -> pd.DataFrame:
    try:
        result = subprocess.check_output(["sudo", "./read_power.sh"])
        return int(result.strip())
    except Exception as e:
        print("read sudo Exception:", e)
        return None

def extract_power():
    data = pd.DataFrame()
    e1 = read_rapl_energy_uj()
    time.sleep(1)
    e2 = read_rapl_energy_uj()
    if e1 and e2:
        power_watts = (e2 - e1) / 1_000_000  # µJ → W·s/s → W
        data = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            "watts": round(power_watts, 2),
        }])
    
    return data

def get_interface_for_ip(ip):
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == ip:
                return iface
    return "other"

def extract_irq_proc() -> pd.DataFrame:
    data = pd.DataFrame()
    with open('/proc/interrupts', 'r') as f:
        lines = f.readlines()

    # Extraire les noms des CPUs depuis la 1re ligne
    cpus = lines[0].split()
    num_cpus = len(cpus)

    for line in lines[1:]:
        # Skip lignes non standards (comme NMI, LOC, etc.)
        if not re.match(r"^\s*\d+:.*", line):
            continue

        parts = line.split()
        irq = parts[0].strip(":")
        cpu_counts = parts[1:1+num_cpus]
        device = " ".join(parts[1+num_cpus:])
        counts = [int(x) if x.isdigit() else 0 for x in cpu_counts]
        #total = sum(int(x) for x in counts if x.isdigit())
        tmp_data = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "irq": irq,
            "device": device,
            **{f"CPU{i}": counts[i] for i in range(num_cpus)},
        #    "total": total,
            "num_cpu": num_cpus,
        }])
        data = pd.concat([data, tmp_data], ignore_index=True)

    return data

def extract_protocol_connections(interfaces, protocol_ports) -> pd.DataFrame:
    data = pd.DataFrame()
    for conn in psutil.net_connections(kind="inet"):
        laddr = conn.laddr if conn.laddr else None
        if not laddr:
            continue

        iface = "other"
        if hasattr(laddr, 'ip'):
            iface = get_interface_for_ip(laddr.ip)

        proto = "unknown"
        if hasattr(laddr, 'port'):
            for tmp_proto, tmp_port in protocol_ports.items():
                if laddr.port == tmp_port:
                    proto = tmp_proto

        remote_ip = str(conn.raddr.ip) if conn.raddr else ""
        remote_port = str(conn.raddr.port) if conn.raddr else ""
        local_ip = str(conn.laddr.ip) if conn.laddr else ""
        local_port = str(conn.laddr.port) if conn.laddr else ""
        
        tmp_data = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "protocol": proto,
            "local_ip": local_ip,
            "local_port": local_port,
            "remote_ip": remote_ip,
            "remote_port": remote_port,
            "interface": iface,
            "pid": conn.pid,
            "status": conn.status,
        }])
        data = pd.concat([data, tmp_data], ignore_index=True)

    return data