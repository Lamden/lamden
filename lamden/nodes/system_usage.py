import psutil
import asyncio
import json
from lamden.logger.base import get_logger
from datetime import datetime

class SystemUsage:
    def __init__(self):
        self.log = get_logger("SYSTEM USAGE")

        self.running = False

        self.last_print = datetime.now()
        self.print_delay = 0
        self.print_task = None

    async def start(self, delay_sec):
        self.running = True
        self.print_delay = delay_sec

        self.print_task = asyncio.ensure_future(self.print_loop())


    async def print_loop(self):
        while self.running:
            self.print_usage()
            await asyncio.sleep(self.print_delay)

    def stop(self):
        self.running = False

    async def stopping(self):
        if not self.print_task:
            return
        self.print_task.cancel()
        while not self.print_task.done():
            await asyncio.sleep(0.1)

    def print_usage(self):
        now = datetime.now()
        diff = now - self.last_print
        if diff.seconds < self.print_delay:
            return

        self.log.debug(json.dumps({
            'type': 'system_load',
            'System_CPU_load': self.get_cpu_usage_pct(),
            'CPU_frequency': self.get_cpu_frequency(),
            'RAM_usage': int(self.get_ram_usage() / 1024 / 1024),
            'RAM_usage_percent': self.get_ram_usage_pct(),
            'RAM_total': int(self.get_ram_total() / 1024 / 1024),
            'Swap_usage': int(self.get_swap_usage() / 1024 / 1024),
            'Swap_total': int(self.get_swap_total() / 1024 / 1024)
        }))

        self.last_print = datetime.now()

    def get_cpu_usage_pct(self):
        """
        Obtains the system's average CPU load as measured over a period of 500 milliseconds.
        :returns: System CPU load as a percentage.
        :rtype: float
        """
        return psutil.cpu_percent(interval=0.5)

    def get_cpu_frequency(self):
        """
        Obtains the real-time value of the current CPU frequency.
        :returns: Current CPU frequency in MHz.
        :rtype: int
        """
        return int(psutil.cpu_freq().current)

    def get_ram_usage(self):
        """
        Obtains the absolute number of RAM bytes currently in use by the system.
        :returns: System RAM usage in bytes.
        :rtype: int
        """
        return int(psutil.virtual_memory().total - psutil.virtual_memory().available)

    def get_ram_total(self):
        """
        Obtains the total amount of RAM in bytes available to the system.
        :returns: Total system RAM in bytes.
        :rtype: int
        """
        return int(psutil.virtual_memory().total)

    def get_ram_usage_pct(self):
        """
        Obtains the system's current RAM usage.
        :returns: System RAM usage as a percentage.
        :rtype: float
        """
        return psutil.virtual_memory().percent

    def get_swap_usage(self):
        """
        Obtains the absolute number of Swap bytes currently in use by the system.
        :returns: System Swap usage in bytes.
        :rtype: int
        """
        return int(psutil.swap_memory().used)

    def get_swap_total(self):
        """
        Obtains the total amount of Swap in bytes available to the system.
        :returns: Total system Swap in bytes.
        :rtype: int
        """
        return int(psutil.swap_memory().total)
