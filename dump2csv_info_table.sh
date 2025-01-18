#!/bin/bash

sqlite3 -header -csv ./ev_charging.db "SELECT * FROM charging_station_info;" > ev_charging_db_info.csv
