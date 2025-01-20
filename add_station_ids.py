### EV charging Webscrape -- station_id_add ###
# 
# reqs:
    # the original main script must be setup

"""
Description: This script adds charging stations to the scraper running on 'Chargepoint' given numerical argument input.

example command line execution->> python3 add_station_ids.py 8416141 2011511

Summary: the user provided stations are read in as strings, verified by a quick webpage load, and then are added as
empty rows in sqlite database
params: station ids to add (only numbers allowed)
output: results (station id data added to sqlite database called 'ev_charging.db')

"""

import time
import datetime
import json
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import os
import sys
import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.firefox.options import Options
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def check_station_id_exists(station_id,driver,url):
    existance = False
    url = url+station_id
    wait = WebDriverWait(driver, 10)
    driver.get(url)
    time.sleep(8)
    get_url = driver.current_url
    wait.until(EC.url_to_be(url))
    wait = WebDriverWait(driver, 10)
    if get_url == url:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, features='html.parser')

        # get the station status
        status = soup.find('img', {'alt': 'Station image placeholder'})
    if status:
        existance = False
    else:
        existance = True
    return existance


def add_stations_to_station_info_table(station_ids: list[str], db_path: str, driver, url):
    stations_not_found = []
    stations_to_add = []
    for station in station_ids:
        station_check = check_station_id_exists(station, driver, url)
        if station_check:
            stations_to_add.append(station)
        else:
            stations_not_found.append(f'{station} -- failed to find')

    if stations_to_add:
        with sqlite3.connect(db_path) as conn:
            sql = f"SELECT * FROM {info_table_name} limit 1"
            info_table_columns = [col[0] for col in conn.cursor().execute(sql).description]
            raw_station_df = pd.DataFrame(index=[stations_to_add], columns=info_table_columns)
            station_info_update_df = raw_station_df.drop(columns='station_id').reset_index(names=['station_id'])
            station_info_update_df['timestamp'] = datetime.datetime.now()
            station_info_update_df.to_sql(info_table_name, conn, if_exists='append', index=False)

    return stations_not_found
    

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide at least one argument.")
        sys.exit(1)
    
    # this should be in config file
    ev_url = "https://driver.chargepoint.com/stations/"

    state_table_name = 'charging_station_states'
    info_table_name = 'charging_station_info'
    database_path = '/root/ev-charging-analysis/ev_charging.db'

    # this should be its own module at this point
    options = Options()
    options.add_argument("--incognito")
    options.add_argument("--nogpu")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1200")
    options.add_argument("--no-sandbox")
    options.add_argument("--enable-javascript")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)

    # get all current station ids
    with sqlite3.connect(database_path) as conn:
        sql = f"SELECT DISTINCT station_id FROM {info_table_name}"
        db_station_ids = conn.cursor().execute(sql).fetchall()
        current_station_ids = [i[0] for i in db_station_ids]

    # list comprehension to get ids given by user, and separate into existing in database or not
    station_ids_given = [
            re.sub(r"[^0-9]",'',sys.argv[i]) for i in range(1, len(sys.argv))
            ]
    station_ids_to_add = [
            id for id in station_ids_given if id not in current_station_ids
            ]
    station_already_added_list = [
            f'{id} exists in table' for id in station_ids_given if id in current_station_ids
            ]
    for station_message in station_already_added_list:
        print(station_message)
    
    if station_ids_to_add:
        stations_not_found_list = add_stations_to_station_info_table(
            station_ids_to_add,
            database_path, 
            driver, 
            ev_url)
        if stations_not_found_list:
            for station_message  in stations_not_found_list:
                print(station_message)

    # get all current station ids
    with sqlite3.connect(database_path) as conn:
        sql = f"SELECT DISTINCT station_id FROM {info_table_name}"
        db_station_ids = conn.cursor().execute(sql).fetchall()
        new_station_ids = [i[0] for i in db_station_ids]

    
    driver.quit()
    print('finished')
    if new_station_ids:
        print('added new stations: {}'.format(', '.join(new_station_ids)))
