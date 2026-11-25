"""Shared constants and helpers for the sustainability analyses."""
from pyproj import Transformer

CRS = "+proj=aea +lat_1=10 +lat_2=30 +lat_0=18.75 +lon_0=102 +datum=WGS84 +units=m +no_defs"
TO_XY = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
CELL_M = 5000.0
CELL_AREA_KM2 = 25.0

# Future window: 2050, the middle of the SSP grids' 2010-2100 range and consistent with the
# climate analysis window once the EM-Earth scenarios are inspected.
YEAR_2050 = 2050
