import os
import requests
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# 设置日志
log_directory = "logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

log_file = os.path.join(log_directory, "currency_tracker.log")

# 创建一个 RotatingFileHandler
file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# 配置 root logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[file_handler, logging.StreamHandler()])

# 加载 .env 文件
load_dotenv()

# 配置参数
CURRENCY_PAIR = "JPYCNY=X"
CHECK_INTERVAL = 86400  # 每天检查一次
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
COMPARISON_TYPE = os.getenv("COMPARISON_TYPE", "YEAR_AVERAGE")
CUSTOM_VALUE = float(os.getenv("CUSTOM_VALUE", 0))
CUSTOM_DAYS = int(os.getenv("CUSTOM_DAYS", 7))

def get_current_rate():
    """获取当前汇率"""
    try:
        logging.info("正在获取当前汇率...")
        ticker = yf.Ticker(CURRENCY_PAIR)
        info = ticker.info
        logging.info(f"获取到的 Ticker 信息: {info}")
        
        if 'regularMarketPrice' in info:
            rate = info['regularMarketPrice']
        elif 'last' in info:
            rate = info['last']
        else:
            logging.warning("无法从 info 中获取汇率，尝试使用历史数据")
            data = yf.download(CURRENCY_PAIR, period="1d")
            if not data.empty:
                rate = data['Close'].iloc[-1]
            else:
                raise ValueError("无法获取当前汇率")
        
        logging.info(f"当前汇率: {rate}")
        return rate
    except Exception as e:
        logging.error(f"获取当前汇率时发生错误: {e}", exc_info=True)
        raise

def get_comparison_rate():
    """获取比较基准汇率"""
    if COMPARISON_TYPE == "YEAR_AVERAGE":
        return get_average_rate(365)
    elif COMPARISON_TYPE == "MONTH_AVERAGE":
        return get_average_rate(30)
    elif COMPARISON_TYPE == "CUSTOM_VALUE":
        return CUSTOM_VALUE
    elif COMPARISON_TYPE == "CUSTOM_DAYS_AVERAGE":
        return get_average_rate(CUSTOM_DAYS)
    else:
        raise ValueError(f"未知的比较类型: {COMPARISON_TYPE}")

def get_average_rate(days):
    """获取指定天数的平均汇率"""
    try:
        logging.info(f"正在获取过去 {days} 天的平均汇率...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = yf.download(CURRENCY_PAIR, start=start_date, end=end_date)
        average_rate = data['Close'].mean()
        logging.info(f"过去 {days} 天的平均汇率: {average_rate}")
        return average_rate
    except Exception as e:
        logging.error(f"获取平均汇率时发生错误: {e}", exc_info=True)
        raise

def send_email(subject, body, max_retries=3, retry_delay=5):
    """发送电子邮件通知，带有重试机制"""
    for attempt in range(max_retries):
        try:
            logging.info(f"正在尝试发送电子邮件 (尝试 {attempt + 1}/{max_retries})...")
            message = MIMEMultipart()
            message['From'] = SENDER_EMAIL
            message['To'] = RECIPIENT_EMAIL
            message['Subject'] = subject
            
            message.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                server.set_debuglevel(1)  # 启用调试输出
                logging.info("正在建立 SMTP 连接...")
                server.connect(SMTP_SERVER, SMTP_PORT)
                logging.info("正在启动 TLS...")
                server.starttls()
                logging.info("正在登录...")
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                logging.info("正在发送邮件...")
                server.send_message(message)
            logging.info("电子邮件发送成功")
            return
        except Exception as e:
            logging.error(f"发送电子邮件时发生错误 (尝试 {attempt + 1}/{max_retries}): {e}", exc_info=True)
            if attempt < max_retries - 1:
                logging.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                logging.error("达到最大重试次数，无法发送电子邮件")
                raise

def main():
    logging.info("程序启动")
    while True:
        try:
            current_rate = get_current_rate()
            comparison_rate = get_comparison_rate()
            
            if current_rate < comparison_rate:
                subject = "JPY/CNY 汇率低于基准值"
                body = f"当前 JPY/CNY 汇率 ({current_rate:.4f}) 低于基准值 ({comparison_rate:.4f})。"
                try:
                    send_email(subject, body)
                    logging.info(f"已发送邮件: {body}")
                except Exception as e:
                    logging.error(f"无法发送电子邮件: {e}")
            else:
                logging.info(f"当前汇率 ({current_rate:.4f}) 高于或等于基准值 ({comparison_rate:.4f})。")
            
            logging.info(f"等待 {CHECK_INTERVAL} 秒后进行下一次检查...")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.error(f"主循环中发生错误: {e}", exc_info=True)
            logging.info(f"等待 {CHECK_INTERVAL} 秒后重试...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
