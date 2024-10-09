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

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 加载 .env 文件
load_dotenv()

# 配置参数
CURRENCY_PAIR = "JPYCNY=X"
CHECK_INTERVAL = 3600  # 每小时检查一次
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

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

def get_average_rate():
    """获取过去一年的平均汇率"""
    try:
        logging.info("正在获取过去一年的平均汇率...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        data = yf.download(CURRENCY_PAIR, start=start_date, end=end_date)
        average_rate = data['Close'].mean()
        logging.info(f"过去一年的平均汇率: {average_rate}")
        return average_rate
    except Exception as e:
        logging.error(f"获取平均汇率时发生错误: {e}", exc_info=True)
        raise

def send_email(subject, body):
    """发送电子邮件通知"""
    try:
        logging.info("正在发送电子邮件...")
        message = MIMEMultipart()
        message['From'] = SENDER_EMAIL
        message['To'] = RECIPIENT_EMAIL
        message['Subject'] = subject
        
        message.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        logging.info("电子邮件发送成功")
    except Exception as e:
        logging.error(f"发送电子邮件时发生错误: {e}", exc_info=True)
        raise

def main():
    logging.info("程序启动")
    while True:
        try:
            current_rate = get_current_rate()
            average_rate = get_average_rate()
            
            if current_rate < average_rate:
                subject = "JPY/CNY 汇率低于年平均值警报"
                body = f"当前 JPY/CNY 汇率 ({current_rate:.4f}) 低于过去一年的平均值 ({average_rate:.4f})。"
                send_email(subject, body)
                logging.info(f"已发送警报邮件: {body}")
            else:
                logging.info(f"当前汇率 ({current_rate:.4f}) 高于或等于年平均值 ({average_rate:.4f})。")
            
            logging.info(f"等待 {CHECK_INTERVAL} 秒后进行下一次检查...")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.error(f"主循环中发生错误: {e}", exc_info=True)
            logging.info(f"等待 {CHECK_INTERVAL} 秒后重试...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()