@echo off
setlocal

set DATA_DIR=data
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

set TTC_GTFS_URL=https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7795b45e-e65a-4465-81fc-c36b9dfff169/resource/cfb6b2b8-6191-41e3-bda1-b175c51148cb/download/TTC%%20Routes%%20and%%20Schedules%%20Data.zip

echo Downloading TTC GTFS data...
curl -L -o "%DATA_DIR%\ttc-gtfs.zip" "%TTC_GTFS_URL%"

echo Downloading Toronto OSM extract...
curl -L -o "%DATA_DIR%\toronto.osm.pbf" "https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf"

echo.
echo Data downloaded to %DATA_DIR%\
echo.
echo Now run MOTIS import and start:
echo   docker compose --profile import run --rm motis-import
echo   docker compose up -d motis
