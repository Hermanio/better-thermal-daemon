import multiprocessing
from abc import ABCMeta, abstractmethod


class Governor(object):
    __metaclass__ = ABCMeta

    def __init__(self, min_perf_pct, max_perf_pct, num_pstates, turbo_pct):
        """
        Init shared components.
        Other governors may want to use multiple temperature levels or different MHz steppings
        or aggressive polling, thus we don't set these here.
        """
        self.pstate_path = "/sys/devices/system/cpu/intel_pstate/"
        self.package_temperature_path = "/sys/devices/platform/coretemp.0/hwmon/hwmon2/temp1_input"
        self.package_max_temp_path = "/sys/devices/platform/coretemp.0/hwmon/hwmon2/temp1_max"
        self.package_critical_temp_path = "/sys/devices/platform/coretemp.0/hwmon/hwmon2/temp1_crit"

        self.governor_name = None

        self.current_min_pct = min_perf_pct
        self.current_max_pct = max_perf_pct

        self.small_pct_stepping = None
        self.big_pct_stepping = None

        self.min_pct_limit = None
        self.max_pct_limit = None

        self.no_turbo = None

        self.current_temperature = None
        self.package_max_temp = None
        self.package_critical_temp = None

        self.governor_thread = None

        self.read_initial_temps()

    @abstractmethod
    def start(self):
        """
        Method containing main loop. Gets called via multiprocess API.
        :return:
        """
        pass

    @abstractmethod
    def apply_action(self, action):
        """
        Apply the given action.
        :param action:
        :return:
        """
        pass

    @abstractmethod
    def decide_action(self):
        """
        Takes into account current clock, low-normal-high and makes decision
        :return:
        """
        pass

    def get_status(self):
        """
        Returns the current state (min perf pct, max perf pct, no turbo status)
        :return:
        """
        stats = {
            "min_perf_pct": "min_perf_pct",
            "max_perf_pct ": "max_perf_pct",
            "no_turbo": "no_turbo"
        }

        for stat, path in stats.items():
            with open("/sys/devices/system/cpu/intel_pstate/{:s}".format(path)) as f:
                print("{:s}:\t{:s}".format(stat, f.read()), end='')
        print()

    def run_governor(self):
        """
        Starts the governor process.
        """
        self.governor_thread = multiprocessing.Process(target=self.start)
        self.governor_thread.start()

    def stop_governor(self):
        """
        Stops the governor main loop from running.
        :return:
        """
        print("Stopping governor {:s}...".format(self.governor_name))
        self.governor_thread.terminate()
        self.governor_thread = None

    def read_initial_temps(self):
        """
        Reads the max and critical temperatures in order to determine the default
        :return:
        """

        with open(self.package_temperature_path, "r") as f:
            self.current_temperature = int(f.read()) / 1000

        with open(self.package_max_temp_path, "r") as f:
            self.package_max_temp = int(f.read()) / 1000

        with open(self.package_critical_temp_path, "r") as f:
            self.package_critical_temp = int(f.read()) / 1000

    def read_current_temps(self):
        """
        Simply reads the current package temperature.
        Alternative to reading all of the core temps and getting the maximum of them.
        Through basic observation the package temperature seems to be the maximum of the individual cores.
        :return:
        """
        with open(self.package_temperature_path, "r") as f:
            self.current_temperature = int(f.read()) / 1000

    def calculate_noturbo_max_pct(self, min_perf_pct, max_perf_pct, num_pstates, turbo_pct):
        """
        Calculates the performance percentage at the turbo clock speed limit.
        Used to allow proper throttling when no_turbo is set to 1, as we need the proper percentages to perform throttling.
        :param min_perf_pct:
        :param max_perf_pct:
        :param num_pstates:
        :param turbo_pct:
        :return:
        """
        percentage_range = max_perf_pct - min_perf_pct
        step_pct = percentage_range / (num_pstates - 1)
        nonturbo_range_pct = (100 - turbo_pct) / 100
        turbo_range_start_as_step_count = nonturbo_range_pct * num_pstates
        turbo_range_as_pct = min_perf_pct + (turbo_range_start_as_step_count * step_pct)
        return int(turbo_range_as_pct)
