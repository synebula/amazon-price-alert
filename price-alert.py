#!/usr/bin/env python3

import os
import re
import json
import time
import requests
import smtplib
import argparse
import logging
from copy import copy
from lxml import html
from urllib.parse import urljoin
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(name, price, url, email_info):
    try:
        if email_info['ssl']:
            s = smtplib.SMTP_SSL(email_info['smtp_url'])
        else:
            s = smtplib.SMTP(email_info['smtp_url'])
        s.login(email_info['user'], email_info['password'])
    except smtplib.SMTPAuthenticationError:
        logger.info('Failed to login')
    else:
        logger.info('Logged in! Composing message..')
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Amazon Subscribe Alert - %s' % price
        msg['From'] = email_info['user']
        msg['To'] = email_info['receive']
        text = 'The %s price is currently %s !! URL to salepage: %s' % (
            name, price, url)
        part = MIMEText(text, 'plain')
        msg.attach(part)
        s.sendmail(msg['From'], msg['To'], msg.as_string())
        logger.info('Message has been sent.')


def get_price(url, selector):
    r = requests.Session().get(url, headers={
        'User-Agent':
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
    })
    r.raise_for_status()
    tree = html.fromstring(r.text)

    try:
        # extract the price from the string
        price_string = re.findall('\d+.\d+', tree.xpath(selector)[0].text)[0]
        logger.info(price_string)
        return float(price_string.replace(',', ''))
    except (IndexError, TypeError) as e:
        logger.debug(e)
        logger.info('Didn\'t find the \'price\' element, trying again later')


def get_config(config):
    with open(config, 'r') as f:
        return json.loads(f.read())


def config_logger(debug):
    global logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    log_path = os.getcwd() + '/log.log'
    file_handler = logging.FileHandler(log_path, mode='a+')
    file_handler.setLevel(logging.WARN)  # 输出到file的log等级的开关
    formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        default='%s/config.json' % os.path.dirname(
                            os.path.realpath(__file__)),
                        help='Configuration file path')
    parser.add_argument('-t', '--poll-interval', type=int, default=30,
                        help='Time in seconds between checks')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Enable debug level logging')
    return parser.parse_args()


def main():
    args = parse_args()
    config_logger(args.debug)
    config = get_config(args.config)
    items = config['items']

    while True and len(items):
        for item in copy(items):
            logger.info('Checking price for %s (should be lower than %s)' % (
                item['name'], item['price']))
            item_page = urljoin(config['base_url'], item['key'])
            price = get_price(item_page, config['xpath_selector'])
            if not price:
                continue
            elif price <= item['price']:
                logger.warning('%s price is %s!! Trying to send email.' % (item['name'], price))
                send_email(item['name'], price, item_page, config['email'])
                items.remove(item)
            else:
                logger.info('Price is %s. Ignoring...' % price)

        if len(items):
            logger.info('Sleeping for %d seconds' % args.poll_interval)
            time.sleep(args.poll_interval)
        else:
            break
    logger.info('Price alert triggered for all items, exiting.')


if __name__ == '__main__':
    main()
