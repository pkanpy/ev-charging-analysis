### EV charging Webscrape ###
# Puppy edition
# reqs:
    # apt-get update
    #### if failed, first try: apt-mark unhold $(apt-mark showhold)
    # apt install python3.11-venv
    # portable chrome: https://www.forum.puppylinux.com/viewtopic.php?t=12402&sid=62ae50f256cb7109a36165ec82473d27
    # chromedriver stuff: https://stackoverflow.com/questions/48649230/how-to-update-chromedriver-on-ubuntu
	# use absolute paths
	# to test in terminal: 
	#     /bin/sh -c "cd ~ && /root/ev-charging-analysis/venv/bin/python /root/ev-charging-analysis/main.py"
	#     */5 * * * *     is format in crontab -e, use above shell command to run
	# set up git, need to store credentials:  git config --global credential.helper store

"""
Description: This program scrapes charging data from the website 'Chargepoint'.

Summary: Details on the charging point status (in use/available) and the last car model to charge are collected by the station,
a list which can be found in the main loop. The data is formatted in a pandas DataFrame and then appended to a sqlite
database. Additionally, in the first 5 minutes of the 23rd day of a month, the station data (like charge rate) is
scraped and added to a separate table in the sqlite database.
params: none
output: none (data added to sqlite database called 'ev_charging.db')

notes: chargepoint seems to block AWS ec2 instance, would need a proxy but this seems against the spirit of scraping
"""

import time
import datetime
import json
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.firefox.options import Options
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# from webdriver_manager.chrome import ChromeDriverManager
# from pyvirtualdisplay import Display  # didn't work
# from fake_useragent import UserAgent


# get the status data of a station
def get_status_data(url, station_id):
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

        # get the port 1 status
        port_1 = soup.find('div', {'data-qa-id': 'port_1'})
        print(port_1)

        # refresh and retry to load site if failed
        try_count = 1
        while port_1 is None and try_count <= 5:
            driver.refresh()
            time.sleep(11 + try_count**2)
            wait.until(EC.url_to_be(url))
            wait = WebDriverWait(driver, 10)
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, features='html.parser')
            port_1 = soup.find('div', {'data-qa-id': 'port_1'})
            print(port_1)
            try_count += 1
            print('try ' + str(try_count))
        # If failed, return failure
        if try_count == 6:
            current_state_df = pd.DataFrame(
                {'station_id': [station_id],
                 'timestamp': [datetime.datetime.now()],
                 'port_1_status': ['failed'],
                 'port_2_status': ['failed'],
                 'car_charge_slice': ['failed'],
                 'port_1_change_flag': [0],
                 'port_2_change_flag': [0]
                 }
            )
            print('failed')
            print(soup.text)
            return current_state_df

        # get port 1 status
        port_1_state = port_1.find('span', {'data-qa-id': 'port_status_pill_available'})
        if port_1_state is None:
            port_1_state = 'in_use'
        else:
            port_1_state = 'available'

        # get the port 2 status
        port_2 = soup.find('div', {'data-qa-id': 'port_2'})
        if port_2 is not None:
            port_2_state = port_2.find('span', {'data-qa-id': 'port_status_pill_available'})
            if port_2_state is None:
                port_2_state = 'in_use'
            else:
                port_2_state = 'available'
        else:
            port_2_state = 'N/A'

        # get last used data on cars and dates, format lists to json
        car_states = soup.find('div', {'data-qa-id':'last_used-accordion-panel'})
        charged_cars = [s.string for s in car_states.find_all("h5")]
        charge_dates = [s.string for s in car_states.find_all("p")]
        json_array = json.dumps([{charged_cars[i]: charge_dates[i]} for i in range(len(charged_cars))])

        # format and add data into dataframe
        current_state_df = pd.DataFrame(
            {'station_id': [station_id],
             'timestamp': [datetime.datetime.now()],
             'port_1_status': [port_1_state],
             'port_2_status': [port_2_state],
             'car_charge_slice': [json_array],
             'port_1_change_flag': [0],
             'port_2_change_flag': [0]
             }
        )
    return current_state_df


