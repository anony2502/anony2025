import logging
import os
import datetime
import pytz
from utils.configs import TIME_ZONE

class TZFormatter(logging.Formatter):
    """支持时区的日志格式器"""
    def __init__(self, fmt=None, datefmt=None, tz=None):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.tz = tz or pytz.UTC

    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, self.tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()


class MyLogger(logging.Logger):
    """自定义日志类，支持控制台和文件输出，可设置时区"""
    def __init__(self, name=__name__, level=logging.INFO, timezone='UTC'):
        super().__init__(name, level)

        # 初始化时区格式器
        self.timezone = pytz.timezone(timezone)
        self.log_formatter = TZFormatter(
            fmt='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            tz=self.timezone
        )

        # 避免重复添加 handler
        if self.hasHandlers():
            self.handlers.clear()

        self._setup_stream_handler()

    def _setup_stream_handler(self):
        """设置控制台输出"""
        if not any(isinstance(h, logging.StreamHandler) for h in self.handlers):
            sh = logging.StreamHandler()
            sh.setFormatter(self.log_formatter)
            self.addHandler(sh)

    def set_log_file(self, log_file=None, mode="a", add_timestamp=True):
        """设置日志输出文件"""
        if log_file is None:
            log_file = "logs/default.log"

        if add_timestamp:
            base, ext = os.path.splitext(log_file)
            timestamp = datetime.datetime.now(self.timezone).strftime("%Y%m%d")
            log_file = f"{base}_{timestamp}{ext}"

        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        fh = logging.FileHandler(log_file, encoding="utf8", mode=mode)
        fh.setFormatter(self.log_formatter)
        self.addHandler(fh)

    def set_log_level(self, log_level):
        """动态设置日志等级"""
        self.setLevel(log_level)


# 项目默认 logger 实例
logger = MyLogger(timezone=TIME_ZONE)

