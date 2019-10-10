[![Build Status](https://travis-ci.org/OCHA-DAP/hdx-scraper-geonode.svg?branch=master&ts=1)](https://travis-ci.org/OCHA-DAP/hdx-scraper-geonode) [![Coverage Status](https://coveralls.io/repos/github/OCHA-DAP/hdx-scraper-geonode/badge.svg?branch=master&ts=1)](https://coveralls.io/github/OCHA-DAP/hdx-scraper-geonode?branch=master)

The HDX Scraper Geonode Library enables easy building of scrapers for extracting data 
from geonode servers. It has class GeoNodeToHDX which has methods:
get_locationsdata, get_layersdata, generate_dataset_and_showcase.

    geonodetohdx = GeoNodeToHDX('https://geonode.wfp.org', downloader)
    # get countries where count > 0
    countries = geonodetohdx.get_countries(use_count=True)
    # get layers for country with ISO 3 code SDN
    layers = geonodetohdx.get_layers(countryiso='SDN')
    # get layers for all countries
    geonodetohdx = GeoNodeToHDX('https://geonode.themimu.info', downloader)
    layers = get_layers(countryiso=None)

There are default terms to be ignored and mapped. These can be overridden by
creating a YAML configuration with the new configuration in this format:

    ignore_data:
      - deprecated

    category_mapping:
      Elevation: 'elevation - topography - altitude'
      'Inland Waters': river

    titleabstract_mapping:
      bridges:
        - bridges
        - transportation
        - 'facilities and infrastructure'
      idp:
        camp:
          - 'displaced persons locations - camps - shelters'
          - 'internally displaced persons - idp'
        else:
          - 'internally displaced persons - idp'
  
ignore_data are any terms in the abstract that mean that the dataset 
should not be added to HDX.
  
category_mapping are mappings from the category field category__gn_description 
to HDX metadata tags.
  
titleabstract_mapping are terms in the title or abstract that mean that 
particular tags should be added to the HDX metadata tags.

For more fine grained tuning of these, you can do:

    geonodetohdx = GeoNodeToHDX('https://geonode.wfp.org', downloader)
    ignore_data = geonodetohdx.get_ignore_data() 
    category_mapping = geonodetohdx.get_category_mapping() 
    titleabstract_mapping = geonodetohdx.get_titleabstract_mapping()         