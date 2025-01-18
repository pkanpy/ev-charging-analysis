#!/bin/bash

sqlite3 -header -csv ./ev_charging.db "SELECT * FROM charging_station_states;" > ev_charging_db_states.csv