# get station info (triggered in main on occasion)
def get_station_info(url, station_id):
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

        # get the port 1 status
        port_1 = soup.find('div', {'data-qa-id': 'port_1'})

        # refresh and retry if site load fails
        try_count = 1
        while port_1 is None and try_count <= 5:
            driver.refresh()
            time.sleep(11 + try_count**2)
            wait.until(EC.url_to_be(url))
            wait = WebDriverWait(driver, 10)
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, features='html.parser')
            port_1 = soup.find('div', {'data-qa-id': 'port_1'})
            try_count += 1
            print('try ' + str(try_count))
            # If failed, return failure
        if try_count == 6:
            current_state_df = pd.DataFrame(
                {'station_id': [station_id],
                 'timestamp': [datetime.datetime.now()],
                 'port_1_status': ['failed'],
                 'port_2_status': ['failed'],
                 'car_charge_slice': ['failed'],
                 'port_1_change_flag': [0],
                 'port_2_change_flag': [0]
                 }
            )
            return current_state_df

        # get port 1 and 2 status (port 2 is optional)
        port_1_info = json.dumps([s.string for s in port_1.find_all("p")])
        port_2 = soup.find('div', {'data-qa-id': 'port_2'})
        if port_2 is not None:
            port_2_info = json.dumps([s.string for s in port_2.find_all("p")])
        else:
            port_2_info = 'N/A'

        # format
        station_info_df = pd.DataFrame(
            {'station_id': [station_id],
             'timestamp': [datetime.datetime.now()],
             'port_1_info': [port_1_info],
             'port_2_info': [port_2_info],
             'port_1_change_flag': [0],
             'port_2_change_flag': [0]
             }
        )
    return station_info_df

# main
if __name__ == '__main__':
    # initialize url, stations, sqlite connection, and chrome webdriver (headless)
    ev_url = "https://driver.chargepoint.com/stations/"
    station_list = ['554251', '5426281', '5426291','15906911','15906941']
    state_table_name = 'charging_station_states'
    info_table_name = 'charging_station_info'
    conn = sqlite3.connect('/root/ev-charging-analysis/ev_charging.db')
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

    # ua = UserAgent()
    # user_agent = ua.random
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver = webdriver.Chrome(options=options)
    
    # cService = webdriver.ChromeService(executable_path='/usr/bin/chromedriver')
    # driver = webdriver.Chrome(service = cService)

    # driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    # driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})

    # setup loop over stations and trigger for station info update
    state_df_list = []
    info_trigger = ((datetime.datetime.today().day == 23)
                    & (datetime.datetime.today().hour < 1)
                    & (datetime.datetime.today().minute < 5))
    info_df_list = []
    for station in station_list:
        # scrape status data
        print(station)
        current_station_state_df = get_status_data(ev_url, station)

        # get the last row of data for the station put into the database
        sql = f"SELECT * FROM {state_table_name} where station_id = {station} order by timestamp DESC limit 1"
        last_station_state = conn.cursor().execute(sql).fetchone()
        print(last_station_state)

        # compare the last station data to the first and flag a change if found
        # !! flawed !!
        # does not account for initial failures (will trigger change flags on fail)
        # but no better solution to flag changes unless sample time increases
        if (last_station_state is None) and ~(current_station_state_df.empty):
	        pass
        elif ((last_station_state[2] != current_station_state_df.loc[0, 'port_1_status']) and
                (last_station_state[2] != 'failed') and
                (last_station_state[4] != current_station_state_df.loc[0, 'car_charge_slice'])):
            current_station_state_df['port_1_change_flag'] = 1
        elif ((last_station_state[3] != current_station_state_df.loc[0, 'port_2_status']) and
                (last_station_state[3] != 'failed') and
                (last_station_state[4] != current_station_state_df.loc[0, 'car_charge_slice'])):
            current_station_state_df['port_2_change_flag'] = 1

        # add station data to list for database upload
        state_df_list.append(current_station_state_df)

        # if time, trigger the station info update for the station
        if info_trigger:
            current_station_info_df = get_station_info(ev_url, station)
            sql = f"SELECT * FROM {info_table_name} where station_id = {station} order by timestamp DESC limit 1"
            last_station_state = conn.cursor().execute(sql).fetchone()
            if (last_station_state is None) and ~(current_station_state_df.empty):
	            pass
            if ((last_station_state[2] != current_station_info_df.loc[0, 'port_1_info']) and
                    (last_station_state[2] != 'failure')):
                current_station_info_df['port_1_change_flag'] = 1
            if ((last_station_state[3] != current_station_info_df.loc[0, 'port_2_info']) and
                    (last_station_state[2] != 'failure')):
                current_station_info_df['port_2_change_flag'] = 1
            info_df_list.append(current_station_info_df)

    # combine all station data, if issues, there should be some error notification
    station_state_update_df = pd.concat(state_df_list, ignore_index=True)
    if 'failed' in station_state_update_df['car_charge_slice'].to_list():
        send = 'error email notification'

    # insert data into sqlite database regardless
    rows_inserted = station_state_update_df.to_sql(state_table_name, conn, if_exists='append', index=False)
    if info_trigger:
        station_info_update_df = pd.concat(info_df_list, ignore_index=True)
        if ('failed' in station_info_update_df['port_1_info'].to_list() or
                'failed' in station_info_update_df['port_2_info'].to_list()):
            send = 'error email notification'
        info_inserted = station_info_update_df.to_sql(info_table_name, conn, if_exists='append', index=False)

    print(station_state_update_df)
    print('finished')
    driver.quit()
    time.sleep(2)
    os.system('killall chrome')

